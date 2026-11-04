"""Task 1600 — every new string renders in French (fr_CA). Checked by
RENDER, website-aware (fr_CA on every website + the ``frontend_lang``
cookie). Synthetic fixtures only.

* UC-F1 Legacy edit form: the confirm step (« Veuillez confirmer »,
  « Corriger l'identité de ce joueur ? », « Retirer le joueur de ces
  équipes ? », « Confirmer et enregistrer », « Retour au formulaire »).
* UC-F2 The refusals: « Confirmez la correction d'identité. » (legacy flash),
  « Un autre joueur a déjà ce nom et cette date de naissance. » (model and
  clinic page), the app-shell 428 « Corriger l'identité de ce joueur ? ».
* UC-F3 The audit note « Correction d'identité confirmée par … », the
  removal-request closing « Clôturé : le joueur n'est plus dans l'équipe. »,
  the last-team toast « Le joueur ne fait plus partie d'aucune de vos
  équipes. ».
* UC-F4 The OWL field's strings are served in French (« À confirmer »,
  « La modification sera notée au dossier du joueur. », « Confirmer »,
  « Annuler »).
"""
from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestIdentityGuardI18n1600(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_c = cls.env['sports.team'].create({'name': 'PC Team C 1600', 'parent_id': cls.org.id})
        cls.env['sports.team.staff'].create({
            'team_id': cls.team_c.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })
        cls.player.write({'date_of_birth': '2008-03-04'})
        cls.other = cls.env['sports.patient'].create({
            'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': '2010-01-02'})

    def _text(self, url):
        return self._fr(url).replace('&#39;', "'")

    def test_legacy_confirm_step_in_french(self):
        self._switch(False)
        self._login_tp()
        text = self._text('/my/player/edit?patient_id=%s' % self.player.id)
        for term in ('Veuillez confirmer', "Corriger l'identité de ce joueur ?",
                     'La modification sera notée au dossier du joueur.',
                     'Retirer le joueur de ces équipes ?',
                     'Toute demande de retrait ouverte pour ce joueur est fermée.',
                     'Retour au formulaire', 'Confirmer et enregistrer'):
            self.assertIn(term, text, term)

    def test_refusals_in_french(self):
        self._switch(False)
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'first_name': 'Patrice', 'last_name': 'One', 'team_ids': str(self.team_a.id),
        }, allow_redirects=False)
        text = self._text('/my/player/edit?patient_id=%s' % self.player.id)
        self.assertIn("Confirmez la correction d'identité.", text)
        # Task 1716: Dana is on another team — the plain twin refusal (was
        # the generic « demandez à un responsable », review 2026-10-23).
        with self.assertRaisesRegex(ValidationError, 'Un autre joueur a déjà ce nom et cette date de naissance.'):
            self.player.with_user(self.tp).with_context(lang='fr_CA', sc_identity_confirmed=True).write(
                {'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': '2010-01-02'})
        # The app-shell confirmation (JSON, the user's language).
        self._switch(True)
        self.player.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'first_name', 'value': 'Patrice', 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(self.player.write_date)}, allow_redirects=False)
        self.assertEqual(resp.status_code, 428)
        self.assertEqual(resp.json()['message'], "Corriger l'identité de ce joueur ?")

    def test_clinic_duplicate_message_in_french(self):
        view = self.env.ref('bemade_sports_clinic.portal_clinic_detail').with_context(lang='fr_CA')
        self.assertIn('Un autre joueur a déjà ce nom et cette date de naissance.', view.arch)

    def test_notes_and_toast_in_french(self):
        self.player.with_user(self.tp).with_context(lang='fr_CA', sc_identity_confirmed=True).write(
            {'first_name': 'Patrice'})
        bodies = ' '.join(self.player.sudo().message_ids.mapped('body'))
        self.assertIn("Correction d'identité confirmée par PC TP", bodies)
        # Removal request closed in the assignee's (French) language.
        teamless = self.env['sports.patient'].create({
            'first_name': 'Hal', 'last_name': 'Synthetic', 'pending_removal': True})
        self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': teamless.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Player Removal Request', 'user_id': self.tp.id,
        })
        self.env['sports.patient']._sc_clear_stale_removal_flags()
        bodies = ' '.join(teamless.sudo().message_ids.mapped('body')).replace('&#39;', "'")
        self.assertIn("Clôturé : le joueur n'est plus dans l'équipe.", bodies)
        # Last team unticked: the players list carries the French toast.
        self._switch(True)
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open('/my/player/save', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'first_name': 'Patrice', 'last_name': 'One',
        }, allow_redirects=False)
        self.assertTrue(resp.headers['Location'].endswith('/my/players'), resp.headers['Location'])
        text = self._text('/my/players')
        self.assertIn("Le joueur ne fait plus partie d'aucune de vos équipes.", text)

    def test_owl_strings_served_in_french(self):
        resp = self.url_open('/web/webclient/translations?lang=fr_CA&mods=bemade_sports_clinic')
        messages = {
            m['id']: m['string']
            for m in resp.json()['modules']['bemade_sports_clinic']['messages']}
        for source, french in (('To confirm', 'À confirmer'),
                               ("The change will be noted in the player's file.",
                                'La modification sera notée au dossier du joueur.'),
                               ('Confirm', 'Confirmer'),
                               ('Cancel', 'Annuler')):
            self.assertEqual(messages.get(source), french, source)
