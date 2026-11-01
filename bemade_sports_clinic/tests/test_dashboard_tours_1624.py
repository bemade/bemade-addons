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

* TOUR-3 (owner UAT round 2, 2026-10-29; phone 390 px and laptop 1440 px)
  « Cliniques aujourd'hui » does not touch the first event card; expanding
  and collapsing « Activités en retard » (10 cards), its « Voir les N
  autres » and an event's « Détails » keeps the toggle's top within 2 px;
  the quick « Retour prévu » of « Retours dépassés » drops « Dépassé » and
  the count follows; « Suivre » from « Joueurs à surveiller » adds the card
  to « Joueurs que je suis », « Ne plus suivre » removes it — no reload.

* TOUR-4 (round 2, zones) laptop 1440 px: « Configurer » shows left and
  right side by side, bottom under both; drag « Aujourd'hui » left → right
  → bottom (saved by fetch, no reload); after a reload it is still in the
  bottom zone, and the dashboard renders it full width under the columns.
* TOUR-5 (round 2, zones) phone 390 px: the zones stacked; « Déplacer
  vers : Gauche » (no reload), ▲ within the zone; the dashboard reads
  left, right, bottom in one column. Then « Rétablir par défaut » (model)
  gives the default zones back.

The look (spacing, dark / light) stays for the dev-review click-through.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
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


class _Round2Tour1624:

    def test_round2_tour(self):
        env = self.env
        model = env['ir.model']._get('sports.patient').id
        today = fields.Date.context_today(self.tp)
        env['mail.activity'].create([{
            'res_model_id': model, 'res_id': self.red.id, 'user_id': self.tp.id,
            'summary': 'Synthetic overdue %s' % n, 'date_deadline': today - timedelta(days=1)}
            for n in range(10)])
        # Two overdue returns (the quick edit takes one: 2 -> 1).
        (self.red | self.shared).sudo().with_context(**{PAST_RETURN_OK: True}).write(
            {'predicted_return_date': today - timedelta(days=4)})
        # A long « Couvertures à venir » under « À faire » (a page to scroll).
        now = fields.Datetime.now()
        env['sports.event'].create([{
            'name': 'DB Soon %s' % n, 'event_type': 'practice',
            'date_start': now + timedelta(days=1, hours=n), 'date_end': now + timedelta(days=1, hours=n + 1),
            'team_ids': [Command.set(self.team_a.ids)],
            'assigned_staff_ids': [Command.set(self.tp.ids)], 'state': 'confirmed'} for n in range(6)])
        self._dash(self.tp)._sc_layout_update(
            'watch', settings={'level': 'red', 'scope_team_ids': self.team_a.ids})
        self.start_tour('/my/home', 'sc_1624_dashboard_round2', login='pc.tp@example.com')
        self.assertFalse(self.tp.sudo().sc_followed_patient_ids)
        self.assertEqual(len((self.red | self.shared).filtered('predicted_return_overdue')), 1)


@tagged('post_install', '-at_install')
class TestDashboardRound2TourLaptop1624(_Round2Tour1624, Dashboard1624Common):
    browser_size = '1440x900'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestDashboardRound2TourPhone1624(_Round2Tour1624, Dashboard1624Common):
    browser_size = '390x844'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestDashboardZonesTourLaptop1624(Dashboard1624Common):
    browser_size = '1440x900'

    def test_zones_drag_and_drop(self):
        self.start_tour('/my/app/dashboard/configure', 'sc_1624_zones_dnd', login='pc.tp@example.com')
        today = self._instance(self.tp, 'today')
        self.assertEqual(today['zone'], 'bottom')
        self.assertEqual(self.tp.sudo().sc_dashboard_layout['v'], 2)


@tagged('post_install', '-at_install')
class TestDashboardZonesTourPhone1624(Dashboard1624Common):
    browser_size = '390x844'

    def test_zones_move_control(self):
        self.start_tour('/my/app/dashboard/configure', 'sc_1624_zones_move', login='pc.tp@example.com')
        left = [i['id'] for i in self._dash(self.tp)._sc_layout() if i['zone'] == 'left']
        self.assertEqual(left, ['today', 'todo', 'coverage', 'indicators', 'missing_timesheets'])
        # « Rétablir par défaut »: the default zones again.
        self._dash(self.tp)._sc_layout_reset()
        self.assertEqual(self._instance(self.tp, 'indicators')['zone'], 'right')
