"""Owner review fixes 2026-10-18 (second batch, /dev-review) on top of
#1606 / #1608 / #1616 / #1620. Synthetic fixtures only (this repository is
public).

Acceptance criteria:

* F1 Allergies only in the player header: the Medical card (Infos tab) has
  no allergies row in its read view and no allergies field in its edit
  view; the header keeps the allergies banner (read) and the allergies
  field behind its pencil (therapists).
* F2 One document picker: the player Documents tab and the injury card's
  « Add documents » sheet render the SAME upload component
  (``form[data-sc-doc-upload]``: drop zone with a ``multiple`` file input,
  the file list, the 10 MB error, shared « Category » / « Description »,
  the per-file row prototype); the player tab adds the optional injury
  select (this player's injuries only), the card posts its injury.
* F3 Per-document values: ``/my/patient/document/upload`` stores each
  file's own name / category / description from the parallel lists
  ``doc_file`` / ``doc_name`` / ``doc_category`` / ``doc_description``
  (position i = file i, checked against the file name); an unknown
  category (per-file or shared) refuses the whole upload
  (``error=invalid_category``, nothing saved); lists that do not line up
  fall back to the file name match, then to the shared values; the shared
  single values keep working (backwards compatibility).
* F4 « Mon compte »: no « Company » card and no company name / VAT field
  (a save keeps them as they were); « Contact details » and « Address » are
  edit cards (read view + pencil) whose edit view holds its own error box
  (round 2, 1018c: « Done », no « Save » / « Cancel » — each field
  autosaves, test_review_fixes_1018c); no page-level save button; the read
  views are read fragments.
* F5 #1608 all teams (owner decision): every user who may create events
  gets every ACTIVE team (grouped by organization) on the create form and
  on the event page's teams field (sports.team has no « active » flag
  today: every team; the search would drop archived ones if it ever gets
  one); a therapist who does not cover team X creates (and re-teams) an
  event for team X — accepted, the event exists and they can open it; an
  unknown team is refused; the
  one-organization rule still applies; a coach still cannot create; team
  READ access elsewhere is unchanged (no record rule change).
"""
import json
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_account_security_shell_1620 import (
    SAVED_URL, AccountShellCommon)
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon
from odoo.addons.bemade_sports_clinic.tests.test_event_org_team_filter_1597 import Org1597Common
from odoo.addons.bemade_sports_clinic.tests.test_injury_card_sections_1616 import InjuryCard1616Mixin


def _props(node):
    return json.loads(node.get('props'))


def _island_fields(scope):
    return [_props(node).get('field')
            for node in scope.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]')]


