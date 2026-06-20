# Epic: `odoo_herd_portal`

**Status:** Draft — requirements agreed, awaiting manifest sign-off before scaffolding.
**Module:** `odoo_herd_portal` (Odoo 19.0, LGPL-3, depends `odoo_herd` + `portal`)
**Companion:** a separate, non-Odoo **log-stream sidecar** service repo (see §6).

---

## 1. Purpose

A client-facing portal layer over `odoo_herd`. A Bemade hosting customer logs
into the central Bemade Odoo (`odoo.bemade.org`, where `odoo_herd` runs) and can
observe and — within guardrails — act on the instances their company owns,
without a support ticket and without ever seeing another client's data.

`odoo_herd` today is internal-only: no client/partner linkage, global record
rules, all access via the `K8s User` / `K8s Manager` groups. This module adds the
ownership model, portal surface, and customer-safe actions on top of it.

---

## 2. Locked scope decisions

| Decision | Choice |
| --- | --- |
| v1 features | A access · B overview · C live logs · D backups · E self-serve lifecycle |
| Portal host | Central Bemade Odoo — broad ServiceAccount, **in-code** per-instance isolation |
| Ownership | `allowed_partner_ids` (M2M) on the instance; match user's `commercial_partner_id` |
| Self-serve actions | upgrade, staging-refresh (restart deferred to v2) |
| Restore | self-service on **staging**; **production** restore is back-office only |
| Log transport | dedicated sidecar + iframe; **search + filtering required** (not tail-only) |
| Live-log scope | live + recent only (node log retention); history search is v2 (Loki) |
| License | LGPL-3 |
| Code layout | `odoo_herd_portal` addon + separate sidecar repo |

---

## 3. Ownership model (the keystone)

Everything portal-facing depends on this; build it first.

- **New field** on `k8s.odoo.instance`: `allowed_partner_ids = Many2many('res.partner')`.
  Entries are normalised to commercial partners on grant.
- **Record rule** (portal group, read):
  `[('allowed_partner_ids', 'in', user.partner_id.commercial_partner_id.ids)]`
  so any contact of an allowed company matches.
- **Provisioning:** standard Odoo portal grant on the client contact + populate
  `allowed_partner_ids` on their instances. No new login system.
- **Field exposure:** the portal ACL/templates expose a whitelist only — never
  `kubeconfig`, `spec`, `webhook_token`, or other internal fields.

> Check `feat/portal-partner-manager` branch before implementing — it may already
> cover portal↔partner wiring.

---

## 4. Feature breakdown (stories → acceptance criteria → builds-on / gaps)

### A — Access & ownership *(keystone)*
- *As a portal user I only ever see instances my company owns; another client's
  instances are invisible at the ORM layer.*
- **AC:** record rule enforces commercial-partner match; portal group has
  read-only ACL on a curated field subset; a user with no owned instances sees
  an empty, non-erroring portal; secrets never exposed.
- **Builds on:** nothing — all new (`allowed_partner_ids`, portal group, record
  rules, portal mixin).

### B — Instance overview
- *As a client I see my instances grouped into Production and Staging, with
  status, version/image, and URL.*
- **AC:** `/my/instances` list + detail driven by `environment`; staging entries
  link to their prod source via `production_instance_id`; shows `phase`,
  ready/available replicas, `ingress_url`; no internal fields leak.
- **Builds on:** existing instance data only. **No model changes.**

### C — Live log viewer
- *As a technical client I tail my instance's web + cron logs live, and
  search/filter what's on screen.*
- **AC:** selector `bemade.org/instance=<name>` multiplexes the web and `-cron`
  pods (and transient lifecycle Job pods); live tail via streamed HTTP;
  in-browser search + level/text/pod filter over the buffered window; scope comes
  **only** from an Odoo-signed short-lived token, never request params; the kube
  token never reaches the browser; UI clearly marks "recent only".
- **Builds on:** existing `action_view_logs()` / `CoreV1Api` as reference.
- **Gaps:** the sidecar (§6); JWT mint/verify; `@melloware/react-logviewer`;
  iframe embed. History search beyond retention = Loki (v2).

### D — Backups self-service
- *As a client I list and download my backups, trigger a backup, and restore
  staging myself.*
- **AC:** list owned-instance backups (state/size/time); download via S3
  pre-signed URL through an auth-checked portal endpoint; "Backup now" creates an
  `OdooBackupJob` and shows live state via the operator webhook; **restore is
  self-service only when `target.environment == 'staging'`**; production restore
  is not exposed in the portal.
- **Builds on:** `k8s.odoo.backup` (`download_url`, `state`, `size_bytes`),
  `k8s.backup.wizard`, `k8s.odoo.restore`, `k8s.s3.config`.
- **Gaps:** portal download endpoint + presign exposure; portal-safe backup-now;
  environment gate on restore.

### E — Self-serve lifecycle (upgrade, staging-refresh)
- *As a client I upgrade modules or refresh staging from prod myself, with
  guardrails.*
- **AC:** each action confirms intent and posts to the existing job pipeline;
  **upgrade auto-takes a backup first** and is restricted to safe targets;
  staging-refresh reuses existing wizard logic pre-bound to owned source/target;
  every action writes an **audit record (who/what/when)** and notifies the client
  on completion/failure.
