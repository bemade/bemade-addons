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

import logging
import re
from functools import partial
from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser, no_retry

SUITE = "@conversation_draft"
EXPECTED_TESTS = 8

# Per-test budget hoot enforces, in ms of wall-clock time. The suite takes
# about a second on a workstation, but a CI runner can be starved to where the
# same registry loads 20 times slower. Every test starts with the mock server
# fetching the mail models' definitions from the real server
# (POST /web/model/get_definitions, ~1 s here), so at Odoo's default of 15 s
# the first test times out there and the suite fails with nothing wrong.
# browser_js's own timeout below bounds the run as a whole.
TEST_TIMEOUT_MS = 180000
RUN_TIMEOUT_S = 1200
# How long a request the page still has in flight may take to finish after
# the suite failed. Each timed-out test leaves its get_definitions request
# running; browser_js then waits only 60 s for the registry lock and exits
# the whole test run when it cannot get it back, which turns one failed suite
# into an error for every HttpCase after it.
REQUEST_DRAIN_S = 600

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


class _HootReport(logging.Handler):
    """Reads hoot's report off the browser log as it is written.

    A plain handler on the test's logger: the log keeps flowing to the
    console and the CI trace, which is where a failed hoot assertion is
    described. (``assertLogs`` would replace the root handlers and silence
    everything the browser says, including the reason the suite failed.)
    """

    def __init__(self):
        super().__init__()
        self.passed = []
        self.failed_tests = []

    def emit(self, record):
        message = record.getMessage()
        if match := re.search(r"Passed (\d+) tests", message):
            self.passed.append(int(match[1]))
        if match := re.search(r'\[HOOT\] Test "([^"]+)" failed', message):
            self.failed_tests.append(match[1])


@tagged("post_install", "-at_install")
class TestDraftCollaborationJs(HttpCase):
    @no_retry
    def test_draft_collaboration_hoot(self):
        report = _HootReport()
        self._logger.addHandler(report)
        self.addCleanup(self._logger.removeHandler, report)
        with (
            patch.object(ChromeBrowser, "_handle_console", _handle_console_ignoring_import_fetches),
            patch.object(
                self,
                "_wait_remaining_requests",
                partial(self._wait_remaining_requests, timeout=REQUEST_DRAIN_S),
            ),
        ):
            try:
                self.browser_js(
                    f"/web/tests?headless&loglevel=2&preset=desktop&timeout={TEST_TIMEOUT_MS}"
                    f"&id={_hoot_id(SUITE)}",
                    "",
                    "",
                    login="admin",
                    timeout=RUN_TIMEOUT_S,
                    success_signal="[HOOT] Test suite succeeded",
                    error_checker=lambda message: "[HOOT]" not in message,
                )
            except AssertionError as error:
                if report.failed_tests:
                    raise AssertionError(
                        "hoot tests failed (details above in the browser log): "
                        + "; ".join(report.failed_tests)
                    ) from error
                raise
        self.assertEqual(report.passed, [EXPECTED_TESTS], "the draft hoot suite did not run")
