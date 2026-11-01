"""Task 1585 — tap-to-call / tap-to-email in the app shell. Synthetic
fixtures only (invented names, 555 numbers, example.com addresses).

Acceptance criteria:

* UC-T1 Player Contact Information card: the email reads as a ``mailto:``
  link and the phone as a ``tel:`` link (the href keeps only ``+`` and the
  digits); each link carries the ``data-sc-display`` hook (a pencil save
  updates its text) and ``data-sc-display-href`` (the kind, so the save
  updates the href too — browser half: the ``sc_1585_tap_links`` tour).
* UC-T2 Emergency contact cards: the mobile is a ``tel:`` link, the email a
  ``mailto:`` link, same hooks.
* UC-T3 An empty phone / email reads « — » and is NOT a link (no href).
* UC-T4 Event page: each assigned staff member's email and the
  organization's email are ``mailto:`` links (staff without an email: the
  name only).
* UC-T5 The href helper: ``tel:`` keeps ``+`` and digits only, ``mailto:``
  keeps the address; empty / digit-less → no href.
* UC-T6 Switch off: the legacy pages are untouched (no shell link hooks).
* UC-T7 fr_CA (website-aware): the restructured rows keep their French
  labels (« Courriel », « Téléphone », « Cellulaire », « Organisation »).
"""
from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.app_shell import sc_contact_href
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class TapLinksCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Task 1645: raw 555 numbers (not dialable) kept as typed — lenient.
        lenient = {'sc_phone_lenient': True}
        cls.player.with_context(**lenient).write({'email': 'pat.one@example.com', 'phone': '+1 (555) 010-0123'})
        cls.contact.with_context(**lenient).write({'mobile': '555 010 0456', 'email': 'parent.one@example.com'})
        cls.org.write({'email': 'org@example.com'})
        cls.tp.partner_id.write({'email': 'pc.tp@example.com'})
        cls.event.write({'partner_id': cls.org.id})

    def _player_url(self):
        return '/my/player?player_id=%s&tab=info' % self.player.id

    @staticmethod
    def _display(tree, record, field):
        return tree.xpath('//*[@data-sc-display="%s:%s:%s"]' % (record._name, record.id, field))


