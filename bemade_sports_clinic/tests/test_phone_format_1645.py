"""Task 1645 — one phone rule for every phone field (players, emergency
contacts, team staff, « Mon compte »). Synthetic numbers only (514-555-01xx,
a +44 20 7946 09xx London test range).

Acceptance criteria covered here:

* UC-1 The helper: national / international / punctuated / leading 1 /
  foreign / extension (« x123 », « poste 45 ») are formatted INTERNATIONAL
  (+1 514-555-0123); empty -> False; an invalid number -> « Invalid phone
  number. ».
* UC-2 ORM create / write of the three models format or refuse; an
  unrelated write of a record whose stored number is invalid still saves;
  imports (``import_file``) and superuser scripts are lenient (format if
  valid, keep as typed otherwise).
* UC-3 The app autosave (player phone, contact mobile): formatted value back;
  an invalid number -> 400 with the message, nothing written.
* UC-4 Forms: the shell's add-contact form re-opens with the message and the
  typed values; the new-player form (phone, EC mobile) and the legacy
  /my/player/save come back with the message; nothing is written.
* UC-5 The one-time reformat (migrations/19.0.1.102.0): counts, invalid
  untouched, idempotent; the « Phone numbers to fix » flag (players, via
  their own phone or a contact's mobile).
"""
import importlib.util
import os

from lxml import html as lxml_html

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.sc_phone import sc_normalize_phone, sc_phone_is_valid
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

MSG = 'Invalid phone number.'


