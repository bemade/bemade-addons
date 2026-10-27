"""Task 1661 — fr_CA gaps and inconsistencies in the app. Synthetic fixtures.

Acceptance criteria covered here (render-checked, website-aware via the 1538
base: fr_CA added to every website's languages + the ``frontend_lang``
cookie when ``website`` is installed):

* AC-1 Injury statuses are feminine: « Non vérifiée / Active / Résolue » (the
  selection labels every pill, chip and filter renders from).
* AC-2 The proposal sheet reads « Appliquer » / « Ignorer » (no more
  « Annuler », which stays for undo / cancel).
* AC-3 The events segment reads « Passés »; past clinics keep « Passées ».
* AC-4 The timesheet list column reads « Statut » (not « Étape »).
* AC-5 The role label « Doctor » is « Médecin » (code + selection labels).
* AC-6 The « Verify injury » To-Do summary is translated in the assignee's
  language (« Vérifier la blessure ») and the lookups still find it; the
  English marker keeps working for To-Dos created before.
* AC-7 The /my/players Match / Practice filter options render the field's
  TRANSLATED selection (« Oui / Non / Oui, sans contact »).
* AC-8 The install page iPhone steps say « Safari ou Chrome ».
* AC-9 The backend « Admin » menu is « Administration »; « Therapist End » is
  « Fin de la couverture » on the event page; « Assigned Staff » is
  « Personnel assigné ».
"""
from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.translate import code_translations

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestFrCaGaps1661(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def _fr_text(self, url):
        return self._fr(url).replace('&#39;', "'")

    # -- AC-1 ----------------------------------------------------------------
    def test_injury_stage_labels_feminine(self):
        Injury = self.env['sports.patient.injury'].with_context(lang='fr_CA')
        labels = dict(Injury._fields['stage']._description_selection(Injury.env))
        self.assertEqual(labels, {
            'unverified': 'Non vérifiée', 'active': 'Active', 'resolved': 'Résolue'})
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/player?player_id=%s' % self.player.id)
        tree = lxml_html.fromstring(text)
        pill_texts = ' '.join(' '.join(n.itertext()) for n in tree.xpath(
            '//*[@data-sc-pill-field="stage" or contains(@class, "o_sc_status_pill")]'))
        self.assertIn('Active', pill_texts)
        self.assertNotIn('Actif', pill_texts)

    # -- AC-2 ----------------------------------------------------------------
    def test_proposal_sheet_ignorer(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr_text('/my/home'))
        dismiss = tree.xpath('//button[@data-sc-proposal-dismiss]')
        apply_ = tree.xpath('//button[@data-sc-proposal-apply]')
        self.assertTrue(dismiss and apply_)
        self.assertEqual(dismiss[0].text_content().strip(), 'Ignorer')
        self.assertEqual(apply_[0].text_content().strip(), 'Appliquer')

    # -- AC-3 ----------------------------------------------------------------
    def test_events_past_segment_masculine(self):
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/events')
        self.assertIn('Passés', text)
        self.assertNotIn('>Passées<', text)
        python = code_translations.get_python_translations('bemade_sports_clinic', 'fr_CA')
        self.assertEqual(python.get('Past'), 'Passés')
        self.assertEqual(python.get('Earlier'), 'Passées')

    # -- AC-4 ----------------------------------------------------------------
    def test_timesheets_status_column(self):
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/sc/timesheets')
        self.assertIn('Statut', text)
        self.assertNotIn('Étape', text)

    # -- AC-5 ----------------------------------------------------------------
    def test_doctor_is_medecin(self):
        python = code_translations.get_python_translations('bemade_sports_clinic', 'fr_CA')
        self.assertEqual(python.get('Doctor'), 'Médecin')
        Staff = self.env['sports.team.staff'].with_context(lang='fr_CA')
        roles = dict(Staff._fields['role']._description_selection(Staff.env))
        self.assertEqual(roles['doctor'], 'Médecin')
        Event = self.env['sports.event'].with_context(lang='fr_CA')
        kinds = dict(Event._fields['event_type']._description_selection(Event.env))
        self.assertEqual(kinds['training'], 'Entraînement')

    # -- AC-6 ----------------------------------------------------------------
    def test_verify_injury_todo_translated(self):
        python = code_translations.get_python_translations('bemade_sports_clinic', 'fr_CA')
        self.assertEqual(python.get('Verify injury'), 'Vérifier la blessure')
        head = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'G1661 Head TP', 'login': 'g1661.head@example.com', 'lang': 'fr_CA',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id])],
        })
        team = self.env['sports.team'].create({'name': 'G1661 Team'})
        self.env['sports.team.staff'].create({
            'team_id': team.id, 'partner_id': head.partner_id.id, 'role': 'head_therapist'})
        player = self.env['sports.patient'].create({
            'first_name': 'Gap', 'last_name': 'Synthetic', 'team_ids': [Command.set([team.id])]})
        injury = self.env['sports.patient.injury'].create({
            'patient_id': player.id, 'diagnosis': 'Synthetic strain'})
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        todo = self.env['mail.activity'].search(injury._verify_activity_domain())
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo.user_id, head)
        self.assertTrue(todo.summary.endswith('Vérifier la blessure'), todo.summary)
        self.assertIn('[Blessure', todo.summary)
        # Idempotent: the French summary is found again, no duplicate.
        self.env['sports.patient.injury']._cron_create_injury_verification_tasks()
        self.assertEqual(self.env['mail.activity'].search_count(injury._verify_activity_domain()), 1)
        # A legacy English To-Do still matches the lookup.
        todo.summary = '[Injury: Synthetic strain] Verify injury'
        self.assertEqual(self.env['mail.activity'].search_count(injury._verify_activity_domain()), 1)

    # -- AC-7 ----------------------------------------------------------------
    def test_players_match_practice_filters_translated(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr_text('/my/players'))
        practice = [o.text_content().strip() for o in tree.xpath(
            '//select[@id="sc_players_practice"]/option[@value]') if o.get('value')]
        match = [o.text_content().strip() for o in tree.xpath(
            '//select[@id="sc_players_match"]/option[@value]') if o.get('value')]
        self.assertEqual(sorted(practice), sorted(['Oui', 'Oui, sans contact', 'Non']))
        self.assertEqual(sorted(match), sorted(['Oui', 'Non']))

    # -- AC-8 ----------------------------------------------------------------
    def test_install_page_safari_or_chrome(self):
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/app/install')
        for term in ('iPhone et iPad (Safari ou Chrome)',
                     'Ouvrez cette page dans Safari ou Chrome.',
                     "dans la barre d'adresse (Chrome)"):
            self.assertIn(term, text, term)

    # -- AC-9 ----------------------------------------------------------------
    def test_backend_and_event_labels(self):
        menu = self.env.ref('bemade_sports_clinic.sports_clinic_staff_menu').with_context(lang='fr_CA')
        self.assertEqual(menu.name, 'Administration')
        self.env.cr.execute(
            "SELECT arch_db->>'fr_CA' FROM ir_ui_view WHERE key = %s",
            ['bemade_sports_clinic.sc_app_event'])
        arch_fr = self.env.cr.fetchone()[0]
        for term in ('Début de la couverture', 'Fin de la couverture', 'Personnel assigné'):
            self.assertIn(term, arch_fr, term)
        self.assertNotIn('Fin du thérapeute', arch_fr)
        self.assertNotIn('Therapist End', arch_fr)
        # A real render too: the event page in French.
        self.event.sudo().write({
            'therapist_start': fields.Datetime.to_datetime('2026-02-02 09:30:00'),
            'therapist_end': fields.Datetime.to_datetime('2026-02-02 12:30:00'),
        })
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/event/%s' % self.event.id)
        self.assertIn('Fin de la couverture', text)
        self.assertNotIn('Fin du thérapeute', text)
