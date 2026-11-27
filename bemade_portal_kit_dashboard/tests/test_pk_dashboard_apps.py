# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5391: the dashboard per app — two synthetic apps (« north »,
« south ») in one database.

Acceptance criteria:

* UC-DA1 Each viewer's dashboard holds the widgets of their app and the
  shared ones only (``pk_dash_app_widgets``, ``_pk_dash_widgets``,
  ``_pk_dash_widget``); the filters and scope fields of another app are not
  theirs (default settings, configure sheet).
* UC-DA2 ``/my/home`` draws the viewer's app's home: an app registering
  ``home_render`` gets that method's answer (no ``home()`` override); an app
  without one gets the kit's ``pk_dash_page`` with its own sections.
* UC-DA3 An app with its own home does not see the shared ``pk_dash_page``
  (its own page answers ``/my/home``); the other app does.
Synthetic users, widgets and apps only.
"""
from unittest.mock import patch

from lxml import html as lxml_html

from odoo.http import request
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_extra_roles, pk_hooks
from odoo.addons.bemade_portal_kit.tools import pk_static_page
from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit_dashboard import pk_dash_filter, pk_dash_widget

from .common import BODY, pk_dash_shell, pk_dash_templates

ROLES = {
    'n_member': {'groups': (), 'app': 'north'},
    's_member': {'groups': (), 'app': 'south'},
}
HOLDERS = {'pk_da_north': {'n_member'}, 'pk_da_south': {'s_member'}}
APPS = {
    'north': {'sequence': 10, 'home_render': '_pk_test_north_home'},
    'south': {'sequence': 20},
}


def _widgets(_self):
    return [
        pk_dash_widget('s_w', 'South Widget', 'left', BODY, app='south'),
        pk_dash_widget('alpha', 'Alpha', 'left', BODY),
        pk_dash_widget('n_w', 'North Widget', 'right', BODY, scoped=True, filters=('n_f',), app='north'),
    ]


def _filters(_self):
    return {
        'n_f': pk_dash_filter('choice', 'North filter', (('a', 'A'), ('b', 'B')), default='a', app='north'),
        's_f': pk_dash_filter('choice', 'South filter', (('x', 'X'),), default='x', app='south'),
    }


def _scope_fields(_self):
    return [{'name': 'scope_tag_ids', 'label': 'Tags', 'placeholder': 'All tags', 'app': 'north'}]


def _north_home(self, values):
    return request.make_response('NORTH HOME %s' % ','.join(s['id'] for s in values['pk_dash_sections']))


@tagged('post_install', '-at_install')
class TestPkDashboardApps(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = {login: new_test_user(cls.env, login=login, groups='base.group_portal', lang='en_US')
                     for login in HOLDERS}
        pk_dash_templates(cls.env)

    def setUp(self):
        super().setUp()
        from odoo.addons.bemade_portal_kit_dashboard.controllers.pk_dashboard import PortalKitDashboard as Ctrl
        dash_cls = type(self.env['portal.kit.dashboard'])
        for ctx in (pk_dash_shell(self.env),
                    pk_hooks(self.env, _pk_roles=lambda _orig: ROLES, _pk_apps=lambda _orig: APPS,
                             _pk_pages=lambda orig: list(orig) + [
                                 pk_static_page('n_home', '/my/home', 'North Home', app='north')]),
                    pk_extra_roles(self.env, lambda user: frozenset(HOLDERS.get(user.login, ()))),
                    patch.object(dash_cls, '_pk_widgets', _widgets),
                    patch.object(dash_cls, '_pk_dash_filters', _filters),
                    patch.object(dash_cls, '_pk_dash_scope_fields', _scope_fields),
                    patch.object(Ctrl, '_pk_test_north_home', _north_home, create=True)):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)

    def dash(self, login):
        return self.env(user=self.users[login])['portal.kit.dashboard']

    # ------------------------------------------------------------ UC-DA1
    def test_widgets_filters_scope_per_app(self):
        north, south = self.dash('pk_da_north'), self.dash('pk_da_south')
        self.assertEqual([s['key'] for s in north._pk_dash_widgets()], ['alpha', 'n_w'])
        self.assertEqual([s['key'] for s in south._pk_dash_widgets()], ['s_w', 'alpha'])
        self.assertEqual([s['key'] for s in north.pk_dash_app_widgets('south')], ['s_w', 'alpha'])
        self.assertIsNone(north._pk_dash_widget('s_w'))
        self.assertEqual(south._pk_dash_widget('s_w')['app'], 'south')
        self.assertEqual(set(north._pk_dash_app_filters()), {'n_f'})
        self.assertEqual(set(south._pk_dash_app_filters()), {'s_f'})
        self.assertEqual([f['name'] for f in north._pk_dash_app_scope_fields()], ['scope_tag_ids'])
        self.assertEqual(south._pk_dash_app_scope_fields(), [])
        layout = {inst['id']: inst['settings'] for inst in north._pk_dash_layout()}
        self.assertEqual(layout['n_w'], {'scope_tag_ids': [], 'n_f': 'a'})
        self.assertEqual([inst['id'] for inst in south._pk_dash_layout()], ['s_w', 'alpha'])
        self.assertEqual(south._pk_dash_viewer()['app'], 'south')

    # ------------------------------------------------------------ UC-DA2
    def test_home_is_the_viewers_apps(self):
        self.authenticate('pk_da_north', 'pk_da_north')
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'NORTH HOME alpha,n_w')
        self.authenticate('pk_da_south', 'pk_da_south')
        response = self.url_open('/my/home')
        self.assertEqual(response.status_code, 200)
        tree = lxml_html.document_fromstring(response.text)
        sections = tree.xpath('//div[@data-pk-dashboard]//section/@data-pk-dash-instance')
        self.assertEqual(sections, ['s_w', 'alpha'])
        # The configure sheet: south's sections only.
        response = self.url_open('/my/app/dashboard/configure')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('North Widget', response.text)
        self.assertIn('South Widget', response.text)

    # ------------------------------------------------------------ UC-DA3
    def test_dashboard_page_only_for_an_app_without_its_home(self):
        kit = self.env['portal.kit']
        self.assertNotIn('pk_dash_page', kit.pk_pages(app='north'))
        self.assertEqual(kit.with_user(self.users['pk_da_north']).pk_match_url('/my/home')[0], 'n_home')
        self.assertIn('pk_dash_page', kit.pk_pages(app='south'))
        self.assertEqual(kit.with_user(self.users['pk_da_south']).pk_match_url('/my/home')[0], 'pk_dash_page')
