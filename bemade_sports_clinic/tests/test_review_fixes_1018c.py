"""Owner review fixes 2026-10-18, round 2 (« 1018c », on top of
review-fixes-1018b). Synthetic fixtures only (this repository is public).

Acceptance criteria:

* C1 Player header, empty date placeholder: in the header READ view, when
  the one date that should show is empty (« Retour prévu » while the
  player is not Play OK, else « Retour réel »), a muted placeholder line
  shows instead of nothing — « Predicted return: not set » / « Actual
  return: not set » (fr_CA « Retour prévu : non défini » / « Retour réel :
  non défini »), for therapists (editable behind the pencil) and coaches
  (read-only, no pencil) alike. A set date shows as before, no placeholder.
* C2 Document picker: the shared « Category » / « Description »
  (``[data-sc-doc-shared]``) sit in ONE group (``[data-sc-doc-shared-group]``)
  the JS hides once at least one file row is listed and shows again when the
  list is emptied — same markup on the player Documents tab and the injury
  card sheet (behaviour: tour ``sc_1018b_player_documents``).
* C3 « Mon compte » like the rest of the app: no « Cancel » / « Save » in
  the cards (``data-sc-account-save`` / ``data-sc-account-cancel`` gone),
  each card has the usual « Done » (``data-sc-edit-done``) and its error box
  (``data-sc-account-errors``); every field has a save-state holder next to
  its label (``data-sc-account-state``) — each field autosaves on its own
  (behaviour: tour ``sc_1620_account``).
* C4 Relaxed mandatory fields for app-shell users only: through the core
  ``/my/address/submit`` only the name and the email are required (street,
  city, zip, country, province, phone optional — an empty phone, or a city
  without the rest of the address, is saved); an empty name or email is
  still refused. ``/my/address/country_info`` answers ``name`` / ``email``
  as the required fields for them. Shell off, or a plain portal user (no
  app role): the core rules (the whole address + phone) are unchanged.
"""
import json

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_account_security_shell_1620 import (
    SAVED_URL, AccountShellCommon)
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon
from odoo.addons.bemade_sports_clinic.tests.test_review_fixes_1018b import DocPicker1018bMixin


def _text(node):
    return ' '.join(' '.join(node.itertext()).split())


def _french(case, user):
    """fr_CA with this module's terms, on the website too (render tests)."""
    env = case.env
    lang = env['res.lang']._activate_lang('fr_CA')
    env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
    if 'website' in env:
        env['website'].sudo().search([]).write({'language_ids': [Command.link(lang.id)]})
    user.sudo().lang = 'fr_CA'
    case.opener.cookies.set('frontend_lang', 'fr_CA')


