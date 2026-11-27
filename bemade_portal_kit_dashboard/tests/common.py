# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers: the dashboard as this addon alone draws it, whatever
consumer is installed, with SYNTHETIC widgets, filters and scope.

* widgets: ``alpha`` (left, every viewer, unscoped), ``beta`` (right,
  scoped, filter ``colors`` multi), ``gamma`` (bottom, scoped, filters
  ``size`` choice and ``days`` int, default ``days`` 14 for it) and
  ``secret`` (left, visibility key ``dash.secret``: no role has it);
* scope: one field ``scope_tag_ids``; the viewer may name tags 1, 2, 3
  (labels One, Two, Three); nothing chosen = all three;
* body template ``pk_dash_test.body`` (created by ``pk_dash_templates``),
  builder values ``{'note': 'built <key>', 'tags': <scope>}``.
"""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from odoo.addons.bemade_portal_kit.tests.common import pk_hook, pk_kit_shell
from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit_dashboard import (
    PortalKitDashboard, pk_dash_filter, pk_dash_widget,
)

ROLES = {'member': {'groups': ('base.group_portal',)}}
BODY = 'pk_dash_test.body'
TAGS = ((1, 'One'), (2, 'Two'), (3, 'Three'))
ORDER = ['alpha', 'beta', 'gamma']
ENGINE_HOOKS = (
    '_pk_widgets', '_pk_dash_filters', '_pk_dash_filter_choices', '_pk_dash_viewer', '_pk_dash_widget_title',
    '_pk_dash_scope_fields', '_pk_dash_scope_universe', '_pk_dash_scope_allowed', '_pk_dash_scope_options',
    '_pk_dash_scope_resolve', '_pk_dash_scope_empty', '_pk_dash_scope_label', '_pk_dash_scope_hint',
    '_pk_dash_scope_refused', '_pk_dash_scope_empty_label', '_pk_dash_intro',
)
CONTROLLER_HOOKS = ('_pk_dash_context', '_pk_dash_page_values', '_pk_dash_home_template', '_pk_dash_render',
                    '_pk_dash_build')


def widgets(_self):
    return [
        pk_dash_widget('alpha', 'Alpha', 'left', BODY),
        pk_dash_widget('beta', 'Beta', 'right', BODY, scoped=True, filters=('colors',)),
        pk_dash_widget('gamma', 'Gamma', 'bottom', BODY, scoped=True, filters=('size', 'days'),
                       defaults={'days': 14}),
        pk_dash_widget('secret', 'Secret', 'left', BODY, can='dash.secret'),
    ]


def filters(_self):
    return {
        'colors': pk_dash_filter('multi', 'Colors', (('red', 'Red'), ('green', 'Green'), ('blue', 'Blue')),
                                 default=['red', 'green', 'blue']),
        'size': pk_dash_filter('choice', 'Size', (('small', 'Small'), ('large', 'Large')), default='small'),
        'days': pk_dash_filter('int', 'Period', ((7, '7 days'), (14, '14 days'), (30, '30 days')), default=7),
    }


def scope_resolve(_self, settings, viewer, universe):
    chosen = set(settings.get('scope_tag_ids') or ())
    return [tag for tag in universe if not chosen or tag in chosen]


def scope_label(_self, settings, scope):
    if not settings.get('scope_tag_ids'):
        return 'All tags'
    return ', '.join(label for tag, label in TAGS if tag in scope)


SYNTHETIC = {
    '_pk_widgets': widgets,
    '_pk_dash_filters': filters,
    '_pk_dash_scope_fields': lambda self: [{'name': 'scope_tag_ids', 'label': 'Tags', 'placeholder': 'All tags'}],
    '_pk_dash_scope_universe': lambda self, viewer: [tag for tag, _label in TAGS],
    '_pk_dash_scope_allowed': lambda self, universe: {'scope_tag_ids': set(universe)},
    '_pk_dash_scope_options': lambda self, universe: {'scope_tag_ids': [t for t in TAGS if t[0] in universe]},
    '_pk_dash_scope_resolve': scope_resolve,
    '_pk_dash_scope_label': scope_label,
}


def build(_self, spec, instance, scope, ctx):
    return {'note': 'built %s' % spec['key'], 'tags': scope}


@contextmanager
def pk_dash_shell(env, synthetic=True):
    """``pk_kit_shell`` + this addon's pages and engine: the consumers'
    overrides of the engine and controller hooks set aside, the synthetic
    registry above (``synthetic=False``: none, the addon's own empty
    defaults), the visibility key ``dash.secret`` (no role)."""
    from odoo.addons.portal.controllers.portal import CustomerPortal
    from odoo.addons.bemade_portal_kit_dashboard.controllers.pk_dashboard import PortalKitDashboard as Ctrl
    from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit import PortalKit as DashKit

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    dash_cls = type(env['portal.kit.dashboard'])
    kit_cls = type(env['portal.kit'])
    with ExitStack() as stack:
        stack.enter_context(pk_kit_shell(env, roles=ROLES))
        stack.enter_context(patch.object(kit_cls, '_pk_pages', lambda self: DashKit._pk_pages(self)))
        stack.enter_context(pk_hook(env, '_pk_visibility',
                                    lambda orig: dict(orig, **{'dash.secret': {'include': ('nobody',)}})))
        for hook in ENGINE_HOOKS:
            stack.enter_context(patch.object(dash_cls, hook, getattr(PortalKitDashboard, hook)))
        if synthetic:
            for hook, func in SYNTHETIC.items():
                stack.enter_context(patch.object(dash_cls, hook, func))
        # Every portal controller (a consumer's may not derive from the kit's).
        for sub in set(subclasses(CustomerPortal)):
            for hook in CONTROLLER_HOOKS:
                if hook in sub.__dict__ and sub is not Ctrl:
                    stack.enter_context(patch.object(sub, hook, getattr(Ctrl, hook)))
        if synthetic:
            stack.enter_context(patch.object(Ctrl, '_pk_dash_build', build))
        env.registry.clear_cache()
        stack.callback(env.registry.clear_cache)
        yield


@contextmanager
def pk_dash_controller_hook(hook, func):
    """Swap a dashboard controller hook everywhere it is defined (this
    addon's controller and any consumer's that overrides it)."""
    from odoo.addons.portal.controllers.portal import CustomerPortal
    from odoo.addons.bemade_portal_kit_dashboard.controllers.pk_dashboard import PortalKitDashboard as Ctrl

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    with ExitStack() as stack:
        for sub in {Ctrl, *subclasses(CustomerPortal)}:
            if hook in sub.__dict__:
                stack.enter_context(patch.object(sub, hook, func))
        yield


def pk_dash_templates(env):
    """The synthetic body template (in the test transaction)."""
    return env['ir.ui.view'].create({
        'name': 'pk dash test body', 'type': 'qweb', 'key': BODY,
        'arch': '<t t-name="%s"><p class="pk_t_body" t-att-data-w="section[\'widget\']" '
                't-out="section.get(\'note\')"/></t>' % BODY,
    })
