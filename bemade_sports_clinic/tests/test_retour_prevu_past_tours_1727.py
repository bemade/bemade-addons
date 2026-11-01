"""Task 1727 — « Retour prévu » in the past, in a browser (phone 390 px and
laptop 1366 px). Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_retour_prevu_past_1727_tours.js):

* AC-T1 Header: the read view shows the past date « · Dépassé »; in the
  pencil's edit view the « Retour prévu » date input has min = today; a
  past date typed anyway is refused INLINE (the message under the field,
  the typed value kept, nothing written); a date today or later then saves
  and the read view drops the flag.
* AC-T2 Proposal: a proposal whose « Retour prévu » date has passed opens
  with an EMPTY date (min = today) and its reason; « Apply » without a
  date asks for one (nothing posted); a new date applies.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class RetourPrevuPastTourCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp.write({'tz': 'UTC'})
        cls.today = fields.Date.context_today(cls.player.with_user(cls.tp))
        cls.injury.write({'diagnosis': 'Synthetic ankle'})
        cls.player.with_context(**{PAST_RETURN_OK: True}).write({
            'match_status': 'no', 'practice_status': 'no',
            'predicted_return_date': cls.today - timedelta(days=12)})

    def setUp(self):
        super().setUp()
        self._switch(True)


class RetourPrevuPastTours:

    def _url(self, **extra):
        url = '/my/player?player_id=%s&tab=injuries' % self.player.id
        return url + ''.join('&%s=%s' % kv for kv in extra.items())

    def test_header_refuses_a_past_date(self):
        self.start_tour(self._url(), 'sc_1727_header_past', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.predicted_return_date, self.today + timedelta(days=20))

    def test_proposal_asks_for_a_new_date(self):
        self.start_tour(self._url(injury=self.injury.id), 'sc_1727_proposal_past',
                        login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.injury.predicted_resolution_date, self.today - timedelta(days=2))
        self.assertEqual(self.player.predicted_return_date, self.today + timedelta(days=9))


@tagged('post_install', '-at_install')
class TestRetourPrevuPastToursPhone1727(RetourPrevuPastTours, RetourPrevuPastTourCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestRetourPrevuPastToursLaptop1727(RetourPrevuPastTours, RetourPrevuPastTourCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
