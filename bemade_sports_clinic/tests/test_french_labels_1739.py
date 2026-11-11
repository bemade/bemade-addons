"""Task 1739 — French labels: « soumis », the invoiced timesheet card, « EpiPen ? »,
every clinic activity a To-Do named « À faire ». Synthetic fixtures only (this
repository is public).

Acceptance criteria:

* UC-1 « Your injury report has been successfully submitted. » reads « Votre
  rapport de blessure a été soumis avec succès. » (masculine, « rapport »).
* UC-2 An invoiced timesheet card says it with its « Facturée » chip only: no
  « Invoiced (read-only) » / « Facturé (lecture seule) » line under it.
* UC-3 The EpiPen question in the allergies popup reads « EpiPen? » /
  « EpiPen ? » like the field and the gate messages (covered in
  test_epipen_gate_1717).
* UC-4 The core To-Do type reads « À faire » in French (name and default
  summary), applied by the module's data and the 19.0.1.133.0 migration;
  a customised name is kept.
* UC-5 The migration turns the open activities on the clinic's models
  (``sports.*``) whose type is not To-Do (Email, Call, none) into To-Do,
  leaves other models' activities alone, is idempotent and reports the
  per-model counts.
* UC-6 The portal create / edit activity forms have no type picker, and an
  activity created from the portal is a To-Do — even when a stale form posts
  another type.
"""
import importlib.util
import os
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.tests.test_timesheet_sent_state_1731 import (
    TimesheetSent1731Common,
)
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

MIGRATION = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'migrations', '19.0.1.133.0', 'post-migrate.py')


def _load_fr(env):
    env['res.lang']._activate_lang('fr_CA')
    env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)


@tagged('post_install', '-at_install')
class TestInjuryReportFrench1739(TransactionCase):

    def test_submitted_masculine(self):
        _load_fr(self.env)
        arch = self.env.ref('bemade_sports_clinic.portal_injury_created').with_context(
            lang='fr_CA').arch_db
        self.assertIn('Votre rapport de blessure a été soumis avec succès.', arch)
        self.assertNotIn('soumise avec succès', arch)


@tagged('post_install', '-at_install')
class TestInvoicedCard1739(TimesheetSent1731Common):

    def test_invoiced_card_chip_only(self):
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event_billed.id)
        card = self._card(tree, self.ts_billed)
        self.assertEqual(self._text(self._chip(card)), 'Billed')
        self.assertNotIn('read-only', self._text(card))
        self.assertFalse(card.xpath('./p[contains(@class, "o_pk_meta")]'))

    def test_invoiced_card_chip_only_french(self):
        _load_fr(self.env)
        if self.env['ir.module.module']._get('website').state == 'installed':
            fr_lang = self.env['res.lang']._lang_get('fr_CA')
            for website in self.env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        self.tp.write({'lang': 'fr_CA'})
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/event/%s' % self.event_billed.id)
        card = self._card(tree, self.ts_billed)
        self.assertEqual(self._text(self._chip(card)), 'Facturée')
        self.assertNotIn('lecture seule', self._text(card))


class _TodoCommon:

    def _todo(self):
        return self.env.ref('mail.mail_activity_data_todo')

    def _fr_name(self, fname='name'):
        return self._todo().with_context(lang='fr_CA')[fname]