@tagged('post_install', '-at_install')
class TestReturnPlaceholder1018c(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _return(self, tree):
        nodes = tree.xpath('//*[@data-sc-section="player.hero"]//*[@data-sc-section="player.return"]')
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def _url(self):
        return '/my/player?player_id=%s' % self.player.id

    def test_placeholder_when_the_date_to_show_is_empty(self):
        cases = (
            ({'match_status': 'no', 'practice_status': 'no', 'predicted_return_date': False,
              'return_date': '2029-01-02'}, 'predicted', 'Predicted return: not set'),
            ({'match_status': 'yes', 'practice_status': 'yes', 'return_date': False,
              'predicted_return_date': '2030-01-02'}, 'actual', 'Actual return: not set'),
        )
        for login in (self._login_tp, self._login_coach):
            login()
            for vals, kind, placeholder in cases:
                self.player.sudo().write(vals)
                _t, tree = self._get(self._url())
                ret = self._return(tree)
                self.assertEqual(ret.get('data-sc-return-kind'), kind)
                empty = ret.xpath('.//*[@data-sc-return-empty]')
                self.assertEqual(len(empty), 1, (login, vals))
                self.assertEqual(empty[0].get('data-sc-return-empty'), kind)
                self.assertIn('o_sc_muted', empty[0].get('class'))
                self.assertEqual(_text(empty[0]), placeholder)
                # No value line (and not the OTHER date).
                self.assertFalse(ret.xpath('.//*[contains(@class, "o_sc_field_static")]'))
                self.assertNotIn('2029', _text(ret))
                self.assertNotIn('2030', _text(ret))

    def test_no_placeholder_when_the_date_is_set(self):
        self.player.sudo().write({'match_status': 'no', 'practice_status': 'no',
                                  'predicted_return_date': '2030-01-02'})
        self._login_coach()
        _t, tree = self._get(self._url())
        ret = self._return(tree)
        self.assertFalse(ret.xpath('.//*[@data-sc-return-empty]'))
        self.assertIn('2030', _text(ret))
        # Coaches: no pencil on the header.
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.hero"]//button[@data-sc-edit-toggle]'))

    def test_placeholder_in_french(self):
        self._login_tp()
        _french(self, self.tp)
        self.player.sudo().write({'match_status': 'no', 'practice_status': 'no',
                                  'predicted_return_date': False})
        _t, tree = self._get(self._url())
        self.assertEqual(_text(self._return(tree).xpath('.//*[@data-sc-return-empty]')[0]),
                         'Retour prévu : non défini')
        self.player.sudo().write({'match_status': 'yes', 'practice_status': 'yes', 'return_date': False})
        _t, tree = self._get(self._url())
        self.assertEqual(_text(self._return(tree).xpath('.//*[@data-sc-return-empty]')[0]),
                         'Retour réel : non défini')


@tagged('post_install', '-at_install')
class TestDocPickerSharedGroup1018c(DocPicker1018bMixin, AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_shared_fields_in_one_group_on_both_pickers(self):
        self._login_tp()
        _t, tree = self._get(self._docs_tab())
        forms = tree.xpath('//form[@data-sc-doc-upload]')
        self.assertGreaterEqual(len(forms), 2)
        for form in forms:
            group = form.xpath('.//*[@data-sc-doc-shared-group]')
            self.assertEqual(len(group), 1, form.get('data-sc-form'))
            self.assertEqual(sorted(group[0].xpath('.//*[@data-sc-doc-shared]/@data-sc-doc-shared')),
                             ['category', 'description'])
            # Owner 2026-10-18: never shown — hidden defaults only.
            self.assertEqual(group[0].get('hidden'), 'hidden')
            # The per-file rows are NOT in the group.
            self.assertFalse(group[0].xpath('.//*[@data-sc-file-proto] | .//*[@data-sc-file-list]'))


class Account1018cCommon(AccountShellCommon):

    def _card(self, tree, key):
        cards = tree.xpath('//section[@data-sc-edit-card="%s"]' % key)
        self.assertEqual(len(cards), 1, key)
        return cards[0]

    def _country_info(self, country):
        resp = self.url_open(
            '/my/address/country_info/%s' % country.id,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'id': 1,
                             'params': {'address_type': 'billing'}}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()['result']


@tagged('post_install', '-at_install')
class TestAccountAutosave1018c(Account1018cCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- C3 --------------------------------------------------------------
    def test_cards_have_done_and_no_save_or_cancel(self):
        self._login_coach()
        _t, tree = self._get('/my/account')
        self.assertFalse(tree.xpath('//*[@data-sc-account-save] | //*[@data-sc-account-cancel]'))
        for key, names in (('account-contact', {'name', 'email', 'phone'}),
                           ('account-address', {'street', 'street2', 'zip', 'city', 'country_id', 'state_id'})):
            card = self._card(tree, key)
            edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
            self.assertEqual(len(edit.xpath('.//button[@data-sc-edit-done]')), 1, key)
            self.assertFalse(edit.xpath('.//button[@type="submit"]'), key)
            self.assertTrue(edit.xpath('.//*[@data-sc-account-errors]'), key)
            # One save-state holder per field, next to its label.
            for name in names:
                field = edit.xpath('.//*[@name="%s"]' % name)[0]
                box = field.xpath('ancestor::*[contains(@class, "o_sc_account_field")][1]')[0]
                state = box.xpath('./label//*[@data-sc-account-state]')
                self.assertEqual(len(state), 1, (key, name))
                self.assertEqual(state[0].get('role'), 'status')

    # -- C4 --------------------------------------------------------------
    def test_only_name_and_email_required(self):
        self._login_coach()
        partner = self.coach.partner_id
        result = self._address_post(partner, phone='', street='', city='', zip='',
                                    country_id='', state_id='', company_name=None, vat=None)
        self.assertEqual(result, {'redirectUrl': SAVED_URL}, result)
        partner.invalidate_recordset()
        self.assertFalse(partner.phone)
        self.assertFalse(partner.street)
        self.assertFalse(partner.country_id)

    def test_partial_address_is_saved(self):
        self._login_coach()
        partner = self.coach.partner_id
        partner.sudo().write({'street': False, 'city': False, 'zip': False,
                              'state_id': False, 'country_id': False, 'phone': False})
        result = self._address_post(partner, city='Synthetic Town', company_name=None, vat=None)
        self.assertEqual(result, {'redirectUrl': SAVED_URL}, result)
        partner.invalidate_recordset()
        self.assertEqual(partner.city, 'Synthetic Town')

    def test_internal_therapist_without_address_saves_a_phone(self):
        self._login_itp()
        partner = self.itp.partner_id
        result = self._address_post(partner, phone='+1 514-555-0144', company_name=None, vat=None)
        self.assertEqual(result, {'redirectUrl': SAVED_URL}, result)
        self.assertIn('555-0144', partner.phone)

    def test_name_and_email_still_required(self):
        self._login_coach()
        partner = self.coach.partner_id
        for field in ('name', 'email'):
            result = self._address_post(partner, company_name=None, vat=None, **{field: ''})
            self.assertIn(field, result.get('invalid_fields', []), field)
            self.assertTrue(result['messages'])
        partner.invalidate_recordset()
        self.assertTrue(partner.name)
        self.assertEqual(partner.email, self.coach.login)

    def test_country_info_requires_name_and_email_only(self):
        self._login_coach()
        info = self._country_info(self.ca)
        self.assertEqual(sorted(info['required_fields']), ['email', 'name'])

    # -- C4: core behaviour kept elsewhere ---------------------------------
    def test_shell_off_keeps_core_rules(self):
        self._switch(False)
        self._login_coach()
        result = self._address_post(self.coach.partner_id, phone='', street='',
                                    company_name=None, vat=None)
        self.assertIn('street', result.get('invalid_fields', []))
        self.assertIn('phone', result.get('invalid_fields', []))
        info = self._country_info(self.ca)
        self.assertIn('street', info['required_fields'])

    def test_plain_portal_user_keeps_core_rules(self):
        self._login_plain()
        partner = self.plain.partner_id
        partner.sudo().write({'email': self.plain.login})
        result = self._address_post(partner, phone='', street='', city='Synthetic Town',
                                    company_name=None, vat=None)
        self.assertIn('street', result.get('invalid_fields', []))
        info = self._country_info(self.ca)
        self.assertIn('street', info['required_fields'])

    def test_fr_strings(self):
        self._login_coach()
        _french(self, self.coach)
        text, tree = self._get('/my/account')
        card = self._card(tree, 'account-contact')
        self.assertEqual(_text(card.xpath('.//button[@data-sc-edit-done]')[0]), 'Terminé')
