"""Task 1752: a generic instance banner (« DÉMO ») driven by a system parameter.

Synthetic fixtures only.

Acceptance criteria:

* UC-B1 Parameter absent (prod, the default): no banner on the login page, the
  backend web client or the portal app shell.
* UC-B2 Parameter set (``bemade_sports_clinic.instance_banner`` = « DÉMO »):
  a red strip carrying exactly that text is rendered at the top of every
  page built on ``web.layout``: the login page (public), the backend web
  client (internal user) and the portal app shell (coach, phone and laptop
  share the same markup).
* UC-B3 A blank / whitespace-only value renders nothing.
* UC-B4 The strip never blocks the page: it is fixed, click-through
  (``pointer-events: none``) and carries a screen-reader explanation.
* UC-B5 The value is editable from the Settings form (« Instance banner »),
  stored in the system parameter, and cleared again when emptied.
"""
from lxml import html as lxml_html

from odoo.tests import Form, tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

PARAM = 'bemade_sports_clinic.instance_banner'


@tagged('post_install', '-at_install')
class TestInstanceBanner1752(AppShellCommon):

    def _set(self, value):
        self.env['ir.config_parameter'].sudo().set_param(PARAM, value)

    @staticmethod
    def _banner(text):
        nodes = lxml_html.fromstring(text).xpath('//*[@id="sc_instance_banner"]')
        return nodes[0] if nodes else None

    def _pages(self):
        """(label, html) of the three page families built on web.layout."""
        self.url_open('/web/session/logout')
        login_page = self.url_open('/web/login').text
        self.authenticate('admin', 'admin')
        backend = self.url_open('/odoo').text
        self._switch(True)
        self._login_coach()
        shell, _tree = self._get('/my/home')
        return [('login', login_page), ('backend', backend), ('app shell', shell)]

    # -- UC-B1 -----------------------------------------------------------
    def test_no_parameter_no_banner(self):
        self.assertFalse(self.env['ir.config_parameter'].sudo().get_param(PARAM))
        for label, text in self._pages():
            self.assertIsNone(self._banner(text), label)

    # -- UC-B2 / UC-B4 -----------------------------------------------------
    def test_banner_on_every_layout(self):
        self._set('DÉMO')
        for label, text in self._pages():
            node = self._banner(text)
            self.assertIsNotNone(node, label)
            label_nodes = node.xpath('.//*[contains(@class, "o_sc_instance_banner_label")]')
            self.assertEqual([n.text_content().strip() for n in label_nodes], ['DÉMO'], label)
            style = node.get('style') or ''
            self.assertIn('position: fixed', style, label)
            self.assertIn('pointer-events: none', style, label)
            self.assertTrue(node.xpath('.//*[contains(@class, "visually-hidden")]'), label)
            # first thing in <body>, so it never hides behind the page's own chrome
            body_children = lxml_html.fromstring(text).xpath('//body/*')
            self.assertEqual(body_children[0].get('id'), 'sc_instance_banner', label)

    # -- UC-B3 -----------------------------------------------------------
    def test_blank_value_renders_nothing(self):
        self._set('   ')
        for label, text in self._pages():
            self.assertIsNone(self._banner(text), label)

    # -- UC-B5 -----------------------------------------------------------
    def test_settings_field(self):
        ICP = self.env['ir.config_parameter'].sudo()
        form = Form(self.env['res.config.settings'])
        form.sc_instance_banner = 'DÉMO'
        form.save().execute()
        self.assertEqual(ICP.get_param(PARAM), 'DÉMO')
        form = Form(self.env['res.config.settings'])
        self.assertEqual(form.sc_instance_banner, 'DÉMO')
        form.sc_instance_banner = False
        form.save().execute()
        self.assertFalse(ICP.get_param(PARAM))
