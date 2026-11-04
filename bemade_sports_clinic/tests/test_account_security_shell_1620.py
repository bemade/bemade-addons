"""Task 1620 — « Mon compte » (/my/account) and « Sécurité » (/my/security)
inside the app shell. Synthetic fixtures only.

The core portal routes keep ALL their logic (values, validation, password
change, account deletion): the addon only swaps the rendered template when
the app shell is active for the viewer.

Acceptance criteria covered here:

* UC-A1 Shell on, coach / therapist / internal therapist: ``/my/account``
  renders in the shell (no website header), back + crumb to Paramètres,
  title « My account », the core address form fields (name, email, phone,
  street, street2, zip, city, country, state — no company / VAT since
  review fixes 2026-10-18 b) prefilled, the
  core hidden inputs (csrf, address_type, required_fields) and the core
  submit contract (``form.address_autoformat`` posting to
  ``/my/address/submit`` inside ``.o_customer_address_fill`` with
  ``#errors``; each card has its « Done » and each field autosaves,
  review fixes 2026-10-18 b / 1018c),
  callback back to the page.
* UC-A2 A valid save through the core route updates the partner and sends
  the browser back to ``/my/account?sc_saved=1``, which shows the
  « saved » toast. An explicit ``redirect`` is kept (core behaviour).
* UC-A3 An invalid email is refused by the core validation (nothing saved,
  ``email`` flagged).
* UC-S1 Shell on: ``/my/security`` renders in the shell (back to
  Paramètres): the password form (old / new1 / new2 → POST /my/security),
  « Log out from all devices », the two-factor section when
  ``auth_totp_portal`` is installed (with the wizard data island the core
  JS needs), the delete-account sheet for portal users only, no API keys
  section outside debug mode.
* UC-S2 Wrong current password / mismatched confirmation / empty field:
  the shell page comes back with the core error, the password unchanged.
* UC-S3 A good change: success banner in the shell, the new password works
  and the session stays valid.
* UC-S4 Delete account with a wrong password: the shell page comes back
  with the sheet open on load and « Wrong password », the user still
  active.
* UC-O1 Shell off, or a viewer without an app role: the core templates,
  untouched (GET and POST).
* UC-F1 French render (website-aware): « Mon compte », « Sécurité » and the
  page labels.
"""
import json

from lxml import html as lxml_html

from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_user_menu_1606 import UserMenuCommon

SAVED_URL = '/my/account?sc_saved=1'


class AccountShellCommon(UserMenuCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.ca = env.ref('base.ca')
        cls.qc = env.ref('base.state_ca_qc')
        for user, phone in ((cls.coach, '+1 514-555-0101'), (cls.tp, '+1 514-555-0102')):
            user.partner_id.write({
                'email': user.login, 'street': '1 Synthetic Street', 'city': 'Testville', 'zip': 'H0H 0H0',
                'country_id': cls.ca.id, 'state_id': cls.qc.id, 'phone': phone,
            })
        cls.itp.partner_id.email = cls.itp.login

    def _form_values(self, tree):
        form = tree.xpath('//form[contains(@class, "address_autoformat")]')
        self.assertEqual(len(form), 1)
        return {el.get('name'): el.get('value') for el in form[0].xpath('.//input[@name]')}

    def _address_post(self, partner, **overrides):
        data = {
            'csrf_token': self._csrf(),
            'name': partner.name, 'email': partner.email, 'phone': partner.phone or '',
            'street': partner.street or '', 'street2': '', 'city': partner.city or '',
            'zip': partner.zip or '', 'country_id': str(partner.country_id.id or ''),
            'state_id': str(partner.state_id.id or ''), 'company_name': '', 'vat': '',
            'address_type': 'billing', 'use_delivery_as_billing': 'True',
            'partner_id': str(partner.id), 'callback': SAVED_URL,
            'required_fields': 'name,email',
        }
        data.update(overrides)
        resp = self.url_open('/my/address/submit', data=data)
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.text)

    def _security_post(self, old, new1, new2):
        resp = self.url_open('/my/security', data={
            'csrf_token': self._csrf(), 'op': 'password',
            'old': old, 'new1': new1, 'new2': new2,
        })
        self.assertEqual(resp.status_code, 200)
        return resp.text, lxml_html.fromstring(resp.text)

    def _assert_shell_sub_page_of_settings(self, tree, title):
        self.assertIsNotNone(self._shell(tree))
        self.assertFalse(tree.xpath('//header[@id="top"]'), 'website header in the shell')
        self.assertEqual(tree.xpath('//a[@data-sc-back]/@href'), ['/my/app/settings'])
        crumbs = tree.xpath('//nav[contains(@class, "o_sc_crumbs")]//a/@href')
        self.assertIn('/my/app/settings', crumbs)
        self.assertEqual(
            tree.xpath('normalize-space(//*[contains(@class, "o_sc_appbar_title_text")])'), title)


