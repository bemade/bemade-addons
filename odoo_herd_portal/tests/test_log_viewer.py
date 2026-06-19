# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
"""Feature C -- live log viewer (Odoo side) acceptance tests.

The streaming sidecar is a SEPARATE service; these tests cover ONLY the Odoo
side: the signed short-lived scope-token mint, the portal route, and the
iframe/postMessage handoff page.

Acceptance criteria under test:

* (a) Token mint for an OWNED instance produces a token of the form
  ``b64url(payload).b64url(hmac_sha256(secret, b64url_payload))``. Decoding the
  payload yields the correct ``ns`` (instance namespace), ``sel``
  (``bemade.org/instance=<name>``) and ``iid`` (instance id); ``exp`` is about
  ``now + 120``; recomputing the HMAC with the stored secret matches the
  signature.
* (b) Tampering with the payload, or signing/verifying with a wrong secret,
  makes verification FAIL.
* (c) A token whose ``exp`` is in the past is rejected by the verify helper.
* (d) IDOR: ``/my/instances/<id>/logs`` for a NON-owned instance redirects (or
  404s) and mints NO token -- the response body contains no token and no
  ``<iframe>``.
* (e) The rendered logs page does NOT contain the signing secret nor the
  namespace in clear text (outside the opaque signed token), and the token is
  NOT present in the iframe ``src`` URL.
* (f) The "recent logs only" notice is present on the page.

The token mint helper is stdlib-only (hmac/hashlib/base64/json/time); no live
cluster is touched, so nothing is stubbed.
"""

import base64
import hashlib
import hmac
import json
import time

from odoo.tests import HttpCase, TransactionCase, tagged

SECRET_PARAM = "odoo_herd_portal.log_token_secret"
VIEWER_URL_PARAM = "odoo_herd_portal.log_viewer_url"


def _b64url_decode(segment):
    """Decode an unpadded urlsafe base64 string (mirrors the sidecar)."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _verify_token(token, secret, *, now=None):
    """Standalone verifier mirroring what the SIDECAR must implement.

    Returns the decoded payload dict on success; raises ``ValueError`` on a bad
    structure, signature mismatch, or expiry. This is intentionally written
    here (not imported from the module) so the test proves the wire format is
    independently verifiable.
    """
    if now is None:
        now = int(time.time())
    try:
        payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("malformed token") from exc
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    got = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected, got):
        raise ValueError("bad signature")
    payload = json.loads(_b64url_decode(payload_b64))
    if int(payload.get("exp", 0)) < now:
        raise ValueError("expired")
    return payload


def _common_fixtures(cls):
    """Two companies, two portal users, one owned + one foreign instance."""
    Partner = cls.env["res.partner"]
    Users = cls.env["res.users"]
    portal_group = cls.env.ref("base.group_portal")

    cls.company_a = Partner.create({"name": "Logs Co A", "is_company": True})
    cls.company_b = Partner.create({"name": "Logs Co B", "is_company": True})

    cls.user_a = Users.create(
        {
            "name": "Logs User A",
            "login": "logs_user_a",
            "password": "logs_user_a",
            "email": "logs_a@example.com",
            "partner_id": cls.company_a.id,
            "group_ids": [(6, 0, [portal_group.id])],
        }
    )

    cls.cluster = cls.env["k8s.cluster"].create(
        {
            "name": "Logs Test Cluster",
            "api_endpoint": "https://example.invalid:6443",
            "kubeconfig": "apiVersion: v1\nkind: Config\n",
            "default_namespace": "default",
            "active": False,
        }
    )

    Instance = cls.env["k8s.odoo.instance"]
    # NB: the namespace is deliberately NOT a substring of the instance name,
    # so the no-leak assertions can tell a namespace leak apart from the
    # instance name (which is legitimately displayed on the page).
    cls.inst_a = Instance.create(
        {
            "name": "alpha-prod",
            "namespace": "nsclient-alpha",
            "cluster_id": cls.cluster.id,
            "environment": "production",
            "allowed_partner_ids": [(6, 0, [cls.company_a.id])],
        }
    )
    cls.inst_b = Instance.create(
        {
            "name": "bravo-prod",
            "namespace": "nsclient-bravo",
            "cluster_id": cls.cluster.id,
            "environment": "production",
            "allowed_partner_ids": [(6, 0, [cls.company_b.id])],
        }
    )

    # Configure a sidecar URL so the page renders an iframe.
    cls.env["ir.config_parameter"].sudo().set_param(
        VIEWER_URL_PARAM, "https://logs.bemade.org"
    )


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestLogTokenMint(TransactionCase):
    """Token mint / verify / tamper / expiry (a, b, c)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)

    def _secret(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param(SECRET_PARAM)
        )

    # -------------------------------------------------------------- (a)
    def test_mint_token_claims_and_signature(self):
        """Mint for an owned instance: claims correct, signature verifies."""
        Instance = self.env["k8s.odoo.instance"]
        inst = Instance.with_user(self.user_a).browse(self.inst_a.id)
        before = int(time.time())
        token = inst._mint_log_token()
        after = int(time.time())

        secret = self._secret()
        self.assertTrue(secret, "A secret must be generated on first use.")
        self.assertNotIn(
            secret, token, "The raw secret must never appear in the token."
        )

        payload = _verify_token(token, secret)
        self.assertEqual(payload["ns"], "nsclient-alpha")
        self.assertEqual(payload["sel"], "bemade.org/instance=alpha-prod")
        self.assertEqual(payload["iid"], self.inst_a.id)
        # exp ~ now + 120 (allow for the second the mint took).
        self.assertGreaterEqual(payload["exp"], before + 120)
        self.assertLessEqual(payload["exp"], after + 120)
        self.assertGreaterEqual(payload["iat"], before)
        self.assertLessEqual(payload["iat"], after)

    def test_secret_is_persisted_and_stable(self):
        """The generated secret is reused, not regenerated each mint."""
        inst = self.env["k8s.odoo.instance"].with_user(self.user_a).browse(
            self.inst_a.id
        )
        inst._mint_log_token()
        first = self._secret()
        inst._mint_log_token()
        self.assertEqual(self._secret(), first)
        self.assertGreaterEqual(len(first), 32, "Secret must be strong.")

    # -------------------------------------------------------------- (b)
    def test_tampered_payload_fails_verification(self):
        """Altering the payload breaks the signature."""
        inst = self.env["k8s.odoo.instance"].with_user(self.user_a).browse(
            self.inst_a.id
        )
        token = inst._mint_log_token()
        secret = self._secret()
        payload_b64, sig_b64 = token.split(".")
        tampered_payload = json.dumps(
            {
                "ns": "victim-namespace",
                "sel": "bemade.org/instance=victim",
                "exp": int(time.time()) + 120,
                "iat": int(time.time()),
                "iid": 999999,
            }
        ).encode("utf-8")
        forged_b64 = (
            base64.urlsafe_b64encode(tampered_payload)
            .rstrip(b"=")
            .decode("ascii")
        )
        forged_token = "%s.%s" % (forged_b64, sig_b64)
        with self.assertRaises(ValueError):
            _verify_token(forged_token, secret)

    def test_wrong_secret_fails_verification(self):
        """Verifying with the wrong secret fails."""
        inst = self.env["k8s.odoo.instance"].with_user(self.user_a).browse(
            self.inst_a.id
        )
        token = inst._mint_log_token()
        with self.assertRaises(ValueError):
            _verify_token(token, "not-the-real-secret")

    # -------------------------------------------------------------- (c)
    def test_expired_token_rejected(self):
        """A token with exp in the past is rejected."""
        inst = self.env["k8s.odoo.instance"].with_user(self.user_a).browse(
            self.inst_a.id
        )
        token = inst._mint_log_token()
        secret = self._secret()
        # It verifies now ...
        self.assertTrue(_verify_token(token, secret))
        # ... but not when "now" is 200s in the future (past its 120s window).
        with self.assertRaises(ValueError):
            _verify_token(token, secret, now=int(time.time()) + 200)


