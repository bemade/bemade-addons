# Log-Stream Sidecar — Design (Feature C companion)

**Status:** DESIGN ONLY. The Odoo side of Feature C (token mint + portal page)
lives in this module and is tested in `tests/test_log_viewer.py`. The streaming
service described here is a **separate** deployable (`odoo-herd-log-sidecar`)
that has **not** been verified against a cluster. This document is the
contract the sidecar must honour; the scaffold implementation lives in its own
repo (`~/src/odoo-herd-log-sidecar/`, local-only at time of writing).

---

## 1. Why a separate service

Odoo must never hold a live, long-lived streaming connection open per portal
user, and must never carry a cluster credential that can `get pods/log`. The
log-stream sidecar is a small, single-purpose Go service that:

- runs **in** the RKE2 cluster with its own **least-privilege** ServiceAccount
  (`get,list,watch` on `pods`, `get` on `pods/log` — nothing else);
- accepts a request only if it carries a **valid, unexpired, signed scope
  token** minted by Odoo;
- derives *all* scoping (namespace + label selector) **from the verified token
  payload** — never from any request parameter;
- discovers the matching pods, tails their logs, multiplexes them into one
  stream, and writes merged lines back to the browser.

The trust boundary is the HMAC: Odoo and the sidecar share a 64-hex-char secret
(via a k8s `Secret`); possession of a freshly minted token is the *only* thing
that authorises a stream, and the token already encodes exactly what the
authenticated, record-rule-checked portal user is allowed to see.

---

## 2. Request flow

```
  Browser (portal)                 Odoo                       Sidecar (in-cluster)
  ----------------                 ----                       --------------------
  GET /my/instances/<id>/logs ───▶ record-rule ownership
                                   check (IDOR guard);
                                   _mint_log_token() under
                                   sudo reads ns + name
                                   AFTER ownership proven
                                ◀── HTML page: <iframe src=
                                    "https://logs.bemade.org">
                                    + token in data-log-scope
                                    (NOT in the iframe URL)

  page JS: postMessage(token) ───▶ iframe (logs.bemade.org SPA)

  iframe SPA: fetch("/stream",
    headers:{Authorization:
      "Bearer <token>"})       ───────────────────────────────▶ verify token (HMAC,
                                                                   exp); derive ns+sel
                                                                   from PAYLOAD ONLY
                                                                 list pods by ns+sel
                                                                 (informer); Follow:true
                                                                 log per pod; fan-in
                              ◀───────────────────────────────── chunked/streamed
                                  ReadableStream of merged lines
  react-logviewer renders +
  client-side search/filter
```

Key properties of the handoff:

- The token is delivered to the iframe via **`postMessage`**, and sent to the
  sidecar in an **`Authorization: Bearer`** header — it is therefore **never** a
  URL query parameter (no token in access logs, referrers, or browser history).
  The Odoo test (`test_logs_page_owned_renders_iframe_no_leak`) asserts the
  token is absent from the iframe `src` and that `token=` does not appear in the
  iframe tag.
- The iframe is served from a **different origin** (`logs.bemade.org`), so the
  parent page hands the token across with a targeted `postMessage` (the SPA must
  validate `event.origin` against the expected Odoo origin before accepting it).

---

## 3. Token-verification contract (VERBATIM — the sidecar MUST implement this)

The mint side is `K8sOdooInstance._mint_log_token` in
`models/k8s_odoo_instance.py`. The reference verifier is `_verify_token` in
`tests/test_log_viewer.py`. Both are stdlib-only; no JWT library.

### Wire format

```
token = b64url(payload_json) + "." + b64url( HMAC_SHA256(secret, b64url(payload_json)) )
```

- **`b64url`** = URL-safe base64 with the `=` padding **stripped**.
- **`payload_json`** = `json.dumps(payload, separators=(",",":"), sort_keys=True)`
  — i.e. compact separators, keys sorted, UTF-8 bytes.
- **The HMAC is computed over the ASCII bytes of the b64url payload _string_**
  (the first token segment as text), **not** over the raw payload JSON bytes.
  This is the single most important detail to get right.
- **`secret`** = the UTF-8 bytes of a 64-hex-char string (256 bits). Shared with
  Odoo out of band via a k8s `Secret`. Odoo stores it in
  `ir.config_parameter` under key `odoo_herd_portal.log_token_secret` and
  generates it on first use (`secrets.token_hex(32)`).

### Payload claims

```json
{
  "exp": <epoch int>,                         // iat + 120
  "iat": <epoch int>,
  "iid": <instance id int>,
  "ns":  "<namespace>",
  "sel": "bemade.org/instance=<instance name>"
}
```

(Keys are emitted sorted; do not rely on order when parsing — parse as a map.)

### Verify algorithm

1. Split the token on the **first** `.` into `payload_b64` and `sig_b64`.
   Reject if there is not exactly one separator.
2. Recompute `expected = HMAC_SHA256(secret_utf8, payload_b64_ascii)` (digest =
   raw 32 bytes).
3. `b64url`-decode `sig_b64` (re-pad to a multiple of 4 with `=` first) → `got`.
4. **Constant-time compare** `expected` vs `got` (`hmac.compare_digest` /
   `crypto/hmac.Equal` / `subtle.ConstantTimeCompare`). Reject on mismatch.
