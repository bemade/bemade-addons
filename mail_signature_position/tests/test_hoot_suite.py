"""Use case: the Reply All / Forward layout is checked in a real browser.

Acceptance criteria
-------------------
* This module's hoot suite (``static/tests/*.test.js``) runs headless in Chrome
  through Odoo's unit-test page (``/web/tests``), filtered on
  ``@mail_signature_position`` only, and succeeds.
* The suite itself covers Reply All and Forward with the setting ``below``
  (body identical to core: signature after the quote) and ``above`` (signature
  right after the empty typing line, before the "On ... wrote" / "Forwarded
  message" header), plus the no-signature case.
* Skipped when a module known to break hoot is installed (see
  ``HOOT_BREAKING_MODULES``): the hoot page loads the code of every installed
  module, and those fire an unmocked network request at load, which aborts the
  whole run before any of this suite's tests start.
"""

from odoo.tests import HttpCase, no_retry, tagged

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
class TestHootSuite(HttpCase):
    @no_retry
    def test_hoot_signature_position(self):
        installed = self.env["ir.module.module"].search_count(
            [("name", "in", HOOT_BREAKING_MODULES), ("state", "=", "installed")]
        )
        if installed:
            self.skipTest(
                "a module that fetches at load is installed (%s); hoot cannot run"
                % ", ".join(HOOT_BREAKING_MODULES)
            )
        job = _hoot_job_hash("@mail_signature_position")
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id={job}",
            "",
            "",
            login="admin",
            timeout=600,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=lambda message: "[HOOT]" not in message,
        )
