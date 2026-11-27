# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers: the installable app as this addon alone draws it, whatever
consumer is installed. Synthetic content only."""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from odoo.addons.bemade_portal_kit.tests.common import pk_kit_shell

# The hooks a consumer may override; the tests use this addon's own.
PWA_HOOKS = ('_pk_nav', '_pk_pages', '_pk_help_keys', '_pk_pwa_start_url', '_pk_pwa_manifest_id',
             '_pk_pwa_shortcuts', '_pk_pwa_offline_style')


@contextmanager
def pk_pwa_shell(env, roles=None):
    """``pk_kit_shell`` (the kit's pages, synthetic roles, switch on) + this
    addon's nav entry, page and hooks (a consumer's overrides set aside), and
    the current company's app fields emptied (the defaults)."""
    from odoo.addons.bemade_portal_kit_pwa.models.portal_kit import PK_PWA_FIELDS, PortalKit
    kit_cls = type(env['portal.kit'])
    with ExitStack() as stack:
        stack.enter_context(pk_kit_shell(env, roles=roles))
        for hook in PWA_HOOKS:
            stack.enter_context(patch.object(kit_cls, hook, getattr(PortalKit, hook)))
        env.registry.clear_cache()
        stack.callback(env.registry.clear_cache)
        env.company.write(dict.fromkeys(PK_PWA_FIELDS, False))
        yield
