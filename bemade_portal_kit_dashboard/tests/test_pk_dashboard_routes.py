# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5202 (kit P7): the dashboard's pages with synthetic widgets, filters
and scope (tests/common.py), whatever consumer is installed.

Acceptance criteria:

* UC-R1 /my/home (switch on, app user): the enabled sections in their
  zones (left / right / bottom, a lone side column solo), each framed
  (title or custom title, scope line, the widget's body from its builder),
  « Configure »; every section off = the empty state; a scope holding
  nothing = the « nothing in scope » line instead of the body. Switch off:
  the stock portal home.
* UC-R2 The page parts extension point: the context hook reaches the
  builders, the page values hook and the template's body slot draw the
  consumer's parts.
* UC-R3 The configure sheet: one row per instance in its zone (switch,
  ▲ / ▼ disabled at the edges, « Move to », the trash on added ones only),
  the scope pickers (hidden inputs + tag props), each filter drawn by its
  type (multi = switches + presence marker, choice / int = a select), the
  add form (widgets the viewer may have, default zone the shorter column),
  the move route on the zones; in the app layout; switch off: home.
* UC-R4 POST routes, JSON (fetch): /save (switch, title, filters, scope),
  /move (step, zone + position), /add, /remove, /reset answer {ok}; a
  refusal answers 400 {ok: false, error} and stores nothing.
* UC-R5 Without JS (PRG): a POST redirects to the sheet (anchored on the
  instance); a refusal is shown on the sheet once.
"""
import json

from lxml import html as lxml_html

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_csrf, pk_frontend_langs

from .common import pk_dash_controller_hook, pk_dash_shell, pk_dash_templates

URL = '/my/app/dashboard/configure'
JSON_HEADERS = {'X-Requested-With': 'XMLHttpRequest'}


@tagged('post_install', '-at_install')
class TestPkDashboardRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)  # task 5392: the English texts asserted below
        cls.member = new_test_user(cls.env, login='pk_p7_web', groups='base.group_portal', lang='en_US',
                                   name='PK P7 Web')
        cls.member.partner_id.email = 'pk_p7_web@example.com'
        pk_dash_templates(cls.env)

    def setUp(self):
        super().setUp()
        shell = pk_dash_shell(self.env)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        self.authenticate('pk_p7_web', 'pk_p7_web')
        self.Dash = self.env(user=self.member)['portal.kit.dashboard']

    def tree(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return lxml_html.document_fromstring(response.text)

    def post(self, path, data, json_answer=True):
        data = dict(data, csrf_token=pk_csrf(self))
        return self.url_open(URL + path, data=data, headers=JSON_HEADERS if json_answer else None,
                             allow_redirects=False)

    def layout(self):
        self.env.invalidate_all()
        return self.Dash._pk_dash_layout()

    # ------------------------------------------------------------- UC-R1
    def test_home_sections_in_zones(self):
        self.Dash._pk_dash_layout_update('gamma', title='My gamma', settings={'scope_tag_ids': [2]})
        tree = self.tree('/my/home')
        dash = tree.xpath('//*[contains(@class, "o_pk_app")]//div[@data-pk-dashboard]')[0]
        zones = dash.xpath('./div[@data-pk-dash-zone]')
        self.assertEqual([z.get('data-pk-dash-zone') for z in zones], ['left', 'right', 'bottom'])
        got = {z.get('data-pk-dash-zone'): [s.get('data-pk-dash-instance') for s in z.xpath('./section')]
               for z in zones}
        self.assertEqual(got, {'left': ['alpha'], 'right': ['beta'], 'bottom': ['gamma']})
        gamma = dash.xpath('.//section[@data-pk-dash-instance="gamma"]')[0]
        self.assertIn('o_pk_dash_section_gamma', gamma.get('class'))
        self.assertEqual(gamma.get('data-pk-dash-widget'), 'gamma')
        self.assertEqual(gamma.xpath('.//*[contains(@class, "o_pk_dash_title_text")]')[0].text, 'My gamma')
        self.assertEqual(gamma.xpath('.//p[@data-pk-dash-scope]')[0].text, 'Two')
        self.assertEqual(gamma.xpath('.//div[contains(@class, "o_pk_dash_body")]/p[@class="pk_t_body"]')[0].text,
                         'built gamma')
        beta = dash.xpath('.//section[@data-pk-dash-instance="beta"]')[0]
        self.assertEqual(beta.xpath('.//p[@data-pk-dash-scope]')[0].text, 'All tags')
        self.assertEqual(beta.xpath('.//*[contains(@class, "o_pk_dash_title_text")]')[0].text, 'Beta')
        alpha = dash.xpath('.//section[@data-pk-dash-instance="alpha"]')[0]
        self.assertFalse(alpha.xpath('.//p[@data-pk-dash-scope]'), 'unscoped: no scope line')
        configure = tree.xpath('//a[@data-pk-action="dashboard.configure"]')[0]
        self.assertEqual(configure.get('href'), URL)
        self.assertFalse(tree.xpath('//*[contains(@class, "o_pk_dash_zone_solo")]'))

    def test_home_solo_empty_and_no_scope(self):
        self.Dash._pk_dash_layout_update('beta', enabled=False)
        tree = self.tree('/my/home')
        self.assertIn('o_pk_dash_zone_solo', tree.xpath('//div[@data-pk-dash-zone="left"]')[0].get('class'))
        # A scope that resolves to nothing: the line instead of the body.
        from unittest.mock import patch
        dash_cls = type(self.env['portal.kit.dashboard'])
        with patch.object(dash_cls, '_pk_dash_scope_resolve', lambda self, s, v, u: []):
            tree = self.tree('/my/home')
        gamma = tree.xpath('//section[@data-pk-dash-instance="gamma"]')[0]
        self.assertFalse(gamma.xpath('.//p[@class="pk_t_body"]'))
        self.assertIn("Nothing in this section's scope", gamma.text_content())
        for key in ('alpha', 'gamma'):
            self.Dash._pk_dash_layout_update(key, enabled=False)
        tree = self.tree('/my/home')
        self.assertFalse(tree.xpath('//section[@data-pk-dash-instance]'))
        self.assertIn('Every section is switched off', tree.xpath('//div[@data-pk-dashboard]')[0].text_content())

    def test_home_switch_off(self):
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_kit.enabled', False)
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('data-pk-dashboard', response.text)

    # ------------------------------------------------------------- UC-R2
    def test_page_parts(self):
        from odoo.addons.bemade_portal_kit_dashboard.controllers.pk_dashboard import PortalKitDashboard as Ctrl
        self.env['ir.ui.view'].create({
            'name': 'pk dash test page', 'type': 'qweb', 'key': 'pk_dash_test.page',
            'arch': '<t t-name="pk_dash_test.page"><t t-call="{{ pk_layout }}">'
                    '<t t-call="bemade_portal_kit_dashboard.pk_dash_home">'
                    '<div class="pk_t_part" t-out="pk_t_part"/></t></t></t>',
        })
        seen = []
        base_context = Ctrl._pk_dash_context

        def context(self, Dash, viewer):
            ctx = base_context(self, Dash, viewer)
            ctx['part'] = 'from ctx'
            return ctx

        def build(self, spec, instance, scope, ctx):
            seen.append(ctx['part'])
            ctx['asked'] = True
            return {'note': 'n'}

        def page_values(self, values, ctx):
            return dict(values, pk_t_part='part asked' if ctx.get('asked') else 'no')

        with pk_dash_controller_hook('_pk_dash_context', context), pk_dash_controller_hook('_pk_dash_build', build), \
                pk_dash_controller_hook('_pk_dash_page_values', page_values), \
                pk_dash_controller_hook('_pk_dash_home_template', lambda self: 'pk_dash_test.page'):
            tree = self.tree('/my/home')
        self.assertEqual(seen, ['from ctx'] * 3)
        self.assertEqual(tree.xpath('//div[@class="pk_t_part"]')[0].text, 'part asked')
        self.assertEqual(len(tree.xpath('//section[@data-pk-dash-instance]')), 3)

    # ------------------------------------------------------------- UC-R3
    def test_configure_sheet(self):
        self.Dash._pk_dash_layout_add('beta', zone='right')
        tree = self.tree(URL)
        self.assertTrue(tree.xpath('//*[contains(@class, "o_pk_app")]'))
        root = tree.xpath('//div[@data-pk-dash-zones]')[0]
        self.assertEqual(root.get('data-pk-dash-move-url'), URL + '/move')
        lists = root.xpath('.//ol[@data-pk-dash-zone]')
        self.assertEqual({ol.get('data-pk-dash-zone'): [li.get('data-pk-dash-item') for li in ol.xpath('./li')]
                          for ol in lists}, {'left': ['alpha'], 'right': ['beta', 'beta-2'], 'bottom': ['gamma']})
        beta = root.xpath('.//li[@data-pk-dash-item="beta"]')[0]
        self.assertEqual(beta.get('id'), 'pk-dash-beta')
        self.assertTrue(beta.xpath('.//button[@data-pk-dash-move="up"]')[0].get('disabled'))
        self.assertFalse(beta.xpath('.//button[@data-pk-dash-move="down"]')[0].get('disabled'))
        self.assertFalse(beta.xpath('.//*[@data-pk-dash-remove]'), 'a base instance: no trash')
        self.assertTrue(root.xpath('.//li[@data-pk-dash-item="beta-2"]//*[@data-pk-dash-remove]'))
        self.assertTrue(root.xpath('.//form[@id="pk_dash_remove_beta-2"][@data-pk-confirm-title]'))
        form = beta.xpath('.//form[@data-pk-dash-instance="beta"]')[0]
        self.assertEqual(form.get('action'), URL + '/save')
        scope = form.xpath('.//fieldset[@data-pk-dash-scope]')[0]
        self.assertEqual(scope.xpath('.//input[@type="hidden"]/@name'), ['scope_tag_ids'])
        self.assertEqual(scope.xpath('.//input[@name="scope_tag_ids"]')[0].get('id'), 'pk_dash_beta_scope_tag_ids')
        self.assertIn('everything you have access to', scope.text_content())
        colors = form.xpath('.//fieldset[@data-pk-dash-filter="colors"]')[0]
        self.assertEqual(colors.xpath('.//input[@name="colors_present"]/@value'), ['1'])
        self.assertEqual(colors.xpath('.//input[@name="colors"]/@value'), ['red', 'green', 'blue'])
        self.assertEqual(colors.xpath('.//input[@id="pk_dash_beta_colors_green"]/@name'), ['colors'])
        gamma_form = root.xpath('.//form[@data-pk-dash-instance="gamma"]')[0]
        days = gamma_form.xpath('.//select[@name="days"]')[0]
        self.assertEqual(days.get('id'), 'pk_dash_gamma_days')
        self.assertEqual(days.xpath('./option/@value'), ['7', '14', '30'])
        self.assertEqual(days.xpath('./option[@selected]/@value'), ['14'])
        self.assertEqual(gamma_form.xpath('.//select[@name="size"]/option[@selected]/@value'), ['small'])
        alpha_form = root.xpath('.//form[@data-pk-dash-instance="alpha"]')[0]
        self.assertFalse(alpha_form.xpath('.//fieldset[@data-pk-dash-scope]'), 'unscoped')
        add = tree.xpath('//select[@id="pk_dash_add_widget"]/option/@value')
        self.assertEqual(add, ['alpha', 'beta', 'gamma'])
        self.assertEqual(tree.xpath('//select[@id="pk_dash_add_zone"]/option[@selected]/@value'), ['left'])
        self.assertTrue(tree.xpath('//form[@data-pk-dash-reset-form][@data-pk-confirm-title]'))

    def test_configure_switch_off(self):
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_kit.enabled', False)
        response = self.url_open(URL, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/my/home'))

    # ------------------------------------------------------------- UC-R4
    def test_json_posts(self):
        answer = self.post('/save', {'instance_id': 'beta', 'enabled': '0', 'title': ' B  two ',
                                     'scope_tag_ids': '3, 1', 'colors_present': '1'})
        self.assertEqual((answer.status_code, answer.json()), (200, {'ok': True}))
        beta = {i['id']: i for i in self.layout()}['beta']
        self.assertEqual((beta['enabled'], beta['title']), (False, 'B two'))
        self.assertEqual(beta['settings'], {'scope_tag_ids': [1, 3], 'colors': []})
        answer = self.post('/save', {'instance_id': 'gamma', 'size': 'large', 'days': '30'})
        self.assertEqual(answer.json(), {'ok': True})
        gamma = {i['id']: i for i in self.layout()}['gamma']
        self.assertEqual((gamma['settings']['size'], gamma['settings']['days']), ('large', 30))
        self.assertEqual(self.post('/add', {'widget': 'alpha', 'zone': 'bottom'}).json(), {'ok': True})
        self.assertEqual(self.post('/move', {'instance_id': 'alpha-2', 'step': 'up'}).json(), {'ok': True})
        self.assertEqual([i['id'] for i in self.layout() if i['zone'] == 'bottom'], ['alpha-2', 'gamma'])
        self.assertEqual(self.post('/move', {'instance_id': 'alpha-2', 'zone': 'right', 'position': '0'}).json(),
                         {'ok': True})
        self.assertEqual([i['id'] for i in self.layout() if i['zone'] == 'right'], ['alpha-2', 'beta'])
        self.assertEqual(self.post('/remove', {'instance_id': 'alpha-2'}).json(), {'ok': True})
        self.assertNotIn('alpha-2', [i['id'] for i in self.layout()])
        self.assertEqual(self.post('/reset', {}).json(), {'ok': True})
        self.env.invalidate_all()
        self.assertFalse(self.member.sudo().pk_dashboard_layout)

    def test_json_refusals(self):
        for path, data, error in (
            ('/save', {'instance_id': 'gamma', 'size': 'huge'}, 'Invalid setting.'),
            ('/save', {'instance_id': 'beta', 'scope_tag_ids': '9'},
             'You cannot limit a section to records you do not have access to.'),
            ('/save', {'instance_id': 'beta', 'scope_tag_ids': 'a,b'}, 'Invalid scope.'),
            ('/save', {'instance_id': 'nope'}, 'This section no longer exists.'),
            ('/add', {'widget': 'secret'}, 'This section is not available to you.'),
            ('/move', {'instance_id': 'beta', 'zone': 'top'}, 'Invalid dashboard layout.'),
            ('/move', {'instance_id': 'beta', 'zone': 'left', 'position': 'x'}, 'Invalid dashboard layout.'),
            ('/remove', {'instance_id': 'beta'}, 'This section can be switched off, not removed.'),
        ):
            answer = self.post(path, data)
            self.assertEqual(answer.status_code, 400, (path, data))
            self.assertEqual(answer.json(), {'ok': False, 'error': error})
        self.env.invalidate_all()
        self.assertFalse(self.member.sudo().pk_dashboard_layout, 'nothing stored by a refusal')

    # ------------------------------------------------------------- UC-R5
    def test_prg(self):
        answer = self.post('/save', {'instance_id': 'beta', 'title': 'Bee'}, json_answer=False)
        self.assertEqual(answer.status_code, 303)
        self.assertTrue(answer.headers['Location'].endswith(URL + '#pk-dash-beta'))
        answer = self.post('/add', {'widget': 'beta'}, json_answer=False)
        self.assertTrue(answer.headers['Location'].endswith(URL + '#pk-dash-beta-2'))
        answer = self.post('/save', {'instance_id': 'gamma', 'days': '3'}, json_answer=False)
        self.assertTrue(answer.headers['Location'].endswith(URL + '#pk-dash-gamma'))
        page = self.url_open(URL).text
        self.assertIn('Invalid setting.', page)
        self.assertNotIn('Invalid setting.', self.url_open(URL).text, 'shown once')
        self.assertEqual(json.loads(json.dumps({i['id']: i['title'] for i in self.layout()}))['beta'], 'Bee')
