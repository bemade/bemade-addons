# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers for ``portal.kit`` hooks. Synthetic content only.

``pk_hook(env, hook, build)`` swaps a ``portal.kit._pk_*()`` hook for the
duration of a ``with`` block: ``build(original)`` receives the result of the
installed chain (every consumer's ``super()``) and returns the content the
hook answers instead. Pass ``lambda _orig: {...}`` to REPLACE the content
(the kit tests do: the engine is tested on synthetic roles / nav / pages,
whatever consumer is installed), or extend ``_orig`` to ADD an entry (the
consumers' tests do). The per-registry cache is cleared on enter and exit.
"""
import re
from contextlib import contextmanager, ExitStack
from unittest.mock import patch


@contextmanager
def pk_hook(env, hook, build):
    cls = type(env['portal.kit'])
    original = getattr(cls, hook)

    def patched(self):
        return build(original(self))

    env.registry.clear_cache()
    try:
        with patch.object(cls, hook, patched):
            yield
    finally:
        env.registry.clear_cache()


@contextmanager
def pk_hooks(env, **builds):
    """Several ``pk_hook`` at once: ``pk_hooks(env, _pk_nav=..., _pk_roles=...)``."""
    with ExitStack() as stack:
        for hook, build in builds.items():
            stack.enter_context(pk_hook(env, hook, build))
        yield


@contextmanager
def pk_extra_roles(env, func):
    """Swap ``res.users._pk_extra_roles`` (per-user, never cached)."""
    with patch.object(type(env['res.users']), '_pk_extra_roles', func):
        yield


_CSRF_RE = re.compile(r'csrf_token:\s*"([^"]+)"')


def pk_csrf(case, url='/my'):
    """A CSRF token of the test opener's session (read from a portal page's
    session info)."""
    match = _CSRF_RE.search(case.url_open(url).text)
    case.assertTrue(match, 'no csrf token on %s' % url)
    return match.group(1)


@contextmanager
def pk_kit_shell(env, roles=None, layout='bemade_portal_kit.pk_app_layout'):
    """Task 5200 (P5): the kit's own pages as the kit alone draws them,
    whatever consumer is installed: ``roles`` (``{role: spec}``) replace the
    registry's, the kit's layout and the kit's ``_pk_app_values`` are used
    (a consumer's override of ``_pk_app_values`` is set aside), the help
    and search hooks answer nothing, the switch is on."""
    from odoo.addons.bemade_portal_kit.controllers.pk_shell import PortalKitShell

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    with ExitStack() as stack:
        for sub in set(subclasses(PortalKitShell)):
            if '_pk_app_values' in sub.__dict__:
                stack.enter_context(patch.object(sub, '_pk_app_values', PortalKitShell._pk_app_values))
        stack.enter_context(pk_hooks(
            env,
            _pk_roles=lambda _orig: roles or {'member': {'groups': ('base.group_portal',)}},
            _pk_help_keys=lambda _orig: {},
            _pk_help_tabbed=lambda _orig: (),
            _pk_search_providers=lambda _orig: [],
        ))
        from odoo.addons.bemade_portal_kit.models.portal_kit import PortalKit
        kit_cls = type(env['portal.kit'])
        env.registry.clear_cache()
        stack.enter_context(patch.object(kit_cls, '_pk_pages', lambda self: PortalKit._pk_pages(self)))
        stack.enter_context(patch.object(kit_cls, '_pk_nav', lambda self: []))
        stack.callback(env.registry.clear_cache)
        stack.enter_context(patch.object(kit_cls, '_pk_layout', lambda self: layout))
        stack.enter_context(patch.object(kit_cls, '_pk_help_url', lambda self, url: url))
        stack.enter_context(patch.object(kit_cls, '_pk_pref_fields', lambda self: {
            'pk_theme': ('light', 'dark'), 'pk_show_done_buttons': ('1', '0'), 'lang': None}))
        stack.enter_context(patch.object(kit_cls, '_pk_account_phone', lambda self, phone, country=None: phone))
        params = env['ir.config_parameter'].sudo()
        params.set_param('bemade_portal_kit.enabled', 'True')
        yield
