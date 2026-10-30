# Acceptance criteria (two people editing the same reply draft at once):
#   * An editor that sits idle in an open draft receives the colleague's
#     typing live, without first clicking into it.
#   * Typing while an editor catches up with a colleague's document is kept,
#     on both sides, and applied before a save.
#   * Two people typing at the same moment both keep their text, each in one
#     piece and in order, and each caret stays with its own text.
# The editors run in the browser (hoot suite
# static/tests/unit/draft_collaboration.test.js); this case runs that suite
# headless and checks that its tests ran and passed.

import re
from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser

SUITE = "@conversation_draft"
EXPECTED_TESTS = 8

# Hoot's dry run starts the JS modules of EVERY installed addon, not only this
# suite's dependencies. An addon that fetches at import time gets this
# rejection from hoot's fetch mock and may log it with console.error, which
# would fail this run before the suite starts. An unmocked fetch inside one of
# this suite's own tests throws in that test instead, so the suite fails on its
# own result and the passed-count check below.
UNMOCKED_FETCH = "cannot make a request when fetch is not mocked"
_handle_console = ChromeBrowser._handle_console


def _handle_console_ignoring_import_fetches(browser, type, args=None, **kwargs):  # pylint: disable=redefined-builtin
    if type == "error" and args:
        text = " ".join(str(browser._from_remoteobject(arg)) for arg in args)
        if UNMOCKED_FETCH in text and "[HOOT]" not in text:
            type = "warning"
    return _handle_console(browser, type, args, **kwargs)


def _hoot_id(name):
    # Same hash as the hoot runner's job ids (see web's HOOTCommon).
    value = 0
    for char in name:
        value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
    return f"{value:08x}"


@tagged("post_install", "-at_install")
class TestDraftCollaborationJs(HttpCase):
    def test_draft_collaboration_hoot(self):
        with (
            patch.object(ChromeBrowser, "_handle_console", _handle_console_ignoring_import_fetches),
            self.assertLogs(level="INFO") as logs,
        ):
            self.browser_js(
                "/web/tests?headless&loglevel=2&preset=desktop&timeout=15000"
                f"&id={_hoot_id(SUITE)}",
                "",
                "",
                login="admin",
                timeout=600,
                success_signal="[HOOT] Test suite succeeded",
                error_checker=lambda message: "[HOOT]" not in message,
            )
        passed = [
            int(match[1])
            for line in logs.output
            if (match := re.search(r"Passed (\d+) tests", line))
        ]
        self.assertEqual(passed, [EXPECTED_TESTS], "the draft hoot suite did not run")
