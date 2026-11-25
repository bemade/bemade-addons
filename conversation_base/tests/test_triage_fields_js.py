# The triage list's channel icon shares one provider-label request between
# all its rows. A list render replaced before that request answered (a
# search typed while the list was still loading) used to leave every later
# row waiting forever, so the list never showed the search. The components
# run in the browser (hoot suite static/tests/unit/channel_field.test.js);
# this case runs that suite headless and checks that its tests ran and
# passed.

import logging
import re
from functools import partial
from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser, no_retry

SUITE = "@conversation_base"
EXPECTED_TESTS = 2

# Per-test budget hoot enforces, in ms. A starved CI runner can load the
# test registry many times slower than a workstation; browser_js's own
# timeout below bounds the run as a whole.
TEST_TIMEOUT_MS = 180000
RUN_TIMEOUT_S = 1200
# How long a request the page still has in flight may take to finish after
# a failed suite, so one failure does not take the registry lock with it.
REQUEST_DRAIN_S = 600

# Hoot's dry run starts the JS modules of every installed addon. One that
# fetches at import time gets this rejection from hoot's fetch mock and may
# log it with console.error, which would fail this run before the suite
# starts. An unmocked fetch inside this suite's own tests fails that test.
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
    """Reads hoot's report off the browser log as it is written."""

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
class TestTriageFieldsJs(HttpCase):
    @no_retry
    def test_triage_fields_hoot(self):
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
        self.assertEqual(report.passed, [EXPECTED_TESTS], "the triage fields hoot suite did not run")