5. `b64url`-decode `payload_b64` (re-pad first) and JSON-parse it.
6. Reject if `exp < now` (expired).
7. **Trust ONLY `ns` and `sel` from the verified payload for scoping. Never read
   namespace/selector/instance from any request parameter, header, query, or
   body.** `iid` is informational/audit only.

Re-padding rule (matches `_b64url_decode` in the test):
`pad = "=" * (-len(segment) % 4)`.

---

## 4. Pod discovery + multiplex (Stern pattern)

### Cluster facts

- Per-instance pods carry the label **`bemade.org/instance=<name>`**. This
  covers the web pod, the `<name>-cron` pod, and transient Job pods — all share
  it.
- Namespaces are **per-client**, so multiple instances can live in one
  namespace. Scope must use **both** the namespace (`ns`) **and** the label
  selector (`sel`); the namespace alone is not sufficient isolation.

### Design

1. From the verified token take `ns` and `sel`.
2. Start a **pod informer** (or a `Watch` + initial `List`) scoped to namespace
   `ns` with label selector `sel`. This gives add/update/delete events as pods
   come and go (rollouts, cron pods spinning up, Job pods finishing).
3. For each **Running** pod (and each container, if multi-container), spawn a
   goroutine that opens a log stream with `Follow: true` (and a small
   `TailLines`/`SinceSeconds` so the user sees recent context, not the whole
   history). Each goroutine reads lines and pushes
   `{pod, container, ts, line}` records onto a shared **fan-in channel**.
4. A single writer goroutine drains the fan-in channel and writes merged,
   labelled lines to the HTTP response, flushing as it goes.
5. On pod **delete**, cancel that pod's goroutine (context cancellation). On
   pod **add**, attach a new goroutine. This is the **Stern** model: the set of
   tailed pods tracks the live selector, so a rolling deploy seamlessly moves
   the stream from old to new pods.
6. When the client disconnects (request context cancelled) or the token would
   expire mid-stream, tear everything down: cancel all per-pod contexts, stop
   the informer, close the fan-in channel.

Notes:

- Tokens are short-lived (~120 s). The stream itself may outlive the token; the
  intended posture is **re-mint on (re)connect** — the SPA fetches a fresh token
  from Odoo when it (re)opens the stream. (Optionally the sidecar may also drop
  the connection at `exp` to force a re-mint; decide during review.)
- The `iid` claim is useful as a log/audit correlation id only.

---

## 5. Streaming + frontend

- Transport: a single HTTP response that **streams** (chunked / flush-per-line).
  The browser consumes it with `fetch()` + `ReadableStream` reader (so the token
  travels in the `Authorization` header rather than a URL — SSE/`EventSource`
  cannot set arbitrary headers, which is why plain `fetch` streaming is chosen).
- Frontend: a small **react-logviewer** SPA served from `logs.bemade.org`. It:
  - receives the token via `postMessage` (origin-checked);
  - opens the stream;
  - renders lines with **client-side search / filter / highlight** (no
    server-side query needed for the recent window it holds);
  - shows the **"recent logs only"** notice.
- The SPA is **described here but not built** in the scaffold.

---

## 6. Retention caveat

This sidecar tails **live** pod logs via the Kubernetes API — it shows **recent
logs only** (what kubelet currently holds for running pods, plus a small tail
window). It is **not** a historical log store: rotated/old logs and logs from
deleted pods are gone. **Historical search is out of scope** and belongs to a
separate Loki-backed path (call it "v2"). The portal page carries an explicit
"recent logs only" notice for this reason (asserted by the Odoo test).

---

## 7. Security properties

- **Scope is authority-derived, not caller-derived.** The namespace and label
  selector come *only* from the HMAC-verified token payload. No request
  parameter can widen or redirect scope. An attacker cannot point the stream at
  another client's namespace without forging an HMAC over the shared secret.
- **Least-privilege ServiceAccount.** The sidecar's `ClusterRole` grants only
  `get,list,watch` on `pods` and `get` on `pods/log`. It can **never** exec into
  pods, read `secrets`, read `configmaps`, or touch the operator kubeconfig. A
  full compromise of the sidecar leaks *pod logs*, not cluster control.
- **Short-lived tokens.** ~120 s TTL bounds replay; `exp` is enforced.
- **Constant-time signature compare** prevents timing oracles on the MAC.
- **No token in URLs.** Bearer header + `postMessage` keep it out of logs,
  referrers, and history.
- **TLS end-to-end.** `logs.bemade.org` is fronted by Traefik with a
  cert-manager-issued certificate; the browser↔sidecar hop is HTTPS.
- **Shared secret handling.** The HMAC secret is a k8s `Secret` mounted into the
  sidecar as `LOG_TOKEN_SECRET`; it is the *same* value Odoo holds in
  `ir.config_parameter`. It must never be logged and never reach the browser
  (Odoo tests assert it is absent from the rendered page).
- **Origin checks.** The SPA must verify `event.origin` on the incoming
  `postMessage` before trusting the token.

---

## 8. Open items for human review

- Token-expiry-mid-stream policy (drop at `exp` vs. let the live stream run until
  client disconnect and rely on re-mint at reconnect).
- Whether to bound concurrent streams / pods per request (DoS guard).
- `TailLines` / `SinceSeconds` defaults for the "recent" window.
- Multi-container pods: stream all containers vs. a known primary.
- ClusterRole vs. namespaced Role(s): a ClusterRole is simplest given clients
  span many namespaces, but a tighter posture could enumerate allowed namespaces.
