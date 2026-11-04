"""Review round 3 of #1722 / #1723 (owner UAT 2026-10-27) — « Nouvel
événement »: picking an Organisation in the type-to-search picker
sometimes did not pick it (the field kept its former value); picking it a
second time worked. Synthetic fixtures only.

Root cause: a press on a list option took the focus from the picker's box,
whose focusout closed the list 150 ms later; a click held longer than that
was released over a hidden list and lost. Not tied to the organisation
being new: the owner's first picks were the slow, deliberate ones.

Acceptance criteria:

* AC-1 An organisation picked ONCE with a held click (400 ms) sticks, from
  « All organizations » with no team chosen — and no drop warning.
* AC-2 With a team chosen: an organisation keeping it sticks with no
  warning; one that would drop it sticks and shows the #1723 warning.
* AC-3 The events list's Organisation filter (the same picker) takes a held
  click on the first try and filters the list.
* AC-4 A clinic administrator and a portal therapist; laptop and phone.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_event_org_team_filter_1597 import Org1597Common

ADMIN = 'p77.cadmin@example.com'
THERAPIST = 'pc.tp@example.com'


class _ToursR3:

    def _run(self, url, tour, login):
        self._switch(True)
        self.start_tour(url, tour, login=login)

    def test_admin_pick_no_teams(self):
        self._run('/my/event/create', 'sc_r3_org_pick_no_teams', ADMIN)

    def test_admin_pick_with_teams(self):
        self._run('/my/event/create', 'sc_r3_org_pick_with_teams', ADMIN)

    def test_admin_filters(self):
        self._run('/my/events', 'sc_r3_org_pick_filters', ADMIN)

    def test_therapist_pick_no_teams(self):
        self._staff_tp_on(self.team_c)  # already on PC Team A
        self._run('/my/event/create', 'sc_r3_org_pick_no_teams', THERAPIST)

    def test_therapist_pick_with_teams(self):
        self._staff_tp_on(self.team_c)  # already on PC Team A
        self._run('/my/event/create', 'sc_r3_org_pick_with_teams', THERAPIST)


@tagged('post_install', '-at_install')
class TestOrgPickLaptopR3(_ToursR3, Org1597Common):
    allow_inherited_tests_method = True
    browser_size = '1440x900'


@tagged('post_install', '-at_install')
class TestOrgPickPhoneR3(_ToursR3, Org1597Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'
