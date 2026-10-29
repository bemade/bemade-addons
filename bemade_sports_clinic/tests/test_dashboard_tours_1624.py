"""Task 1624 — « Configurer » the dashboard in a browser
(static/tests/tours/sc_dashboard_1624_tours.js), phone 390 px and laptop
1366 px. Synthetic fixtures only.

* TOUR-1 Open « Configurer » from the dashboard, switch a section off (saved
  as you go), move one up, add a second « Joueurs à surveiller » with a
  custom title scoped to one team (the tag picker), back on the dashboard
  check order / title / content, then « Rétablir par défaut » (confirmed).
  No horizontal scroll at either width.

The look (spacing, dark / light) stays for the dev-review click-through.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common


class _Tours1624:

    def test_configure_tour(self):
        self.start_tour('/my/home', 'sc_1624_dashboard_configure', login='pc.tp@example.com')
        # The reset ran last: the stored layout is gone.
        self.assertFalse(self.tp.sudo().sc_dashboard_layout)


@tagged('post_install', '-at_install')
class TestDashboardToursLaptop1624(_Tours1624, Dashboard1624Common):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestDashboardToursPhone1624(_Tours1624, Dashboard1624Common):
    browser_size = '390x844'
    allow_inherited_tests_method = True
