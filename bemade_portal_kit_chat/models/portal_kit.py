# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the chat's hooks on ``portal.kit`` (all off by default).

* ``_pk_chat_enabled(app)``: the chat is on for ``app`` (default: its
  ``_pk_apps()`` registration's ``'chat'`` key);
* ``_pk_chat_contacts(user)``: the partners ``user`` may START a direct
  chat with (consumer policy; never cached: per user);
* ``_pk_chat_managed_channels()``: ``[{key, name, app?, members:
  {partner_id: 'poster' | 'reader'}}]``, the group channels the consumer
  manages (read through ``pk_chat_managed_channels(app)``; never cached:
  members are data);
* ``_pk_chat_sync(key=None)``: makes the database match the hook, silently.

The chat registers three notification kinds (kit 1.17) for the apps where
it is on: ``chat.direct``, ``chat.announcement``, ``chat.reply``; each has
a phone switch (task 5546, kit 1.18: ``'push': True``). The app icon's
number (``_pk_app_badge_count``) is the viewer's unread messages.
"""
import logging

from odoo import api, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import Page, pk_app_scoped, pk_static_page

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

ROLES = ('poster', 'reader')
KIND_DIRECT = 'chat.direct'
KIND_ANNOUNCEMENT = 'chat.announcement'
KIND_REPLY = 'chat.reply'
CHAT_KINDS = (KIND_DIRECT, KIND_ANNOUNCEMENT, KIND_REPLY)
MODES = ('each', 'digest', 'off')


def _chat_enabled(kit, app):
    return kit._pk_chat_enabled(app)


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_enabled(self, app=None):
        """Is the chat on for ``app`` (default: the current app)? Default:
        the app's registration says ``'chat': True``."""
        return bool(self.pk_app_spec(app).get('chat'))

    @api.model
    def _pk_chat_contacts(self, user):
        """The partners (``res.partner``) ``user`` may start a direct chat
        with. Consumer policy; default: nobody."""
        return self.env['res.partner']

    @api.model
    def _pk_chat_managed_channels(self):
        """``[{'key', 'name', 'app', 'members': {partner_id: role}}]``: the
        group channels the consumer manages (``role``: ``'poster'`` or
        ``'reader'``). Default: none."""
        return []

    @api.model
    def _pk_pages(self):
        return super()._pk_pages() + [
            # A sub-page of « More » (like the kit's « Settings »): every
            # page of an app but its tabs has a parent.
            pk_static_page('pk_chat_page_list', '/my/app/conversations', _lt("Conversations"),
                           parent=lambda v: ('pk_app_more', {})),
            Page('pk_chat_page_conversation',
                 label=lambda v: v.get('pk_chat_title') or '',
                 url=lambda v: '/my/app/conversations/%s' % v.get('pk_chat_channel_id'),
                 parent=lambda v: ('pk_chat_page_list', {})),
        ]

    @api.model
    def _pk_notification_kinds(self):
        kinds = super()._pk_notification_kinds()
        return kinds + [
            {'key': KIND_DIRECT, 'label': _lt("Direct messages"), 'modes': MODES,
             'default': 'each', 'default_internal': 'off', 'sequence': 50, 'enabled': _chat_enabled, 'push': True},
            {'key': KIND_ANNOUNCEMENT, 'label': _lt("Group announcements"), 'modes': MODES,
             'default': 'digest', 'default_internal': 'off', 'sequence': 51, 'enabled': _chat_enabled, 'push': True},
            {'key': KIND_REPLY, 'label': _lt("Replies in groups"), 'modes': MODES,
             'default': 'digest', 'default_internal': 'off', 'sequence': 52, 'enabled': _chat_enabled, 'push': True},
        ]

    @api.model
    def _pk_app_badge_count(self, user=None):
        """Task 5546: the unread chat messages, while the chat is on for
        the user's app."""
        count = super()._pk_app_badge_count(user=user)
        user = user or self.env.user
        if self._pk_shell_enabled() and self._pk_chat_enabled(self._pk_app(user) or None):
            count += self.pk_chat_unread_count(user)
        return count

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_active(self):
        """The kit's switch is on and the chat is on for the current app:
        the kit routes and pages answer (else 404)."""
        return self._pk_shell_enabled() and self._pk_chat_enabled()

    @api.model
    def pk_chat_managed_channels(self, app=None):
        """The managed channels of ``app`` (default: the current app): the
        shared ones and the app's own."""
        return pk_app_scoped(self._pk_chat_managed_channels(), self._pk_resolve_app(app), lambda spec: spec['key'])

    @api.model
    def pk_chat_contacts(self, user=None):
        """``_pk_chat_contacts(user)`` without ``user``'s own partner."""
        user = user or self.env.user
        return self._pk_chat_contacts(user).filtered(lambda partner: partner != user.partner_id)

    # ------------------------------------------------------------------
    # Managed channels: the sync
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_sync(self, key=None):
        """Make the managed channels match ``_pk_chat_managed_channels()``
        (every app's): create or rename the ``group`` channel of each key,
        add and remove its members, set their roles. ``key`` given: that
        channel only. Without ``key``, a managed channel whose key the hook
        no longer returns is archived (never deleted). Idempotent and
        SILENT: no « joined » / « invited » posts (members are created
        without ``_add_members``' messages), and a new member starts with
        the channel's history read and never e-mailed."""
        Channel = self.env['discuss.channel'].sudo().with_context(active_test=False)
        Member = self.env['discuss.channel.member'].sudo()
        specs = self._pk_chat_managed_channels()
        if key is not None:
            specs = [spec for spec in specs if spec['key'] == key]
        seen = set()
        for spec in specs:
            seen.add(spec['key'])
            wanted = {int(pid): role for pid, role in (spec.get('members') or {}).items() if role in ROLES}
            channel = Channel.search([('pk_managed_key', '=', spec['key'])], limit=1)
            if not channel:
                channel = Channel.create({
                    'name': spec['name'],
                    'channel_type': 'group',
                    'pk_managed_key': spec['key'],
                })
            vals = {}
            if channel.name != spec['name']:
                vals['name'] = spec['name']
            if not channel.active:
                vals['active'] = True
            if vals:
                channel.write(vals)
            members = Member.search([('channel_id', '=', channel.id), ('partner_id', '!=', False)])
            by_partner = {member.partner_id.id: member for member in members}
            stale = members.filtered(lambda m: m.partner_id.id not in wanted)
            if stale:
                stale.unlink()
            for member in members - stale:
                if member.pk_role != wanted[member.partner_id.id]:
                    member.pk_role = wanted[member.partner_id.id]
            last = self.env['mail.message'].sudo().search(
                [('model', '=', 'discuss.channel'), ('res_id', '=', channel.id)], order='id desc', limit=1)
            for role in ROLES:
                new_partners = self.env['res.partner'].browse(
                    [pid for pid, r in wanted.items() if r == role and pid not in by_partner]).exists()
                if new_partners:
                    params = {'pk_role': role, 'pk_emailed_message_id': last.id or False}
                    if last:
                        params['new_message_separator'] = last.id + 1
                    # The core's own « no joined message » path: the joined
                    # bus notice only (the channel shows up in Discuss).
                    channel._add_members(partners=new_partners, create_member_params=params,
                                         post_joined_message=False)
        if key is None:
            orphans = Channel.search([('pk_managed_key', '!=', False), ('pk_managed_key', 'not in', list(seen)),
                                      ('active', '=', True)])
            if orphans:
                orphans.write({'active': False})
        return True

    @api.model
    def _pk_chat_cron_sync(self):
        """The nightly sync (``ir.cron``)."""
        self._pk_chat_sync()

