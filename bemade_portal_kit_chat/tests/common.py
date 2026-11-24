# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Test helpers: the chat as this addon alone draws it, whatever consumer
is installed (one app per instance; the CI installs every consumer), with
SYNTHETIC people only.

``pk_chat_shell(env, contacts=, managed=)``: ``pk_kit_shell`` + a synthetic
app ``pkchat`` with the chat on (portal users hold its role), the contacts
hook ``contacts(kit, user) -> partners`` and the managed channels hook
``managed(kit) -> [...]`` (default: nobody, none)."""
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from odoo.tests import new_test_user

from odoo.addons.bemade_portal_kit.tests.common import pk_hook, pk_kit_shell

APP = 'pkchat'
ROLES = {'pkchat_member': {'groups': ('base.group_portal',), 'app': APP}}


@contextmanager
def pk_chat_shell(env, contacts=None, managed=None, chat=True):
    kit_cls = type(env['portal.kit'])
    with ExitStack() as stack:
        stack.enter_context(pk_kit_shell(env, roles=ROLES))
        stack.enter_context(pk_hook(env, '_pk_apps', lambda _orig: {APP: {'chat': chat}}))
        stack.enter_context(patch.object(
            kit_cls, '_pk_chat_contacts',
            lambda self, user: contacts(self, user) if contacts else self.env['res.partner']))
        stack.enter_context(patch.object(
            kit_cls, '_pk_chat_managed_channels', lambda self: managed(self) if managed else []))
        env.registry.clear_cache()
        stack.callback(env.registry.clear_cache)
        yield


def pk_chat_people(cls):
    """Synthetic people on ``cls``: two portal users (Avery, Blake), a third
    (Casey) and an internal user (Dana, staff)."""
    env = cls.env
    cls.avery = new_test_user(env, login='pkc_avery', name='Avery Testperson', groups='base.group_portal',
                              lang='en_US', email='pkc_avery@example.com', tz='America/Toronto')
    cls.blake = new_test_user(env, login='pkc_blake', name='Blake Testperson', groups='base.group_portal',
                              lang='en_US', email='pkc_blake@example.com', tz='America/Toronto')
    cls.casey = new_test_user(env, login='pkc_casey', name='Casey Testperson', groups='base.group_portal',
                              lang='en_US', email='pkc_casey@example.com', tz='America/Toronto')
    cls.dana = new_test_user(env, login='pkc_dana', name='Dana Staffperson', groups='base.group_user',
                             lang='en_US', email='pkc_dana@example.com', tz='America/Toronto')
    for user in (cls.avery, cls.blake, cls.casey, cls.dana):
        user.partner_id.phone = '+1 555 0100'


def everyone(kit, user):
    """Contacts: every synthetic person but the user."""
    return kit.env['res.partner'].sudo().search([('user_ids.login', 'like', 'pkc_%')]) - user.partner_id


def enter(case, ctx):
    ctx.__enter__()
    case.addCleanup(ctx.__exit__, None, None, None)
