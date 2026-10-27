"""Task 1666 — small polish found while documenting. Synthetic fixtures.

Acceptance criteria covered here:

* AC-1 Every clinic email subject is signed « Le Fit Crew » (no more
  « FitCrew »): the urgent-updates and morning-briefing templates, the
  event-cancelled template (en + fr_CA), and the Python-built subjects
  (briefing, urgent, cancelled fallback, deleted).
* AC-2 A cancelled event's notice reaches a fr_CA assignee as « Le Fit Crew —
  Événement annulé : … » and an English one as « Le Fit Crew — Event
  cancelled: … ».
* AC-3 The 19.0.1.107.4 migration rewrites a stale French subject on an
  existing database (an upgrade alone keeps the old translation).
* AC-4 The team page's Joueurs tab renders for a therapist, a coach and a
  clinic admin without the former search-then-create panel (removed: it
  could no longer render after #1655); the therapist and the admin get the
  inline create panel, the coach the request panel.
"""
import importlib.util
import os
from datetime import datetime

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger
from odoo.tools.translate import code_translations

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common

BRAND = 'Le Fit Crew'


def _migration():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'migrations', '19.0.1.107.4', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_107_4', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestLeFitCrewEmails1666(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        internal = env.ref('base.group_user').id
        tp = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id
        cls.staff_fr = env['res.users'].create({
            'name': 'LFC Staff FR', 'login': 'lfc.fr@example.com', 'email': 'lfc.fr@example.com',
            'lang': 'fr_CA', 'group_ids': [Command.set([internal, tp])]})
        cls.staff_en = env['res.users'].create({
            'name': 'LFC Staff EN', 'login': 'lfc.en@example.com', 'email': 'lfc.en@example.com',
            'lang': 'en_US', 'group_ids': [Command.set([internal, tp])]})
        cls.team = env['sports.team'].create({'name': 'LFC Team'})

    def test_template_subjects_signed(self):
        for xmlid in ('mail_template_urgent_summary', 'mail_template_morning_digest',
                      'mail_template_event_cancelled'):
            template = self.env.ref('bemade_sports_clinic.%s' % xmlid)
            self.assertTrue(template.subject.startswith(BRAND), (xmlid, template.subject))
            self.assertNotIn('FitCrew', template.with_context(lang='fr_CA').subject)
        cancelled = self.env.ref('bemade_sports_clinic.mail_template_event_cancelled')
        self.assertEqual(cancelled.with_context(lang='fr_CA').subject,
                         'Le Fit Crew — Événement annulé : {{ object.name }}')

    def test_python_subjects_signed(self):
        python = code_translations.get_python_translations('bemade_sports_clinic', 'fr_CA')
        self.assertEqual(python.get('Le Fit Crew — Event cancelled: %s'), 'Le Fit Crew — Événement annulé : %s')
        self.assertEqual(python.get('Le Fit Crew — Event deleted: %s'), 'Le Fit Crew — Événement supprimé : %s')
        for module in ('patient', 'res_users', 'sports_event'):
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'models', '%s.py' % module)
            with open(path, encoding='utf-8') as handle:
                self.assertNotIn('"FitCrew', handle.read(), module)

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_event')
    def test_cancel_notice_subject_per_language(self):
        event = self.env['sports.event'].create({
            'name': 'LFC Game', 'team_ids': [Command.set([self.team.id])],
            'assigned_staff_ids': [Command.set([self.staff_fr.id, self.staff_en.id])],
            'date_start': datetime(2026, 3, 5, 10, 0), 'date_end': datetime(2026, 3, 5, 12, 0),
            'state': 'confirmed'})
        event.action_cancel()
        messages = self.env['mail.message'].search([('model', '=', 'sports.event'), ('res_id', '=', event.id)])
        by_partner = {}
        for message in messages:
            for partner in message.notified_partner_ids:
                by_partner[partner] = message.subject or ''
        self.assertEqual(by_partner[self.staff_fr.partner_id], 'Le Fit Crew — Événement annulé : LFC Game')
        self.assertEqual(by_partner[self.staff_en.partner_id], 'Le Fit Crew — Event cancelled: LFC Game')

    def test_migration_rewrites_stale_french_subject(self):
        template = self.env.ref('bemade_sports_clinic.mail_template_event_cancelled')
        template.with_context(lang='fr_CA').subject = 'Événement annulé : {{ object.name }}'
        self.assertEqual(template.with_context(lang='fr_CA').subject, 'Événement annulé : {{ object.name }}')
        _migration().migrate(self.env.cr, '19.0.1.107.3')
        self.env.invalidate_all()
        self.assertEqual(template.with_context(lang='fr_CA').subject,
                         'Le Fit Crew — Événement annulé : {{ object.name }}')
        self.assertEqual(template.with_context(lang='en_US').subject,
                         'Le Fit Crew — Event cancelled: {{ object.name }}')


@tagged('post_install', '-at_install')
class TestTeamPlayersTabNoLegacyPanel1666(Parity1577Common):

    def _players_tab(self):
        resp = self.url_open('/my/team?team_id=%s&tab=players' % self.team_a.id)
        self.assertEqual(resp.status_code, 200)
        return resp.text, lxml_html.fromstring(resp.text)

    def _assert_no_legacy(self, text, tree):
        self.assertFalse(tree.xpath('//form[@data-sc-form="player.search"]'))
        self.assertNotIn('data-sc-create-hint', text)
        self.assertNotIn('data-sc-copy-from', text)
        self.assertNotIn('team.add_player.results', text)

    def test_therapist_coach_admin(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._players_tab()
        self._assert_no_legacy(text, tree)
        self.assertTrue(tree.xpath('//details[@data-sc-section="team.add_player"]//form[@data-sc-player-add]'))
        self._login_coach()
        text, tree = self._players_tab()
        self._assert_no_legacy(text, tree)
        self.assertTrue(tree.xpath('//details[@id="sc_request_add"]'))
        self.assertFalse(tree.xpath('//details[@data-sc-section="team.add_player"]'))
        self._login_cadmin()
        text, tree = self._players_tab()
        self._assert_no_legacy(text, tree)
        self.assertTrue(tree.xpath('//details[@data-sc-section="team.add_player"]//form[@data-sc-player-add]'))
