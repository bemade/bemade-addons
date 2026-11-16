"""Task 5196 — the clinic's roles, nav, visibility keys and pages live on the
kit's per-database ``portal.kit`` hooks. Synthetic fixtures only.

Acceptance criteria:

* UC-P1 The module-level registries are gone from the clinic: no
  ``NAV_REGISTRY`` / ``VISIBILITY_REGISTRY`` / ``ROLE_GROUPS`` /
  ``ROLE_STAFF_ROLES`` / ``APP_ROLES`` / ``_bookings_enabled`` /
  ``visible_nav`` / ``can`` in ``models/sc_app_roles.py``, no ``PAGES`` /
  ``resolve`` / ``match_url`` / ``safe_return_url`` / ``nav_label`` in
  ``models/sc_app_nav.py``, whose ``Page`` is the kit's (nothing an addon can mutate at
  import time; the leak's structural proof).
* UC-P2 The clinic's content is registered through the hooks: its roles
  (head_coach / head_therapist / doctor through ``staff_roles``, internal
  not an app role), nav entries, visibility keys and pages.
* UC-P3 The bookings page and nav entry exist in this database exactly
  when ``bemade_sports_clinic_bookings`` is installed here (per database,
  never by import).
* UC-P4 ``res.users._sc_app_roles()`` is the kit's ``_pk_roles()``: groups
  plus the staff-row roles of ``_pk_extra_roles``.
* UC-P5 (task 5391) Every clinic role is the app ``fitcrew``'s; another
  consumer's app registered in the same database (declared FIRST, a page
  on ``/my/home``, a tab for the same role names, a search provider, its
  own layout) never reaches a Fit Crew user: ``/my/home`` is
  ``sc_app_home``, the crumbs, tabs, pages, providers and layout are Fit
  Crew's (the first-match bug of bemade-addons PR #623).
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit import tools as pk_tools
from odoo.addons.bemade_portal_kit.tests.common import pk_hooks
from odoo.addons.bemade_sports_clinic.models import sc_app_nav, sc_app_roles
from odoo.addons.bemade_sports_clinic.models.sc_app_nav import SC_APP


@tagged('post_install', '-at_install')
class TestPortalKitHooks5196(TransactionCase):

    # -- UC-P1 ------------------------------------------------------------
    def test_no_module_level_registries(self):
        for name in ('NAV_REGISTRY', 'VISIBILITY_REGISTRY', 'ROLE_GROUPS', 'ROLE_STAFF_ROLES',
                     'APP_ROLES', '_bookings_enabled', 'visible_nav', 'can', 'is_visible',
                     '_nav'):
            self.assertFalse(hasattr(sc_app_roles, name), 'sc_app_roles.%s' % name)
        for name in ('PAGES', 'resolve', 'match_url', 'safe_return_url', 'nav_label',
                     '_static', '_trail', '_readable'):
            self.assertFalse(hasattr(sc_app_nav, name), 'sc_app_nav.%s' % name)
        # The page class is the kit's (imported to declare the pages), not a copy.
        self.assertIs(sc_app_nav.Page, pk_tools.Page)

    # -- UC-P2 ------------------------------------------------------------
    def test_clinic_content_is_registered(self):
        kit = self.env['portal.kit']
        roles = kit.pk_roles()
        self.assertEqual(set(roles) & set(sc_app_roles.ALL_ROLES), set(sc_app_roles.ALL_ROLES))
        self.assertEqual(roles['head_coach']['staff_roles'], ('head_coach',))
        self.assertFalse(roles['internal']['app'])
        self.assertNotIn('internal', kit.pk_app_roles())
        keys = [entry['key'] for entry in kit.pk_nav_entries(app=SC_APP)]
        for key in ('teams', 'players', 'notepad', 'activities', 'clinic', 'events',
                    'timesheets', 'more', 'digests', 'backend', 'install'):
            self.assertIn(key, keys)
        self.assertIn('patient.medical_alerts', kit.pk_visibility())
        pages = kit.pk_pages(app=SC_APP)
        for key in sc_app_nav.TOP_LEVEL | {'sc_app_player', 'sc_app_team', 'sc_app_clinic'}:
            self.assertIn(key, pages)
        self.assertEqual(kit.pk_resolve('sc_app_events', {}, app=SC_APP)['crumbs'],
                         [(str(kit.pk_nav_label('more', app=SC_APP)), '/my/app/more')])

    # -- UC-P3 ------------------------------------------------------------
    def test_bookings_entries_follow_this_database(self):
        installed = bool(self.env['ir.module.module'].search_count([
            ('name', '=', 'bemade_sports_clinic_bookings'),
            ('state', 'in', ('installed', 'to upgrade'))]))
        kit = self.env['portal.kit']
        self.assertEqual('sc_app_bookings' in kit.pk_pages(app=SC_APP), installed)
        self.assertEqual('bookings' in kit.pk_nav_labels(app=SC_APP), installed)

    # -- UC-P4 ------------------------------------------------------------
    def test_sc_app_roles_is_the_kit_roles(self):
        team = self.env['sports.team'].create({'name': 'Kit 5196 Team'})
        coach = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'kit5196.coach', 'login': 'kit5196.coach@example.com',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_team_coach').id])],
        })
        self.assertEqual(coach._sc_app_roles(), coach._pk_roles())
        self.assertEqual(coach._pk_extra_roles(), frozenset())
        self.env['sports.team.staff'].create({
            'team_id': team.id, 'partner_id': coach.partner_id.id, 'role': 'head_coach'})
        self.assertEqual(coach._pk_extra_roles(), frozenset({'head_coach'}))
        self.assertEqual(coach._sc_app_roles(), frozenset({'coach', 'head_coach'}))

    # -- UC-P5 ------------------------------------------------------------
    def test_another_app_never_reaches_fit_crew(self):
        kit = self.env['portal.kit']
        roles = kit.pk_roles()
        self.assertEqual({spec['app'] for role, spec in roles.items() if role in sc_app_roles.ALL_ROLES},
                         {SC_APP, False})
        coach = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'kit5391.coach', 'login': 'kit5391.coach@example.com',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_team_coach').id])],
        })
        other_page = pk_tools.pk_static_page('other_home', '/my/home', 'Other Today', app='other')
        other_tab = pk_tools.pk_nav('other_tab', 'Other', 'home', '/my/other', {'coach', 'other_member'}, 1,
                                    ('tab', 'rail'), app='other')
        with pk_hooks(
                self.env,
                _pk_roles=lambda orig: dict(orig, other_member={'groups': (), 'app': 'other'}),
                _pk_apps=lambda orig: dict(orig, other={'sequence': 1, 'layout': 'other.layout'}),
                _pk_pages=lambda orig: [other_page] + list(orig),
                _pk_nav=lambda orig: [other_tab] + list(orig),
                _pk_search_providers=lambda orig: [
                    {'key': 'other', 'title': 'Other', 'search': lambda *a: [], 'app': 'other'}] + list(orig)):
            ckit = kit.with_user(coach)
            self.assertEqual(ckit._pk_app(), SC_APP)
            self.assertEqual(ckit.pk_match_url('/my/home')[0], 'sc_app_home')
            self.assertEqual(ckit.pk_resolve('pk_dash_configure', {})['crumbs'], [('Dashboard', '/my/home')])
            tabs = [entry['key'] for entry in ckit.pk_visible_nav(coach._sc_app_roles(), 'tab')]
            self.assertNotIn('other_tab', tabs)
            self.assertIn('teams', tabs)
            self.assertNotIn('other_home', ckit.pk_pages())
            self.assertNotIn('other', [p['key'] for p in ckit.pk_search_providers()])
            self.assertEqual(ckit._pk_layout(), 'bemade_sports_clinic.sc_app_layout')
            # The other app sees its own home, never Fit Crew's.
            self.assertEqual(kit.pk_match_url('/my/home', app='other')[0], 'other_home')
            self.assertNotIn('sc_app_teams', kit.pk_pages(app='other'))