def _migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.102.0', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('sc_1645_post_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestPhoneRule1645(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ca = cls.env.ref('base.ca')
        # A backend clinic admin: the rule is strict for real users (the
        # test superuser env is lenient, like a script).
        admin = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Phone Synthetic Admin', 'login': 'phone1645.admin@example.com',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('bemade_sports_clinic.group_sports_clinic_admin').id,
            ])],
        })
        cls.su_env = cls.env
        cls.env = cls.env(user=admin)
        cls.player = cls.env['sports.patient'].create({
            'first_name': 'Phone', 'last_name': 'Synthetic', 'country_id': cls.ca.id})

    # -- UC-1 ------------------------------------------------------------
    def test_helper(self):
        env = self.env
        for raw in ('514-555-0123', '+1 514-555-0123', '(514) 555.0123', '1 514 555 0123', '5145550123'):
            self.assertEqual(sc_normalize_phone(env, raw, self.ca), '+1 514-555-0123', raw)
        self.assertEqual(sc_normalize_phone(env, '+44 20 7946 0958', self.ca), '+44 20 7946 0958')
        self.assertEqual(sc_normalize_phone(env, '514-555-0123 x123', self.ca), '+1 514-555-0123 ext. 123')
        self.assertEqual(sc_normalize_phone(env, '514 555 0123 poste 45', self.ca), '+1 514-555-0123 ext. 45')
        self.assertFalse(sc_normalize_phone(env, '  ', self.ca))
        self.assertFalse(sc_normalize_phone(env, False, self.ca))
        for bad in ('12345', 'abc', '555-0100', '555-123-4567'):
            with self.assertRaises(ValidationError, msg=bad) as caught:
                sc_normalize_phone(env, bad, self.ca)
            self.assertEqual(caught.exception.args[0], MSG)
            self.assertEqual(sc_normalize_phone(env, bad, self.ca, strict=False), bad)
        self.assertTrue(sc_phone_is_valid(env, ''))
        self.assertFalse(sc_phone_is_valid(env, '12345'))

    # -- UC-2 ------------------------------------------------------------
    def test_orm_formats_and_refuses(self):
        self.player.write({'phone': '514 555 0111'})
        self.assertEqual(self.player.phone, '+1 514-555-0111')
        with self.assertRaises(ValidationError):
            self.player.write({'phone': '12345'})
        contact = self.env['sports.patient.contact'].create({
            'patient_id': self.player.id, 'name': 'Synthetic Parent', 'contact_type': 'mother',
            'mobile': '514.555.0122'})
        self.assertEqual(contact.mobile, '+1 514-555-0122')
        with self.assertRaises(ValidationError):
            contact.write({'mobile': 'abc'})
        with self.assertRaises(ValidationError):
            self.env['sports.patient.contact'].create({
                'patient_id': self.player.id, 'name': 'Synthetic Other', 'contact_type': 'other',
                'mobile': '555-0100'})
        team = self.env['sports.team'].create({'name': 'Phone Synthetic Team'})
        partner = self.env['res.partner'].create({'name': 'Synthetic Coach', 'country_id': self.ca.id})
        staff = self.env['sports.team.staff'].create({
            'team_id': team.id, 'partner_id': partner.id, 'role': 'coach', 'mobile': '5145550133'})
        self.assertEqual(staff.mobile, '+1 514-555-0133')
        with self.assertRaises(ValidationError):
            staff.write({'mobile': '999'})

    def test_unrelated_write_with_stored_invalid_number(self):
        self.player.with_context(sc_phone_lenient=True).write({'phone': '12345'})
        self.assertEqual(self.player.phone, '12345')
        self.player.write({'first_name': 'Renamed'})  # no refusal
        self.player.write({'phone': '12345', 'last_name': 'Again'})  # unchanged value
        self.assertEqual(self.player.phone, '12345')

    def test_import_and_superuser_scripts_are_lenient(self):
        importing = self.env['sports.patient.contact'].with_context(import_file=True)
        bad = importing.create({'patient_id': self.player.id, 'name': 'Imported Bad',
                                'contact_type': 'other', 'mobile': '555-0100'})
        self.assertEqual(bad.mobile, '555-0100')
        good = importing.create({'patient_id': self.player.id, 'name': 'Imported Good',
                                 'contact_type': 'other', 'mobile': '514 555 0144'})
        self.assertEqual(good.mobile, '+1 514-555-0144')
        su_env = self.su_env
        script = su_env['sports.patient.contact'].create({
            'patient_id': self.player.id, 'name': 'Script', 'contact_type': 'other', 'mobile': 'n/a'})
        self.assertEqual(script.mobile, 'n/a')

    # -- UC-5 ------------------------------------------------------------
    def test_reformat_migration_and_flag(self):
        lenient = {'sc_phone_lenient': True}
        Contact = self.env['sports.patient.contact'].with_context(**lenient)
        p_ok = self.env['sports.patient'].create({'first_name': 'Mig', 'last_name': 'Ok'})
        p_ok.with_context(**lenient).write({'phone': '+1 514-555-0150'})
        p_raw = self.env['sports.patient'].create({'first_name': 'Mig', 'last_name': 'Raw'})
        # Stored as typed before task 1645 (no rule then): raw SQL.
        self.env.cr.execute("UPDATE res_partner SET phone = %s WHERE id = %s",
                            ('514 555 0151', p_raw.partner_id.id))
        p_bad = self.env['sports.patient'].create({'first_name': 'Mig', 'last_name': 'Bad'})
        p_bad.with_context(**lenient).write({'phone': '12345'})
        c_raw = Contact.create({'patient_id': p_ok.id, 'name': 'C raw', 'contact_type': 'other'})
        self.env.cr.execute("UPDATE sports_patient_contact SET mobile = %s WHERE id = %s",
                            ('(514) 555-0152', c_raw.id))
        self.env.invalidate_all()
        c_raw._compute_sc_phone_invalid()
        p_raw._compute_sc_phone_invalid()
        c_bad = Contact.create({'patient_id': p_ok.id, 'name': 'C bad', 'contact_type': 'other',
                                'mobile': '555-0100'})
        self.assertEqual(p_raw.phone, '514 555 0151')
        self.assertTrue(p_bad.sc_phone_invalid)
        self.assertFalse(p_raw.sc_phone_invalid)
        self.assertTrue(c_bad.sc_phone_invalid)
        self.assertTrue(p_ok.sc_phone_invalid, 'a contact mobile to fix flags the player')
        flagged = self.env['sports.patient'].search([('sc_phone_invalid', '=', True)])
        self.assertIn(p_bad, flagged)
        self.assertNotIn(p_raw, flagged)

        migration = _migration()
        with mute_logger(migration.__name__):
            first = migration.reformat_phones(self.su_env)
        self.env.invalidate_all()
        self.assertEqual(p_raw.phone, '+1 514-555-0151')
        self.assertEqual(c_raw.mobile, '+1 514-555-0152')
        self.assertEqual(p_bad.phone, '12345', 'invalid left untouched')
        self.assertEqual(c_bad.mobile, '555-0100')
        self.assertGreaterEqual(first['partners (players + staff)']['reformatted'], 1)
        self.assertGreaterEqual(first['partners (players + staff)']['invalid'], 1)
        self.assertGreaterEqual(first['emergency contacts']['reformatted'], 1)
        with mute_logger(migration.__name__):
            second = migration.reformat_phones(self.su_env)
        for counts in second.values():
            self.assertEqual(counts['reformatted'], 0, 'not idempotent')