@tagged('post_install', '-at_install')
class TestAccountShell1620(AccountShellCommon):

    # -- UC-A1 -----------------------------------------------------------
    def test_account_in_the_shell_for_every_role(self):
        self._switch(True)
        for login, user in ((self._login_coach, self.coach), (self._login_tp, self.tp),
                            (self._login_itp, self.itp)):
            login()
            _text, tree = self._get('/my/account')
            self._assert_shell_sub_page_of_settings(tree, 'My account')
            # Not the core template.
            self.assertFalse(tree.xpath('//div[@name="address_div"]'))
            root = tree.xpath('//*[contains(@class, "o_customer_address_fill")]')
            self.assertEqual(len(root), 1, user.name)
            self.assertTrue(root[0].xpath('.//*[@id="errors"]'))
            form = root[0].xpath('.//form[contains(@class, "address_autoformat")]')
            self.assertEqual(len(form), 1)
            self.assertEqual(form[0].get('data-submit-url'), '/my/address/submit')
            self.assertEqual(form[0].get('action'), '/my/address/submit')
            self.assertEqual(form[0].get('method'), 'post')
            # Review fixes 2026-10-18 b: no core #save_address; no company
            # name / VAT. Round 2 (1018c): each field autosaves, each card
            # has the usual « Done ».
            self.assertFalse(form[0].xpath('.//button[@id="save_address"]'))
            self.assertEqual(len(form[0].xpath('.//button[@data-sc-edit-done]')), 2)
            names = set(form[0].xpath('.//input/@name | .//select/@name'))
            self.assertFalse({'company_name', 'vat'} & names)
            for name in ('name', 'email', 'phone', 'street', 'street2',
                         'zip', 'city', 'country_id', 'state_id', 'csrf_token',
                         'address_type', 'use_delivery_as_billing', 'partner_id',
                         'callback', 'required_fields'):
                self.assertIn(name, names, (user.name, name))
            values = self._form_values(tree)
            self.assertEqual(values['name'], user.partner_id.name)
            self.assertEqual(values['email'], user.partner_id.email)
            self.assertEqual(values['callback'], SAVED_URL)
            self.assertEqual(values['required_fields'], 'name,email')
            self.assertEqual(values['partner_id'], str(user.partner_id.id))
            # Each input sits in its own field box with its label (the core
            # address JS shows / hides / reorders the parent element).
            for name in ('street', 'zip', 'city', 'phone'):
                field = form[0].xpath('.//input[@name="%s"]' % name)[0]
                parent = field.getparent()
                self.assertTrue(parent.xpath('./label[@for="%s"]' % field.get('id')), name)
            zip_box = form[0].xpath('.//input[@name="zip"]/..')[0]
            city_box = form[0].xpath('.//input[@name="city"]/..')[0]
            self.assertIs(zip_box.getparent(), city_box.getparent())
            if user != self.itp:  # (no address on the internal therapist)
                selected = form[0].xpath('.//select[@name="country_id"]/option[@selected]/@value')
                self.assertEqual(selected, [str(self.ca.id)])
                selected = form[0].xpath('.//select[@name="state_id"]/option[@selected]/@value')
                self.assertEqual(selected, [str(self.qc.id)])
                self.assertEqual(values['phone'], user.partner_id.phone)

    # -- UC-A2 -----------------------------------------------------------
    def test_valid_save_goes_back_with_the_saved_toast(self):
        self._switch(True)
        self._login_coach()
        result = self._address_post(self.coach.partner_id, phone='+1 514-555-0199')
        self.assertEqual(result, {'redirectUrl': SAVED_URL})
        self.assertIn('555-0199', self.coach.partner_id.phone)
        _text, tree = self._get(SAVED_URL)
        toast = tree.xpath('//*[contains(@class, "o_sc_toast")]')
        self.assertEqual(len(toast), 1)
        self.assertEqual(toast[0].get('data-sc-notify'), 'Your details have been saved.')
        self.assertEqual(toast[0].get('data-sc-notify-tone'), 'success')
        # A plain visit: no toast.
        _text, tree = self._get('/my/account')
        self.assertIsNone(tree.xpath('//*[contains(@class, "o_sc_toast")]')[0].get('data-sc-notify'))

    def test_explicit_redirect_is_kept(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/account?redirect=/my/app/settings')
        self.assertEqual(self._form_values(tree)['callback'], '/my/app/settings')

    # -- UC-A3 -----------------------------------------------------------
    def test_invalid_email_is_refused(self):
        self._switch(True)
        self._login_coach()
        before = self.coach.partner_id.email
        result = self._address_post(self.coach.partner_id, email='coach@localhost')
        self.assertIn('email', result['invalid_fields'])
        self.assertTrue(result['messages'])
        self.assertEqual(self.coach.partner_id.email, before)

    # -- UC-O1 -----------------------------------------------------------
    def test_account_shell_off_is_the_core_page(self):
        self._login_coach()
        text, tree = self._get('/my/account')
        self.assertIsNone(self._shell(tree))
        self.assertNotIn('data-sc-app-shell', text)
        self.assertTrue(tree.xpath('//div[@name="address_div"]'))
        self.assertEqual(self._form_values(tree)['callback'], '/my')

    def test_account_plain_portal_user_keeps_the_core_page(self):
        self._switch(True)
        self._login_plain()
        text, tree = self._get('/my/account')
        self.assertIsNone(self._shell(tree))
        self.assertTrue(tree.xpath('//div[@name="address_div"]'))


@tagged('post_install', '-at_install')
class TestSecurityShell1620(AccountShellCommon):

    # -- UC-S1 -----------------------------------------------------------
    def test_security_in_the_shell(self):
        self._switch(True)
        totp = self.env['ir.module.module']._get('auth_totp_portal').state == 'installed'
        for login, user, portal in ((self._login_coach, self.coach, True),
                                    (self._login_tp, self.tp, True),
                                    (self._login_itp, self.itp, False)):
            login()
            _text, tree = self._get('/my/security')
            self._assert_shell_sub_page_of_settings(tree, 'Security')
            self.assertFalse(tree.xpath('//section[@name="portal_change_password"]'))
            body = tree.xpath('//*[contains(@class, "o_portal_security_body")]')
            self.assertEqual(len(body), 1, user.name)
            form = body[0].xpath('.//form[@action="/my/security"]')
            self.assertEqual(len(form), 1)
            self.assertEqual(form[0].get('method'), 'post')
            names = set(form[0].xpath('.//input/@name'))
            self.assertLessEqual({'csrf_token', 'old', 'new1', 'new2'}, names)
            self.assertEqual(form[0].xpath('.//input[@name="old"]/@autocomplete'),
                             ['current-password'])
            self.assertTrue(body[0].xpath('.//button[@id="portal_revoke_all_sessions_popup"]'))
            # Two-factor authentication: only when the core offers it.
            self.assertEqual(bool(body[0].xpath('.//*[@id="totp_wizard_view"]')), totp)
            self.assertEqual(bool(body[0].xpath('.//button[@id="auth_totp_portal_enable"]')),
                             totp)
            # The trusted-device JS needs the section right after the island.
            if totp:
                island = body[0].xpath('.//*[@id="totp_wizard_view"]')[0]
                self.assertIsNotNone(island.getnext())
            # API keys: debug mode + the system parameter only (core rule).
            self.assertFalse(body[0].xpath('.//*[contains(@class, "o_portal_new_api_key")]'))
            # Delete account: portal users only (core rule), in a sheet.
            sheet = tree.xpath('//dialog[@id="sc_deactivate_account_sheet"]')
            self.assertEqual(bool(sheet), portal, user.name)
            if portal:
                self.assertTrue(tree.xpath(
                    '//button[@data-sc-sheet-open="sc_deactivate_account_sheet"]'))
                dform = sheet[0].xpath('.//form[@action="/my/deactivate_account"]')
                self.assertEqual(len(dform), 1)
                self.assertLessEqual(
                    {'csrf_token', 'password', 'validation', 'request_blacklist'},
                    set(dform[0].xpath('.//input/@name')))
                self.assertIsNone(sheet[0].get('data-sc-sheet-open-on-load'))

    # -- UC-S2 -----------------------------------------------------------
    @mute_logger('odoo.addons.base.models.res_users', 'odoo.http')
    def test_wrong_current_password(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._security_post('not-the-password', 'pc-coach-new-1620',
                                          'pc-coach-new-1620')
        self.assertIsNotNone(self._shell(tree))
        error = tree.xpath('normalize-space(//*[@data-sc-error-for="old"])')
        self.assertIn('incorrect', error)
        self.assertEqual(tree.xpath('//input[@name="old"]/@aria-invalid'), ['true'])
        self.assertFalse(tree.xpath('//*[@data-sc-section="security.password.done"]'))
        self.authenticate('pc.coach@example.com', 'pc-coach')

    def test_mismatched_confirmation(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._security_post('pc-coach', 'pc-coach-new-1620', 'something-else')
        self.assertIsNotNone(self._shell(tree))
        error = tree.xpath('normalize-space(//*[@data-sc-error-for="new2"])')
        self.assertIn('identical', error)
        self.authenticate('pc.coach@example.com', 'pc-coach')

    def test_empty_password_field(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._security_post('pc-coach', '', '')
        error = tree.xpath('normalize-space(//*[@data-sc-error-for="new1"])')
        self.assertIn('empty', error)

    # -- UC-S3 -----------------------------------------------------------
    def test_good_password_change(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._security_post('pc-coach', 'pc-coach-new-1620', 'pc-coach-new-1620')
        self.assertIsNotNone(self._shell(tree))
        self.assertTrue(tree.xpath('//*[@data-sc-section="security.password.done"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-error-for]'))
        # The session survives the change (core updates its token).
        _text, tree = self._get('/my/security')
        self.assertIsNotNone(self._shell(tree))
        self.authenticate('pc.coach@example.com', 'pc-coach-new-1620')

    # -- UC-S4 -----------------------------------------------------------
    @mute_logger('odoo.addons.base.models.res_users', 'odoo.http')
    def test_delete_account_wrong_password_reopens_the_sheet(self):
        self._switch(True)
        self._login_coach()
        resp = self.url_open('/my/deactivate_account', data={
            'csrf_token': self._csrf(), 'validation': 'pc.coach@example.com',
            'password': 'wrong-password', 'request_blacklist': 'on',
        })
        self.assertEqual(resp.status_code, 200)
        tree = lxml_html.fromstring(resp.text)
        self.assertIsNotNone(self._shell(tree))
        sheet = tree.xpath('//dialog[@id="sc_deactivate_account_sheet"]')
        self.assertEqual(len(sheet), 1)
        self.assertEqual(sheet[0].get('data-sc-sheet-open-on-load'), '1')
        self.assertIn('Wrong password',
                      sheet[0].xpath('normalize-space(.//*[@data-sc-error-for="password"])'))
        self.assertTrue(self.coach.active)

    def test_delete_account_wrong_login(self):
        self._switch(True)
        self._login_coach()
        resp = self.url_open('/my/deactivate_account', data={
            'csrf_token': self._csrf(), 'validation': 'someone-else',
            'password': 'pc-coach',
        })
        tree = lxml_html.fromstring(resp.text)
        sheet = tree.xpath('//dialog[@id="sc_deactivate_account_sheet"]')[0]
        self.assertEqual(sheet.get('data-sc-sheet-open-on-load'), '1')
        self.assertIn('exactly', sheet.xpath('normalize-space(.//*[@data-sc-error-for="validation"])'))
        self.assertIn('pc.coach@example.com', sheet.xpath('normalize-space(.//label[@for="sc_deactivate_validation"])'))
        self.assertTrue(self.coach.active)

    # -- UC-O1 -----------------------------------------------------------
    @mute_logger('odoo.addons.base.models.res_users', 'odoo.http')
    def test_security_shell_off_is_the_core_page(self):
        self._login_coach()
        text, tree = self._get('/my/security')
        self.assertNotIn('data-sc-app-shell', text)
        self.assertTrue(tree.xpath('//section[@name="portal_change_password"]'))
        text, tree = self._security_post('not-the-password', 'x-1620-x', 'x-1620-x')
        self.assertNotIn('data-sc-app-shell', text)
        self.assertTrue(tree.xpath('//section[@name="portal_change_password"]'))
        self.assertIn('incorrect', text)

    def test_security_plain_portal_user_keeps_the_core_page(self):
        self._switch(True)
        self._login_plain()
        text, tree = self._get('/my/security')
        self.assertNotIn('data-sc-app-shell', text)
        self.assertTrue(tree.xpath('//section[@name="portal_change_password"]'))


@tagged('post_install', '-at_install')
class TestAccountSecurityFrench1620(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from odoo import Command
        env = cls.env
        fr = env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr.id)]
        cls.coach.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text.replace('&#39;', "'")

    # -- UC-F1 -----------------------------------------------------------
    def test_pages_in_french(self):
        self._switch(True)
        self._login_coach()
        text = self._fr('/my/account')
        for term in ('Mon compte', 'Paramètres', 'Coordonnées', 'Votre nom', 'Courriel',
                     'Téléphone', 'Adresse', 'Ville', 'Code postal', 'Pays',
                     'Province / État', 'Terminé'):
            self.assertIn(term, text, term)
        self.assertNotIn('Entreprise', text)
        text = self._fr('/my/security')
        for term in ('Sécurité', 'Changer le mot de passe', 'Mot de passe actuel',
                     'Nouveau mot de passe', 'Confirmer le nouveau mot de passe',
                     'Se déconnecter de tous les appareils', 'Supprimer le compte'):
            self.assertIn(term, text, term)
        if self.env['ir.module.module']._get('auth_totp_portal').state == 'installed':
            self.assertIn('Authentification à deux facteurs', text)