@tagged('post_install', '-at_install')
class TestTapLinks(TapLinksCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- UC-T5 -----------------------------------------------------------
    def test_href_helper(self):
        self.assertEqual(sc_contact_href('tel', '+1 (555) 010-0123'), 'tel:+15550100123')
        self.assertEqual(sc_contact_href('tel', '555.010.0456'), 'tel:5550100456')
        self.assertEqual(sc_contact_href('mailto', ' a.b@example.com '), 'mailto:a.b@example.com')
        for kind, value in (('tel', ''), ('tel', 'n/a'), ('mailto', ''), ('mailto', None), ('tel', False)):
            self.assertIsNone(sc_contact_href(kind, value), (kind, value))

    # -- UC-T1 -----------------------------------------------------------
    def test_player_contact_links(self):
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self._player_url())
            email = self._display(tree, self.player, 'email')
            phone = self._display(tree, self.player, 'phone')
            self.assertEqual(len(email), 1)
            self.assertEqual(len(phone), 1)
            self.assertEqual(email[0].tag, 'a')
            self.assertEqual(email[0].get('href'), 'mailto:pat.one@example.com')
            self.assertEqual(email[0].get('data-sc-display-href'), 'mailto')
            self.assertEqual(email[0].text_content().strip(), 'pat.one@example.com')
            self.assertEqual(phone[0].tag, 'a')
            self.assertEqual(phone[0].get('href'), 'tel:+15550100123')
            self.assertEqual(phone[0].get('data-sc-display-href'), 'tel')
            self.assertEqual(phone[0].text_content().strip(), '+1 (555) 010-0123')
            # Other read rows stay plain text.
            street = self._display(tree, self.player, 'street')
            self.assertEqual(street[0].tag, 'span')

    # -- UC-T2 -----------------------------------------------------------
    def test_emergency_contact_links(self):
        self._login_tp()
        _text, tree = self._get(self._player_url())
        mobile = self._display(tree, self.contact, 'mobile')
        email = self._display(tree, self.contact, 'email')
        self.assertEqual(mobile[0].tag, 'a')
        self.assertEqual(mobile[0].get('href'), 'tel:5550100456')
        self.assertEqual(email[0].tag, 'a')
        self.assertEqual(email[0].get('href'), 'mailto:parent.one@example.com')

    # -- UC-T3 -----------------------------------------------------------
    def test_empty_value_is_not_a_link(self):
        self.contact.write({'mobile': False, 'email': False})
        self._login_tp()
        _text, tree = self._get(self._player_url())
        for field in ('mobile', 'email'):
            node = self._display(tree, self.contact, field)[0]
            self.assertIsNone(node.get('href'), field)
            self.assertEqual(node.text_content().strip(), '—', field)
            # Still carries the kind, so a later save can make it a link.
            self.assertTrue(node.get('data-sc-display-href'), field)

    def test_save_answers_display_for_links(self):
        """The pencil save's ``display`` is the raw value the browser turns
        into the new href (sc_app_ui.js)."""
        self._login_tp()
        self.contact.invalidate_recordset()
        resp = self.url_open('/my/app/save/%s/%s' % (self.contact._name, self.contact.id), data={
            'field': 'mobile', 'value': '514 555 0199',  # task 1645: a valid number
            'write_date': fields.Datetime.to_string(self.contact.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['display'], '+1 514-555-0199')

    # -- UC-T4 -----------------------------------------------------------
    def test_event_staff_and_organization_emails(self):
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get('/my/event/%s' % self.event.id)
            hero = tree.xpath('//*[@data-sc-section="event.hero"]')[0]
            staff = hero.xpath('.//*[@data-sc-event-staff]')
            self.assertEqual(len(staff), 1)
            self.assertIn('PC TP', staff[0].text_content())
            self.assertEqual(staff[0].xpath('.//a/@href'), ['mailto:pc.tp@example.com'])
            org = hero.xpath('.//*[@data-sc-event-organization]')
            self.assertEqual(len(org), 1)
            self.assertIn('PC Org', org[0].text_content())
            self.assertEqual(org[0].xpath('.//a/@href'), ['mailto:org@example.com'])

    def test_event_staff_without_email(self):
        self.tp.partner_id.write({'email': False})
        self.org.write({'email': False})
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        hero = tree.xpath('//*[@data-sc-section="event.hero"]')[0]
        staff = hero.xpath('.//*[@data-sc-event-staff]')
        self.assertIn('PC TP', staff[0].text_content())
        self.assertFalse(hero.xpath('.//a[starts-with(@href, "mailto:")]'))
        self.assertIn('PC Org', hero.xpath('.//*[@data-sc-event-organization]')[0].text_content())

    # -- UC-T6 -----------------------------------------------------------
    def test_switch_off_untouched(self):
        self._switch(False)
        self._login_tp()
        text, _tree = self._get('/my/event/%s' % self.event.id)
        self.assertNotIn('data-sc-display-href', text)
        self.assertNotIn('data-sc-event-staff', text)


@tagged('post_install', '-at_install')
class TestTapLinksTour(TapLinksCommon):
    """UC-T1 in the browser: a pencil save of an emergency contact's mobile
    moves the tel: href to the new number, without a reload."""

    def test_tap_links_tour(self):
        self._switch(True)
        self.start_tour(self._player_url(), 'sc_1585_tap_links', login='pc.tp@example.com')
        self.contact.invalidate_recordset()
        self.assertEqual(self.contact.mobile, '+1 514-555-0177')  # task 1645: stored formatted


@tagged('post_install', '-at_install')
class TestTapLinksFr(TapLinksCommon):
    """UC-T7: rendered in fr_CA (website-aware: fr_CA on the website + the
    frontend_lang cookie)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})

    @staticmethod
    def _label_of(node):
        return node.xpath('ancestor::dd[1]/preceding-sibling::dt[1]')[0].text_content().strip()

    def test_labels_in_french(self):
        self._switch(True)
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get(self._player_url())
        self.assertEqual(self._label_of(self._display(tree, self.player, 'email')[0]), 'Courriel')
        self.assertEqual(self._label_of(self._display(tree, self.player, 'phone')[0]), 'Téléphone')
        self.assertEqual(self._label_of(self._display(tree, self.contact, 'mobile')[0]), 'Cellulaire')
        _text, tree = self._get('/my/event/%s' % self.event.id)
        org = tree.xpath('//*[@data-sc-event-organization]')[0]
        self.assertEqual(org.xpath('preceding-sibling::dt[1]')[0].text_content().strip(), 'Organisation')
        staff = tree.xpath('//*[@data-sc-event-staff]')[0]
        staff_label = staff.xpath('ancestor::dd[1]/preceding-sibling::dt[1]')[0].text_content().strip()
        self.assertNotEqual(staff_label, 'Assigned Staff')
