"""Task 1614 — browser tours of the inline digest history
(static/tests/tours/sc_digest_history_1614_tours.js), at phone width
(390 px) and on a laptop (1366 px), in the shell's forced dark theme.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-DT1 History → tap a date → that day's body loads IN the row (the page
  stays the list), with the « Snapshot of … » line; the player name reads
  against its card (contrast ≥ 3 — it was white on white); the player's
  details are folded and « Show details » unfolds them, readable.

The visual layout and a comparison with a prod-like copy stay UNVERIFIED
here — the dev-review click-through covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_digest_history_inline_1614 import (
    Digest1614Common,
)


class _Tours1614(Digest1614Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _run(self, login):
        self.start_tour(self.history_url, 'sc_1614_digest_history_inline', login=login)


@tagged('post_install', '-at_install')
class TestDigestHistoryToursPhone1614(_Tours1614):
    browser_size = '390x844'

    def test_therapist_phone(self):
        self._run('pc.tp@example.com')

    def test_coach_phone(self):
        self._run('pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestDigestHistoryToursLaptop1614(_Tours1614):
    browser_size = '1366x900'

    def test_therapist_laptop(self):
        self._run('pc.tp@example.com')
