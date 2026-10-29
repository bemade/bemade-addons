# Acceptance criteria (two people editing the same reply draft at once):
#   * An editor that sits idle in an open draft receives the colleague's
#     typing live, without first clicking into it.
#   * Typing while an editor catches up with a colleague's document is kept,
#     on both sides, and applied before a save.
# The editors run in the browser (hoot suite
# static/tests/unit/draft_collaboration.test.js); this case runs that suite
# headless and checks that its tests ran and passed.

import re

from odoo.tests import HttpCase, tagged

SUITE = "@conversation_draft"
EXPECTED_TESTS = 4


def _hoot_id(name):
    # Same hash as the hoot runner's job ids (see web's HOOTCommon).
    value = 0
    for char in name:
        value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
    return f"{value:08x}"


@tagged("post_install", "-at_install")
class TestDraftCollaborationJs(HttpCase):
    def test_draft_collaboration_hoot(self):
        with self.assertLogs(level="INFO") as logs:
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