- **Builds on:** `k8s.odoo.upgrade` + `k8s.upgrade.wizard`,
  `k8s.odoo.staging.refresh` + wizard.
- **Gaps:** audit trail is new (today only `create_uid`/`write_uid`); guardrails
  (auto-backup-before-upgrade, confirmation).

---

## 5. Cross-cutting / non-functional

- **Security:** in-code scoping is the only barrier between clients — hardened
  record rules + portal controller; field whitelist; never expose secrets.
- **Audit:** lightweight audit on every client-initiated action — foundational
  for self-serve trust.
- **Notifications:** post to the client (mail/activity) on job completion/failure
  (`mail.thread` already on the instance).
- **Token minting:** Odoo signs short-lived (~2 min) scope-bound tokens with a
  shared secret (HMAC/stdlib — no new Python dep) after the record-rule check.

---

## 6. The log-stream sidecar (separate repo)

A small standalone web service whose only job is turning "a client wants their
instance's logs" into a safe, live, multiplexed stream — without Odoo holding the
connection and without the browser touching a kube token.

**Stack:** Go (native `client-go`, cheap goroutine fan-in, single static binary)
serving the `react-logviewer` SPA as static assets. (Node/TS is the alternative.)

```
Browser — portal page (Odoo, OWL)
  │  Odoo controller checks record rule, mints short-lived JWT
  │    claims: { ns, selector: "bemade.org/instance=<name>", exp: +120s }
  │  parent page → iframe via postMessage(token)   (not in a URL → not logged)
  ▼
iframe → logs.bemade.org   (React + react-logviewer, served by the sidecar)
  │  fetch('/stream', { headers: { Authorization: 'Bearer <JWT>' } })
  │  (fetch + ReadableStream, not EventSource — lets us send the auth header)
  ▼
Sidecar (Go) — own ServiceAccount, least-privilege
  │  1. verify JWT (sig + exp) → trust ONLY ns + selector from the token
  │  2. pod informer: discover web + -cron (+ Job) pods, attach/detach as they come/go (Stern pattern)
  │  3. one goroutine per pod: Pods(ns).GetLogs(pod, {Follow:true}) → tag line → fan-in channel
  │  4. stream merged lines back to the browser
  ▼
Kube API → kubelet → container log files
```

**Safety properties:**
1. Scope comes only from the signed token; client cannot request another
   namespace/instance. Tokens short-lived and scope-bound.
2. Own minimal ServiceAccount: `get,list,watch pods` + `get pods/log`,
   read-only. No exec, no secrets, not `odoo_herd`'s broad kubeconfig.
   (ClusterRole for pods/log read vs per-namespace RoleBindings — lean ClusterRole
   since read-only and the token already enforces scope.)
3. Traefik + cert-manager TLS; same-origin iframe; JWT secret via k8s Secret.

**Search/filtering:** v1 is client-side over the live buffer (react-logviewer
highlight-search + a level/substring/pod filter box); the sidecar may grep
server-side via a token claim for chatty instances. Searching beyond retention is
Loki (v2).

---

## 7. Phasing

- **v1:** A → (B, C, D, E in parallel once A lands).
- **v2:**
  - Client-initiated staging *creation* within a quota.
  - **Log history search (Loki):** add a one-line Alloy relabel forwarding
    `bemade.org/instance` → `odoo_instance` Loki label; per-client Grafana org +
    datasource (OSS Grafana — no LBAC). Currently Loki only scopes by `namespace`
    (= client), not per-instance, until that label is added.
  - **Instance restart** as an operator-reconciled CRD action: add a trigger
    field/annotation (e.g. `restartNonce`) to `OdooInstanceSpec`; on change the
    operator stamps the owned Deployments' pod-template annotation
    (`bemade.org/restarted-at`) → rolling restart. (CRDs can't have custom verbs;
    this declarative-trigger pattern is the idiomatic equivalent.)
  - **Portal upgrade → mirror the backend wizard.** v1 triggers a fixed
    `-u all` (update all installed modules, no installs). v2 should mirror
    `odoo_herd`'s `k8s.upgrade.wizard`: module selection, scheduling, and an
    image/version bump — rather than the hardcoded standard upgrade.
  - Possibly metrics/health (Prometheus) and self-service production restore.

---

## 8. Cluster facts this design relies on (verified)

- **Namespaces are per-client, not per-instance** — e.g. `pneumac` holds both
  `pneumac-prod` and `pneumac-staging`. So namespace scopes a *client*; the
  per-instance key is the `bemade.org/instance` label.
- Each `OdooInstance` owns two Deployments: `<name>` (web, HTTP 8069 + WS 8072 in
  one container) and `<name>-cron` (runs `ir.cron`, `--no-http`). Crons are a pod,
  not k8s CronJobs.
- The operator stamps `bemade.org/instance=<name>` uniformly on **all** owned
  pods (web, cron, lifecycle Jobs) — the clean per-instance selector.
- Alloy → Loki currently forwards `namespace, pod, container, app, cluster`;
  `bemade.org/instance` is **not** yet a Loki label (hence v2 relabel).
- Loki is single-tenant `bemade`; Grafana is OSS 10.4.9 (no LBAC).
