"""Use case: the compact chatter composer shows the signature as it is sent.

Acceptance criteria
-------------------
* Hoot suite (``static/tests/*.test.js``, filtered on ``@bemade_mail_signature``):
  in « Send message » mode the composer shows the server-provided signature block
  and an « Edit » link that opens the full composer; in « Log note » mode the block
  is not shown; a user without signature sees nothing.
* Tour ``bemade_mail_signature_tour``: on a contact, « Send message » shows the
  signature; « Log note » hides it; after sending, the chatter message holds the
  signature folded under the « … » button.
"""

from odoo.tests import HttpCase, no_retry, tagged

from .common import SIGNATURE

# Modules whose JavaScript fetches a file as soon as it loads. Hoot forbids
# unmocked requests, so with any of them installed the unit-test page aborts.
HOOT_BREAKING_MODULES = ("onlyoffice_odoo",)


def _hoot_job_hash(name):
    """Same hash as ``web.tests.test_js.HOOTCommon._generate_hash``."""
    value = 0
    for char in name:
        value = (value << 5) - value + ord(char)
        value = value & 0xFFFFFFFF
    return f"{value:08x}"


@tagged("post_install", "-at_install")
class TestSignatureUi(HttpCase):
    @no_retry
    def test_hoot_composer_preview(self):
        installed = self.env["ir.module.module"].search_count(
            [("name", "in", HOOT_BREAKING_MODULES), ("state", "=", "installed")]
        )
        if installed:
            self.skipTest(
                "a module that fetches at load is installed (%s); hoot cannot run"
                % ", ".join(HOOT_BREAKING_MODULES)
            )
        job = _hoot_job_hash("@bemade_mail_signature")
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id={job}",
            "",
            "",
            login="admin",
            timeout=600,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=lambda message: "[HOOT]" not in message,
        )

    def test_tour_send_message_signed_and_folded(self):
        self.env.ref("base.user_admin").signature = SIGNATURE
        partner = self.env["res.partner"].create(
            {"name": "Tour Customer", "email": "tour.customer@example.com"}
        )
        self.start_tour(
            f"/odoo/res.partner/{partner.id}",
            "bemade_mail_signature_tour",
            login="admin",
        )
        message = self.env["mail.message"].search(
            [("model", "=", "res.partner"), ("res_id", "=", partner.id),
             ("message_type", "=", "comment")],
            order="id desc",
            limit=1,
        )
        self.assertIn("Tour hello", message.body)
        self.assertIn("o_bemade_mail_signature", message.body)