@tagged('post_install', '-at_install')
class TestTodoFrench1739(_TodoCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('fr_CA')

    def test_renamed(self):
        todo = self._todo()
        todo.update_field_translations('name', {'fr_CA': 'To-Do'})
        todo.update_field_translations('summary', {'fr_CA': 'To-Do'})
        self.assertIn('fr_CA', self.env['mail.activity.type']._sc_set_todo_french_name())
        self.assertEqual(self._fr_name(), 'À faire')
        self.assertEqual(self._fr_name('summary'), 'À faire')
        self.assertEqual(todo.with_context(lang='en_US').name, 'To-Do')
        # Idempotent.
        self.env['mail.activity.type']._sc_set_todo_french_name()
        self.assertEqual(self._fr_name(), 'À faire')

    def test_customised_name_kept(self):
        self._todo().update_field_translations('name', {'fr_CA': 'Tâche'})
        self.env['mail.activity.type']._sc_set_todo_french_name()
        self.assertEqual(self._fr_name(), 'Tâche')

    def test_installed_by_module_data(self):
        """After install / upgrade (fr_CA active on the test DB) the name is
        « À faire » without calling anything — the module's data did it."""
        self.env['mail.activity.type']._sc_set_todo_french_name()
        self.assertEqual(self._fr_name(), 'À faire')


@tagged('post_install', '-at_install')
class TestTodoConversion1739(_TodoCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.player = env['sports.patient'].create({'first_name': 'Syn1739', 'last_name': 'Player'})
        cls.team = env['sports.team'].create({'name': 'Syn1739 Team'})
        cls.partner = env['res.partner'].create({'name': 'Syn1739 Contact'})

        def act(record, summary, type_xmlid):
            return env['mail.activity'].create({
                'res_model_id': env['ir.model']._get_id(record._name),
                'res_id': record.id,
                'summary': summary,
                'user_id': env.user.id,
                'date_deadline': fields.Date.today(),
                'activity_type_id': env.ref(type_xmlid).id if type_xmlid else False,
            })
        cls.a_email = act(cls.player, 'Syn email', 'mail.mail_activity_data_email')
        cls.a_call = act(cls.player, 'Syn call', 'mail.mail_activity_data_call')
        cls.a_none = act(cls.team, 'Syn none', None)
        cls.a_todo = act(cls.team, 'Syn todo', 'mail.mail_activity_data_todo')
        cls.a_other = act(cls.partner, 'Syn partner email', 'mail.mail_activity_data_email')

    def test_convert(self):
        counts = self.env['mail.activity']._sc_convert_clinic_activities_to_todo()
        self.assertEqual(counts.get('sports.patient'), 2)
        self.assertEqual(counts.get('sports.team'), 1)
        self.assertNotIn('res.partner', counts)
        todo = self._todo()
        for activity in self.a_email | self.a_call | self.a_none | self.a_todo:
            self.assertEqual(activity.activity_type_id, todo, activity.summary)
        self.assertEqual(self.a_other.activity_type_id, self.env.ref('mail.mail_activity_data_email'))
        # Idempotent.
        self.assertEqual(self.env['mail.activity']._sc_convert_clinic_activities_to_todo(), {})

    def test_migration_script(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self._todo().update_field_translations('name', {'fr_CA': 'To-Do'})
        spec = importlib.util.spec_from_file_location('sc_migrate_1739', MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, '_logger') as logger:
            module.migrate(self.env.cr, '19.0.1.132.0')
        self.env.invalidate_all()
        self.assertEqual(self._fr_name(), 'À faire')
        self.assertEqual(self.a_email.activity_type_id, self._todo())
        out = self._log_text(logger)
        self.assertIn('sports.patient: 2 activities converted', out)
        self.assertIn('sports.team: 1 activities converted', out)
        # Second run: nothing.
        with patch.object(module, '_logger') as logger:
            module.migrate(self.env.cr, '19.0.1.133.0')
        self.assertIn('no clinic activity to convert', self._log_text(logger))

    @staticmethod
    def _log_text(logger):
        return '\n'.join(call.args[0] % call.args[1:] for call in logger.info.call_args_list)


@tagged('post_install', '-at_install')
class TestActivityFormsNoType1739(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_forms_have_no_type_picker(self):
        self._login_tp()
        for url in ('/my/player?player_id=%s&tab=activities' % self.player.id,
                    '/my/activity/create?model=sports.patient&res_id=%s' % self.player.id):
            text, _tree = self._get(url)
            self.assertNotIn('name="activity_type_id"', text, url)
        activity = self.env['mail.activity'].search(
            [('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id)], limit=1)
        self.assertTrue(activity)
        text, _tree = self._get('/my/activity/%s' % activity.id)
        self.assertNotIn('name="activity_type_id"', text)

    def test_portal_create_is_todo(self):
        self._login_tp()
        for summary, extra in (('Syn1739 no type', {}),
                               ('Syn1739 stale email', {
                                   'activity_type_id': self.env.ref('mail.mail_activity_data_email').id})):
            self.url_open('/my/activity/save', data=dict({
                'csrf_token': self._csrf(),
                'model': 'sports.patient', 'res_id': self.player.id,
                'summary': summary, 'user_id': self.tp.id,
                'date_deadline': fields.Date.today().isoformat(),
            }, **extra))
            created = self.env['mail.activity'].search([('summary', '=', summary)])
            self.assertEqual(len(created), 1, summary)
            self.assertEqual(created.activity_type_id, self.env.ref('mail.mail_activity_data_todo'), summary)