@tagged('post_install', '-at_install')
class TestPhoneRoutes1645(PlayerInlineCommon):

    def _post_form(self, url, data):
        payload = dict(data, csrf_token=self._csrf())
        return self.url_open(url, data=payload, allow_redirects=False)

    @mute_logger('odoo.http')
    def test_autosave_formats_and_refuses(self):
        self._login_tp()
        resp = self._save(self.player, 'phone', '514 555 0161')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['value'], '+1 514-555-0161')
        resp = self._save(self.contact, 'mobile', '(514) 555-0162')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['value'], '+1 514-555-0162')
        for record, field in ((self.player, 'phone'), (self.contact, 'mobile')):
            resp = self._save(record, field, '555-0100')
            self.assertEqual(resp.status_code, 400, resp.text)
            self.assertEqual(resp.json().get('message'), MSG)
            record.invalidate_recordset()
            self.assertTrue(record[field].startswith('+1 514-555-016'), record[field])

    def test_add_contact_form_comes_back_with_message(self):
        self._login_tp()
        resp = self._post_form('/my/player/contact/save', {
            'patient_id': self.player.id, 'name': 'Synthetic Typed Name',
            'contact_type': 'father', 'mobile': '555-0100', 'email': '',
            'return_url': self._url(tab='info'),
        })
        self.assertIn(resp.status_code, (302, 303))
        self.assertFalse(self.env['sports.patient.contact'].search_count(
            [('name', '=', 'Synthetic Typed Name')]))
        resp = self.url_open(resp.headers['Location'])  # follows to the info tab
        tree = lxml_html.fromstring(resp.text)
        panel = tree.xpath('//details[@id="sc_contact_add"]')[0]
        self.assertEqual(panel.get('open'), 'open')
        self.assertIn(MSG, panel.text_content())
        self.assertEqual(panel.xpath('.//input[@name="name"]/@value'), ['Synthetic Typed Name'])
        self.assertEqual(panel.xpath('.//input[@name="mobile"]/@value'), ['555-0100'])
        self.assertEqual(panel.xpath('.//input[@name="mobile"]/@inputmode'), ['tel'])
        # A valid one is stored formatted.
        self._post_form('/my/player/contact/save', {
            'patient_id': self.player.id, 'name': 'Synthetic Valid', 'contact_type': 'father',
            'mobile': '514-555-0170', 'email': '', 'return_url': self._url(tab='info')})
        contact = self.env['sports.patient.contact'].search([('name', '=', 'Synthetic Valid')])
        self.assertEqual(contact.mobile, '+1 514-555-0170')

    def test_new_player_form_refuses_invalid_numbers(self):
        self._login_tp()
        for field in ('phone', 'ec_mobile'):
            data = {'first_name': 'Synthetic', 'last_name': 'Newplayer %s' % field,
                    'team_ids': self.team_a.id, 'ec_name': 'Synthetic Parent',
                    'ec_contact_type': 'mother', field: '555-0100'}
            resp = self._post_form('/my/player/create/save', data)
            self.assertIn(resp.status_code, (302, 303))
            self.assertTrue(resp.headers['Location'].endswith('/my/player/create'), resp.headers['Location'])
            self.assertFalse(self.env['sports.patient'].search_count(
                [('last_name', '=', 'Newplayer %s' % field)]))
            text = self.url_open('/my/player/create').text
            self.assertIn(MSG, text)

    def test_legacy_player_save_refuses_invalid_phone(self):
        self._login_tp()
        self.player.write({'phone': '514-555-0180'})
        resp = self._post_form('/my/player/save', {
            'patient_id': self.player.id, 'first_name': 'Pat', 'last_name': 'One',
            'phone': '12345'})
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/my/player/edit', resp.headers['Location'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.phone, '+1 514-555-0180')
