"""Task 1624 — « Configurer » the dashboard in a browser
(static/tests/tours/sc_dashboard_1624_tours.js), phone 390 px and laptop
1366 px. Synthetic fixtures only.

* TOUR-1 Open « Configurer » from the dashboard, switch a section off (saved
  as you go), move one up, add a second « Joueurs à surveiller » with a
  custom title scoped to one team (the tag picker), back on the dashboard
  check order / title / content, then « Rétablir par défaut » (confirmed).
  No horizontal scroll at either width.

* TOUR-2 (owner UAT round 1, 2026-10-29) « Suivre » a player from its
  card's « Details » (fetch, no reload); open « Activités en retard » into
  its activity cards and their « Reprogrammer » sheet; fold out an event's
  « Details »; « Ajouter ma feuille de temps » on « Feuilles de temps
  manquantes » opens the event page with the add sheet open.

The look (spacing, dark / light) stays for the dev-review click-through.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common


class _Tours1624:

    def test_configure_tour(self):
        self.start_tour('/my/home', 'sc_1624_dashboard_configure', login='pc.tp@example.com')
        # The reset ran last: the stored layout is gone.
        self.assertFalse(self.tp.sudo().sc_dashboard_layout)

    def test_round1_tour(self):
        env = self.env
        env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('sports.patient').id, 'res_id': self.red.id,
            'user_id': self.tp.id, 'summary': 'Synthetic overdue chore',
            'date_deadline': fields.Date.context_today(self.tp) - timedelta(days=2)})
        start = fields.Datetime.now() - timedelta(days=3)
        missing = env['sports.event'].create({
            'name': 'DB Missing Tour', 'event_type': 'game',
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'team_ids': [Command.set(self.team_a.ids)],
            'assigned_staff_ids': [Command.set(self.tp.ids)], 'state': 'confirmed'})
        # Only Red in « Joueurs à surveiller »: the card the tour opens.
        self._dash(self.tp)._sc_layout_update(
            'watch', settings={'level': 'red', 'scope_team_ids': self.team_a.ids})
        self.shared.write({'team_ids': [Command.set(self.team_c.ids)]})
        self.start_tour('/my/home', 'sc_1624_dashboard_round1', login='pc.tp@example.com')
        self.assertEqual(self.tp.sudo().sc_followed_patient_ids, self.red)
        self.assertTrue(missing.exists())


@tagged('post_install', '-at_install')
class TestDashboardToursLaptop1624(_Tours1624, Dashboard1624Common):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestDashboardToursPhone1624(_Tours1624, Dashboard1624Common):
    browser_size = '390x844'
    allow_inherited_tests_method = True