@tagged('post_install', '-at_install')
class TestAllergiesHeaderOnly1018b(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.player.sudo().allergies = 'Synthetic allergy'

    def test_medical_card_has_no_allergies(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=overview' % self.player.id)
        medical = tree.xpath('//section[@data-sc-edit-card="medical"]')
        self.assertEqual(len(medical), 1)
        read = medical[0].xpath('.//*[@data-sc-edit-view="read"]')[0]
        self.assertNotIn('Allergies', [' '.join(dt.itertext()).strip() for dt in read.xpath('.//dt')])
        self.assertNotIn('allergies', _island_fields(medical[0]))
        # The other medical fields stay.
        self.assertIn('return_date', _island_fields(medical[0]))

    def test_header_keeps_allergies_read_and_edit(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        banner = tree.xpath('//*[@data-sc-section="player.allergies"]')
        self.assertEqual(len(banner), 1)
        self.assertIn('Synthetic allergy', ' '.join(banner[0].itertext()))
        edit = tree.xpath('//*[@data-sc-section="player.allergies.edit"]')
        self.assertEqual(len(edit), 1)
        self.assertEqual(_island_fields(edit[0]), ['allergies'])
        # Exactly one allergies island on the whole page.
        self.assertEqual(_island_fields(tree).count('allergies'), 1)


class DocPicker1018bMixin(InjuryCard1616Mixin):

    def _docs_tab(self):
        return '/my/player?player_id=%s&tab=documents' % self.player.id

    @staticmethod
    def _shape(form):
        """The picker's structure, ids / injury left out."""
        def has(xp):
            return bool(form.xpath(xp))
        return {
            'multiple': has('.//label[@data-sc-dropzone]//input[@type="file"][@name="attachment"][@multiple]'),
            'list': has('.//ul[@data-sc-file-list]'),
            'error': has('.//*[@data-sc-file-error]'),
            'max': form.get('data-sc-max-bytes'),
            'category': has('.//select[@name="category"][@data-sc-doc-shared="category"]'),
            'description': has('.//textarea[@name="description"][@data-sc-doc-shared="description"]'),
            'proto': sorted(form.xpath('.//*[@data-sc-file-proto]//*[@disabled]/@name')),
            'submit': has('.//button[@type="submit"]'),
            'action': form.get('action'),
        }


@tagged('post_install', '-at_install')
class TestDocumentPicker1018b(DocPicker1018bMixin, AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- F2 --------------------------------------------------------------
    def test_player_tab_and_card_share_the_picker(self):
        self._login_tp()
        _text, tree = self._get(self._docs_tab())
        tab = tree.xpath('//details[@id="sc_documents_upload"]//form[@data-sc-doc-upload]')
        self.assertEqual(len(tab), 1, 'the player tab uses the shared picker')
        self.assertEqual(tab[0].get('data-sc-form'), 'player.documents.upload')
        cards = tree.xpath('//dialog[@id="sc_injury_%s_documents_add"]//form[@data-sc-doc-upload]'
                           % self.injury.id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].get('data-sc-form'), 'injury.documents.upload')
        self.assertEqual(self._shape(tab[0]), self._shape(cards[0]))
        self.assertEqual(self._shape(tab[0])['proto'],
                         ['doc_category', 'doc_description', 'doc_file', 'doc_name'])
        self.assertEqual(self._shape(tab[0])['max'], '10485760')
        # No single-file name field left on the tab.
        self.assertFalse(tab[0].xpath('.//input[@name="document_name"]'))
        # The tab: an optional injury select (this player's injuries); the
        # card: its injury, hidden.
        options = tab[0].xpath('.//select[@name="injury_id"]/option/@value')
        self.assertEqual(options[0], '')
        self.assertIn(str(self.injury.id), options)
        self.assertEqual(cards[0].xpath('.//input[@type="hidden"][@name="injury_id"]/@value'),
                         [str(self.injury.id)])
        self.assertFalse(cards[0].xpath('.//select[@name="injury_id"]'))
        # Ids stay unique on the page.
        ids = tree.xpath('//form[@data-sc-doc-upload]//*[@id]/@id')
        self.assertEqual(len(ids), len(set(ids)), ids)

    # -- F3 --------------------------------------------------------------
    def test_each_file_keeps_its_own_values(self):
        self._login_tp()
        resp = self._upload(
            [('Synthetic a.pdf', b'aaa'), ('Synthetic b.pdf', b'bbb')],
            category='other', description='Synthetic shared',
            doc_file=['Synthetic a.pdf', 'Synthetic b.pdf'],
            doc_name=['Synthetic A named', ''],
            doc_category=['medical_imaging', 'prescription'],
            doc_description=['Synthetic only a', 'Synthetic only b'])
        _path, query, _frag = self._location(resp)
        self.assertEqual(query['success'], ['documents_uploaded'])
        docs = self.env['sports.injury.document'].search([('injury_id', '=', self.injury.id)])
        got = {d.file_name: (d.name, d.category, d.description) for d in docs}
        self.assertEqual(got, {
            'Synthetic a.pdf': ('Synthetic A named', 'medical_imaging', 'Synthetic only a'),
            'Synthetic b.pdf': ('Synthetic b.pdf', 'prescription', 'Synthetic only b'),
        })

    def test_player_tab_upload_without_injury(self):
        self._login_tp()
        resp = self._upload(
            [('Synthetic c.pdf', b'ccc')], injury_id='',
            return_url=self._docs_tab(),
            doc_file=['Synthetic c.pdf'], doc_name=['Synthetic C'],
            doc_category=['prescription'], doc_description=['Synthetic c note'])
        path, query, _frag = self._location(resp)
        self.assertEqual(path, '/my/player')
        self.assertEqual(query['success'], ['document_uploaded'])
        doc = self.env['sports.injury.document'].search([('file_name', '=', 'Synthetic c.pdf')])
        self.assertEqual((doc.patient_id, doc.injury_id.id, doc.name, doc.category, doc.description),
                         (self.player, False, 'Synthetic C', 'prescription', 'Synthetic c note'))

    def test_invalid_category_refuses_everything(self):
        self._login_tp()
        resp = self._upload(
            [('Synthetic a.pdf', b'aaa'), ('Synthetic b.pdf', b'bbb')],
            doc_file=['Synthetic a.pdf', 'Synthetic b.pdf'], doc_name=['', ''],
            doc_category=['other', 'not_a_category'], doc_description=['', ''])
        _path, query, _frag = self._location(resp)
        self.assertEqual(query['error'], ['invalid_category'])
        self.assertFalse(self.env['sports.injury.document'].search([('injury_id', '=', self.injury.id)]))
        text, _tree = self._get(resp.headers['Location'].split('#')[0])
        self.assertIn('Please choose a valid category.', text)
        # The shared value is checked too.
        resp = self._upload([('Synthetic a.pdf', b'aaa')], category='nope')
        self.assertEqual(self._location(resp)[1]['error'], ['invalid_category'])

    def test_misaligned_lists_match_by_file_name_then_shared(self):
        self._login_tp()
        # Only b has a row (a browser that could not rebuild the input):
        # b gets its row, a the shared values.
        resp = self._upload(
            [('Synthetic a.pdf', b'aaa'), ('Synthetic b.pdf', b'bbb')],
            category='prescription', description='Synthetic shared',
            doc_file=['Synthetic b.pdf'], doc_name=['Synthetic B'],
            doc_category=['medical_imaging'], doc_description=['Synthetic only b'])
        self.assertEqual(self._location(resp)[1]['success'], ['documents_uploaded'])
        docs = self.env['sports.injury.document'].search([('injury_id', '=', self.injury.id)])
        got = {d.file_name: (d.name, d.category, d.description) for d in docs}
        self.assertEqual(got, {
            'Synthetic a.pdf': ('Synthetic a.pdf', 'prescription', 'Synthetic shared'),
            'Synthetic b.pdf': ('Synthetic B', 'medical_imaging', 'Synthetic only b'),
        })

    def test_fr_invalid_category_message(self):
        self._login_tp()
        self.env['res.lang']._activate_lang('fr_CA')
        self.tp.lang = 'fr_CA'
        if 'website' in self.env:
            self.env['website'].search([]).write({
                'language_ids': [Command.link(self.env.ref('base.lang_fr_CA').id)]})
            self.opener.cookies['frontend_lang'] = 'fr_CA'
        text, _tree = self._get(self._docs_tab() + '&error=invalid_category')
        self.assertIn('Veuillez choisir une catégorie valide.', text)


class AccountCards1018bCommon(AccountShellCommon):

    def _card(self, tree, key):
        cards = tree.xpath('//section[@data-sc-edit-card="%s"]' % key)
        self.assertEqual(len(cards), 1, key)
        return cards[0]


@tagged('post_install', '-at_install')
class TestAccountCards1018b(AccountCards1018bCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_no_company_card_and_no_page_save(self):
        self._login_coach()
        _text, tree = self._get('/my/account')
        self.assertFalse(tree.xpath('//*[@data-sc-section="account.company"]'))
        form = tree.xpath('//form[contains(@class, "address_autoformat")]')[0]
        names = set(form.xpath('.//input/@name | .//select/@name'))
        self.assertNotIn('company_name', names)
        self.assertNotIn('vat', names)
        self.assertFalse(tree.xpath('//*[@id="save_address"]'), 'no page-level save')
        # Core hooks the address JS needs are kept.
        self.assertTrue(tree.xpath('//*[contains(@class, "o_customer_address_fill")]//*[@id="errors"]'))
        for name in ('csrf_token', 'address_type', 'use_delivery_as_billing', 'partner_id',
                     'callback', 'required_fields', 'name', 'email', 'phone', 'street',
                     'street2', 'zip', 'city', 'country_id', 'state_id'):
            self.assertIn(name, names, name)

    def test_cards_read_view_pencil_and_own_actions(self):
        self._login_coach()
        _text, tree = self._get('/my/account')
        partner = self.coach.partner_id
        expected = {
            'account-contact': ({'name', 'email', 'phone'}, [partner.name, partner.email]),
            'account-address': ({'street', 'street2', 'zip', 'city', 'country_id', 'state_id'},
                                ['1 Synthetic Street', 'Testville', 'H0H 0H0']),
        }
        for key, (field_names, shown) in expected.items():
            card = self._card(tree, key)
            self.assertTrue(card.xpath('.//button[@data-sc-edit-toggle]'), key)
            read = card.xpath('.//*[@data-sc-edit-view="read"]')
            self.assertEqual(len(read), 1, key)
            self.assertEqual(read[0].get('data-sc-fragment'), 'res.partner:%s:%s' % (partner.id, key))
            text = ' '.join(read[0].itertext())
            for value in shown:
                self.assertIn(value, text, key)
            edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
            self.assertEqual(edit.get('hidden'), 'hidden')
            self.assertEqual(set(edit.xpath('.//input/@name | .//select/@name')), field_names, key)
            # Round 2 (1018c): no « Save » / « Cancel », a « Done ».
            self.assertTrue(edit.xpath('.//button[@data-sc-edit-done]'), key)
            self.assertTrue(edit.xpath('.//*[@data-sc-account-errors]'), key)
        # The read views show the state and country names.
        address = ' '.join(self._card(tree, 'account-address').xpath(
            './/*[@data-sc-edit-view="read"]')[0].itertext())
        self.assertIn(self.qc.name, address)
        self.assertIn(self.ca.name, address)

    def test_read_fragments_follow_a_save(self):
        self._login_coach()
        partner = self.coach.partner_id
        result = self._address_post(partner, phone='+1 514-555-0177', company_name=None, vat=None)
        self.assertEqual(result, {'redirectUrl': SAVED_URL})
        resp = self.url_open('/my/account', headers={
            'X-Sc-Fragments': 'res.partner:%s:account-contact' % partner.id})
        self.assertEqual(resp.status_code, 200)
        html = resp.json()['fragments']['res.partner:%s:account-contact' % partner.id]
        self.assertIn('555-0177', html)

    def test_save_without_company_fields_keeps_them(self):
        partner = self.coach.partner_id
        partner.sudo().write({'company_name': 'Synthetic Co', 'vat': 'SYN123'})
        self._login_coach()
        data = {k: v for k, v in {
            'csrf_token': self._csrf(), 'name': partner.name, 'email': partner.email,
            'phone': '+1 514-555-0166', 'street': partner.street, 'street2': '',
            'city': partner.city, 'zip': partner.zip, 'country_id': str(partner.country_id.id),
            'state_id': str(partner.state_id.id), 'address_type': 'billing',
            'use_delivery_as_billing': 'True', 'partner_id': str(partner.id),
            'callback': SAVED_URL, 'required_fields': 'name,email',
        }.items()}
        resp = self.url_open('/my/address/submit', data=data)
        self.assertEqual(json.loads(resp.text), {'redirectUrl': SAVED_URL})
        partner.invalidate_recordset()
        self.assertIn('555-0166', partner.phone)
        self.assertEqual((partner.company_name, partner.vat), ('Synthetic Co', 'SYN123'))


class AllTeams1608Common(Org1597Common):

    def _create(self, teams, name='SC 1018b Event', **extra):
        data = dict({
            'name': name, 'event_type': 'game',
            'team_ids': ','.join(str(t.id) for t in teams),
            'assigned_staff_ids': str(self.tp.id),
            'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00',
            'therapist_start': '2026-05-04T18:00', 'therapist_end': '2026-05-04T20:00',
        }, **extra)
        return self._post('/my/event/create/submit', data)

    def _team_keys(self, form):
        nodes = form.xpath('.//*[@data-sc-event-pick="teams"]//owl-component')
        return [opt[0] for opt in _props(nodes[0])['options']]


@tagged('post_install', '-at_install')
class TestAllTeamsForEveryone1018b(AllTeams1608Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_tp_offered_every_active_team_grouped(self):
        self._login_tp()  # staffs PC Team A only
        keys = self._team_keys(self._form())
        active = self.env['sports.team'].search([])
        self.assertEqual(sorted(keys), sorted(str(i) for i in active.ids))
        for team in (self.team_a, self.team_b, self.team_c, self.team_free):
            self.assertIn(str(team.id), keys, team.name)

    def test_tp_creates_event_for_a_team_they_do_not_cover(self):
        self._login_tp()
        self.assertNotIn(self.team_c, self.env['sports.team'].with_user(self.tp).search([]))
        resp = self._create(self.team_c)
        self.assertEqual(resp.status_code, 303, resp.text[:300])
        event = self.env['sports.event'].search([('name', '=', 'SC 1018b Event')])
        self.assertEqual(len(event), 1, resp.headers.get('Location'))
        self.assertIn('/my/event/%s' % event.id, resp.headers['Location'])
        self.assertEqual(event.team_ids, self.team_c)
        self.assertEqual(event.create_uid, self.tp)
        # They can open it afterwards (and its edit options list every team).
        text, tree = self._get('/my/event/%s' % event.id)
        self.assertIn('SC 1018b Event', text)
        props = [_props(n) for n in tree.xpath('//owl-component[@props]')
                 if _props(n).get('field') == 'team_ids' and _props(n).get('model') == 'sports.event']
        self.assertEqual(len(props), 1)
        self.assertIn(str(self.team_free.id), [opt[0] for opt in props[0]['options']])
        # Their team READ access is unchanged.
        self.assertNotIn(self.team_c, self.env['sports.team'].with_user(self.tp).search([]))

    def test_tp_re_teams_an_event_to_a_team_they_do_not_cover(self):
        self._login_tp()
        event = self.event  # PC Team A
        event.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.event/%s' % event.id, data={
            'field': 'team_ids', 'value': str(self.team_free.id), 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(event.sudo().write_date),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertTrue(resp.json()['ok'], resp.text)
        event.invalidate_recordset()
        self.assertEqual(event.sudo().team_ids, self.team_free)

    @mute_logger('odoo.http')
    def test_unknown_team_refused(self):
        self._login_tp()
        for team_ids in ('999999', '%s,999999' % self.team_a.id):
            self._post('/my/event/create/submit', {
                'name': 'SC 1018b Refused', 'event_type': 'game', 'team_ids': team_ids,
                'date_start': '2026-05-04T18:00', 'date_end': '2026-05-04T20:00'})
            self.assertFalse(self.env['sports.event'].search([('name', '=', 'SC 1018b Refused')]))
        event = self.event
        resp = self.url_open('/my/app/save/sports.event/%s' % event.id, data={
            'field': 'team_ids', 'value': '999999', 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(event.sudo().write_date),
        }, allow_redirects=False)
        self.assertFalse(resp.json().get('ok'), resp.text)
        event.invalidate_recordset()
        self.assertEqual(event.sudo().team_ids, self.team_a)

    @mute_logger('odoo.http')
    def test_one_organization_rule_still_applies(self):
        self._login_tp()
        self._create(self.team_a | self.team_c, name='SC 1018b Mixed')
        self.assertFalse(self.env['sports.event'].search([('name', '=', 'SC 1018b Mixed')]))
        text, _tree = self._get('/my/event/create')
        self.assertIn('same organization', text)

    @mute_logger('odoo.http')
    def test_coach_unchanged(self):
        self._login_coach()
        resp = self._create(self.team_a, name='SC 1018b Coach')
        self.assertNotEqual(resp.status_code, 303)
        self.assertFalse(self.env['sports.event'].search([('name', '=', 'SC 1018b Coach')]))
        resp = self.url_open('/my/event/create')
        self.assertNotEqual(resp.status_code, 200)
