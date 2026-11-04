"""Task 1729 — the player header's edit rows on a phone: no overlapping
controls. Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_header_edit_phone_1729_tours.js):

* UC-H1 Phone (360 px and 390 px): in the header pencil's edit view —
  training recommendation (title + « Historique », « Effacer »),
  « Retour prévu » (with #1727's inline refusal of a past date) and
  « Retour réel » — no two visible interactive controls overlap, nothing
  overflows the screen width, every field takes the full width of its row
  and its actions (save state, « Effacer ») sit on their own line under it.
* UC-H2 Laptop (1366 px): unchanged — the training row's « Effacer » stays
  on the title's line, and still nothing overlaps.

The visual check against prod-like data stays for the dev-review
click-through.
"""
from datetime import timedelta

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.test_retour_prevu_past_tours_1727 import (
    RetourPrevuPastTourCommon,
)


class HeaderEdit1729Common(RetourPrevuPastTourCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.with_context(**{PAST_RETURN_OK: True}).write({
            'training_recommendation': 'Synthetic light jog only, no contact',
            'return_date': cls.today - timedelta(days=1),
        })

    def _url(self):
        return '/my/player?player_id=%s' % self.player.id


@tagged('post_install', '-at_install')
class TestHeaderEditPhone360_1729(HeaderEdit1729Common):
    browser_size = '360x800'

    def test_no_overlap_360(self):
        self.start_tour(self._url(), 'sc_1729_header_edit_phone', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestHeaderEditPhone390_1729(HeaderEdit1729Common):
    browser_size = '390x844'

    def test_no_overlap_390(self):
        self.start_tour(self._url(), 'sc_1729_header_edit_phone', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestHeaderEditLaptop1729(HeaderEdit1729Common):
    browser_size = '1366x768'

    def test_laptop_unchanged(self):
        self.start_tour(self._url(), 'sc_1729_header_edit_laptop', login='pc.tp@example.com')