@tagged("post_install", "-at_install", "odoo_herd_portal")
class TestLogViewerPage(HttpCase):
    """Portal route: IDOR guard + no-leak rendering (d, e, f)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _common_fixtures(cls)

    # -------------------------------------------------------------- (e, f)
    def test_logs_page_owned_renders_iframe_no_leak(self):
        """Owned instance: iframe present, token NOT in src, no secret/ns leak."""
        self.authenticate("logs_user_a", "logs_user_a")
        resp = self.url_open("/my/instances/%d/logs" % self.inst_a.id)
        self.assertEqual(resp.status_code, 200)
        body = resp.text

        # (f) recent-only notice.
        self.assertIn("recent", body.lower())

        # iframe present, pointing at the configured sidecar base URL.
        self.assertIn("<iframe", body)
        self.assertIn("https://logs.bemade.org", body)

        # (e) the signing secret never appears.
        secret = (
            self.env["ir.config_parameter"].sudo().get_param(SECRET_PARAM)
        )
        self.assertTrue(secret)
        self.assertNotIn(secret, body)

        # (e) the namespace never appears in clear text outside the token.
        # Locate the token, strip it, then assert the namespace is absent.
        self.assertIn("data-log-scope", body)
        # The iframe src must NOT carry the token as a query param.
        # Grab the iframe tag and check the token value is not inside it.
        token = self._extract_token(body)
        self.assertTrue(token, "A token must be embedded in the page.")
        iframe_tag = body[body.index("<iframe"):]
        iframe_tag = iframe_tag[: iframe_tag.index(">") + 1]
        self.assertNotIn(token, iframe_tag, "Token must NOT be in the iframe src.")
        self.assertNotIn("token=", iframe_tag.lower())

        # Namespace must not appear in clear text. It is only legitimately
        # present inside the signed (base64) token payload, so strip the token
        # out before asserting.
        body_without_token = body.replace(token, "")
        self.assertNotIn("nsclient-alpha", body_without_token)

    # -------------------------------------------------------------- (d) IDOR
    def test_logs_page_non_owned_redirects_no_token(self):
        """Non-owned instance: redirect/404, no token, no iframe."""
        self.authenticate("logs_user_a", "logs_user_a")
        resp = self.url_open(
            "/my/instances/%d/logs" % self.inst_b.id,
            allow_redirects=False,
        )
        self.assertIn(resp.status_code, (301, 302, 303, 404))
        body = resp.text
        self.assertNotIn("data-log-scope", body)
        self.assertNotIn("<iframe", body)
        self.assertNotIn("nsclient-bravo", body)

    def _extract_token(self, body):
        """Pull the token out of the data-log-scope attribute."""
        marker = 'data-log-scope="'
        idx = body.find(marker)
        if idx == -1:
            return ""
        start = idx + len(marker)
        end = body.find('"', start)
        return body[start:end]
