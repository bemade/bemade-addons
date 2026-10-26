"""Task 1678 — messages & French polish (owner-approved 2026-10-25).
Synthetic fixtures only.

Acceptance criteria:

* AC-1 Routing: a removal request stores the team it is about
  (``pending_removal_team_id``); the cron gives the To-Do to that team's
  head therapist (with a user), else a therapist of that team, else the
  superuser. A request stored without a team (older rows) falls back to
  the player's first team; a stored team the player has left too. The
  official removal clears the stored team with the flag.
* AC-2 Wording: the coach's confirmation says the request goes to the
  team's head therapist — in French « … sera traitée par le thérapeute en
  chef de l'équipe. » (website-aware render).
* AC-3 Toasts: the title sits above the text (one column), the action
  button beside it — at 360 px, 390 px and laptop width (tours).
* AC-4 French labels: « Couverture » on the event page (its own term, not
  the generic « Thérapeute »), « Commentaire (facultatif) » on the activity
  « Done » sheet, « Personnel assigné » (typo fixed), and the digest
  template's French body says « Annonce d'équipe » (migration reloads the
  terms with overwrite).
"""
from datetime import datetime, timedelta

from odoo import SUPERUSER_ID, Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestRemovalRouting1678(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        org = env['res.partner'].create({'name': 'RR Org 1678', 'is_company': True})
        cls.team_a = env['sports.team'].create({'name': 'RR Team A', 'parent_id': org.id})
        cls.team_b = env['sports.team'].create({'name': 'RR Team B', 'parent_id': org.id})
        Users = env['res.users'].with_context(no_reset_password=True)
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        portal = env.ref('base.group_portal').id

        def _tp(login):
            return Users.create({'name': login, 'login': login,
                                 'group_ids': [Command.set([portal, tp_g])]})
        cls.head_a = _tp('rr.head.a.1678')
        cls.head_b = _tp('rr.head.b.1678')
        cls.ther_b = _tp('rr.ther.b.1678')
        Staff = env['sports.team.staff']
        Staff.create({'team_id': cls.team_a.id, 'partner_id': cls.head_a.partner_id.id,
                      'role': 'head_therapist'})
        cls.head_b_line = Staff.create({'team_id': cls.team_b.id, 'partner_id': cls.head_b.partner_id.id,
                                        'role': 'head_therapist'})
        cls.ther_b_line = Staff.create({'team_id': cls.team_b.id, 'partner_id': cls.ther_b.partner_id.id,
                                        'role': 'therapist'})
        cls.player = env['sports.patient'].create({'first_name': 'Rr', 'last_name': 'Player1678'})
        cls.player.team_ids = [Command.set([cls.team_a.id, cls.team_b.id])]

    def _todo(self):
        self.env['sports.patient']._cron_handle_pending_removals()
        return self.env['mail.activity'].search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id),
            ('summary', '=', 'Player Removal Request')])

    def test_request_stores_team_and_routes_to_its_head(self):
        self.player._request_team_removal(self.team_b.id, reason='Synthetic reason')
        self.assertTrue(self.player.pending_removal)
        self.assertEqual(self.player.pending_removal_team_id, self.team_b)
        self.assertEqual(self._todo().user_id, self.head_b)

    def test_fallback_therapist_of_that_team(self):
        self.head_b_line.unlink()
        self.player._request_team_removal(self.team_b.id)
        self.assertEqual(self._todo().user_id, self.ther_b)

    def test_fallback_superuser(self):
        (self.head_b_line | self.ther_b_line).unlink()
        self.player._request_team_removal(self.team_b.id)
        self.assertEqual(self._todo().user_id.id, SUPERUSER_ID)

    def test_old_row_without_team_uses_first_team(self):
        self.player.write({'pending_removal': True, 'pending_removal_team_id': False})
        self.assertEqual(self._todo().user_id, self.player.team_ids[0].staff_ids.filtered(
            lambda s: s.role == 'head_therapist').user_ids[:1])

    def test_stored_team_left_falls_back(self):
        self.player._request_team_removal(self.team_b.id)
        self.player.write({'team_ids': [Command.unlink(self.team_b.id)]})
        self.assertEqual(self._todo().user_id, self.head_a)

    def test_official_removal_clears_team(self):
        self.player._request_team_removal(self.team_b.id)
        self.player.remove_from_team(self.team_b.id)
        self.assertFalse(self.player.pending_removal)
        self.assertFalse(self.player.pending_removal_team_id)


@tagged('post_install', '-at_install')
class TestMessagesFrench1678(TestAppShellI18n1538):

    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_removal_request_toast_in_french(self):
        self._switch(True)
        self._login_coach()
        resp = self.url_open('/my/team/%s/player/%s/request_removal' % (self.team_a.id, self.player.id),
                             data={'csrf_token': self._csrf(), 'reason': 'Synthetic reason'},
                             allow_redirects=False)
        self.assertEqual(resp.status_code, 303, resp.text[:300])
        self.assertTrue(self.player.pending_removal)
        self.assertEqual(self.player.pending_removal_team_id, self.team_a)
        text = self._fr('/my/team/%s' % self.team_a.id).replace('&#39;', "'")
        self.assertIn("a été soumise et sera traitée par le thérapeute en chef de l'équipe.", text)
        self.assertNotIn('administrateur', text)

    def test_event_coverage_label_in_french(self):
        self._switch(True)
        start = datetime(2026, 2, 2, 9, 30)
        self.event.sudo().write({'therapist_start': start, 'therapist_end': start + timedelta(hours=3)})
        self._login_tp()
        text = self._fr('/my/event/%s' % self.event.id)
        self.assertIn('<dt>Couverture</dt>', text)

    def test_activity_comment_label_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/activities')
        self.assertIn('Commentaire (facultatif)', text)
        self.assertNotIn('Feedback (optionnel)', text)

    def test_view_terms_in_french(self):
        View = self.env['ir.ui.view'].with_context(lang='fr_CA')
        detail = View.env.ref('bemade_sports_clinic.portal_event_detail')
        self.assertIn('Personnel assigné', detail.arch)
        self.assertNotIn('Personnnel', detail.arch)

    def test_digest_template_french_body(self):
        template = self.env.ref('bemade_sports_clinic.mail_template_morning_digest')
        body = template.with_context(lang='fr_CA').body_html
        self.assertIn("Annonce d'équipe / Team announcement", body)
        self.assertNotIn("Annonce de l'équipe", body)


@tagged('post_install', '-at_install')
class TestToastLayoutPhone1678(AppShellCommon):
    browser_size = '390x844'

    def test_toast_stacked(self):
        self._switch(True)
        self.start_tour('/my/home', 'sc_1678_toast_stacked', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestToastLayoutSmall1678(TestToastLayoutPhone1678):
    browser_size = '360x740'


@tagged('post_install', '-at_install')
class TestToastLayoutLaptop1678(TestToastLayoutPhone1678):
    browser_size = '1366x768'
