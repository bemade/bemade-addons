# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: what the kit routes answer, built for ONE viewer.

The portal UI talks only to the kit routes; these builders decide what a
viewer may see: comment messages only, the authors' names, no e-mail or
phone anywhere, and no member list (nor count) for a reader of a managed
channel. Internal users see whatever vanilla Discuss shows them.

Task 5566: a closed managed channel's row and thread say so (``closed``,
``closed_label``); its rows come after the open ones (most recent first),
its thread has no composer (``composer: 'none'``) and no « Reply »; its
unread messages still count.

Task 5520: a READER of a managed channel never learns who the other
readers are. ``_pk_chat_author_for(member, partner)`` is the ONE place that
decides what a viewer sees of an author: another reader (or a former
member) is ``portal.kit._pk_chat_reader_alias(channel)`` with
``PK_CHAT_NEUTRAL_AVATAR``; the viewer's own messages, the posters' and
internal users' keep their names. The thread, the quoted parent, the
e-mails, the phone's title and the avatar route all use it.
"""
from datetime import datetime, timedelta

import pytz
from babel.dates import format_date, format_time

from odoo import api, models
from odoo.tools import html2plaintext
from odoo.tools.misc import babel_locale_parse

from .discuss_channel import PK_CHAT_NEUTRAL_AVATAR, PK_CHAT_TYPES

EXCERPT = 90


def pk_chat_tz(env, user):
    """The viewer's tz (``pytz``): the user's, else the company's, else UTC;
    an unknown name is UTC. Never raises. Task 5582: sudo, a portal user
    cannot read the company's contact."""
    name = user.tz or env.company.sudo().partner_id.tz or 'UTC'
    try:
        return pytz.timezone(name)
    except pytz.UnknownTimeZoneError:
        return pytz.utc


def pk_chat_when(env, dt, user=None, now=None):
    """``dt`` (naive UTC) for the viewer, CPAS style: the time today,
    « Yesterday », the weekday within the week, else day and month (and the
    year when it is not this year). The viewer's tz, else the company's."""
    if not dt:
        return ''
    user = user or env.user
    tz = pk_chat_tz(env, user)
    local = pytz.utc.localize(dt).astimezone(tz)
    today = (now or pytz.utc.localize(datetime.utcnow())).astimezone(tz).date()
    locale = babel_locale_parse(user.lang or env.lang or 'en_US')
    day = local.date()
    if day == today:
        return format_time(local, format='short', locale=locale)
    if day == today - timedelta(days=1):
        return env._("Yesterday")
    if today - timedelta(days=6) <= day < today:
        return format_date(day, format='EEEE', locale=locale).capitalize()
    if day.year == today.year:
        return format_date(day, format='d MMM', locale=locale)
    return format_date(day, format='d MMM y', locale=locale)


def pk_chat_excerpt(body, size=EXCERPT):
    text = ' '.join(html2plaintext(body or '').split())
    return text if len(text) <= size else text[:size - 1].rstrip() + '…'


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    # ------------------------------------------------------------------
    # The viewer's members and conversations
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_members(self, user=None):
        """The viewer's members (sudo) in active chats and groups."""
        user = user or self.env.user
        return self.env['discuss.channel.member'].sudo().search([
            ('partner_id', '=', user.partner_id.id),
            ('channel_id.channel_type', 'in', PK_CHAT_TYPES),
            ('channel_id.active', '=', True),
        ])

    @api.model
    def _pk_chat_member(self, channel_id, user=None):
        """The viewer's member (sudo) of chat / group ``channel_id``, or an
        empty recordset (the routes answer 404)."""
        user = user or self.env.user
        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return self.env['discuss.channel.member']
        return self.env['discuss.channel.member'].sudo().search([
            ('partner_id', '=', user.partner_id.id),
            ('channel_id', '=', channel_id),
            ('channel_id.channel_type', 'in', PK_CHAT_TYPES),
            ('channel_id.active', '=', True),
        ], limit=1)

    @api.model
    def _pk_chat_comments(self, channel, domain=None, order='id desc', limit=None):
        return self.env['mail.message'].sudo().search(
            [('model', '=', 'discuss.channel'), ('res_id', '=', channel.id), ('message_type', '=', 'comment')]
            + (domain or []), order=order, limit=limit)

    @api.model
    def _pk_chat_other(self, member):
        """The other person of a direct chat (sudo partner)."""
        others = member.channel_id.sudo().channel_member_ids.partner_id - member.partner_id
        return others[:1]

    @api.model
    def _pk_chat_title(self, member):
        channel = member.channel_id.sudo()
        if channel.channel_type == 'chat':
            return self._pk_chat_other(member).name or channel.name
        return channel.name

    @api.model
    def _pk_chat_viewer_is_reader(self, member):
        """Task 5520: ``member`` (the viewer's) is a reader of a managed
        channel, for whom the other readers are anonymous. An internal user
        never is (vanilla)."""
        member = member.sudo()
        if member.pk_role != 'reader' or not member.channel_id.pk_managed_key:
            return False
        return not member.partner_id.user_ids.filtered(lambda user: not user.share)

    @api.model
    def _pk_chat_hides_author(self, member, partner):
        """Task 5520: does the viewer ``member`` see ``partner`` (an author)
        only as the alias? Yes when the viewer is a reader and ``partner`` is
        not themselves, not a poster of the channel and not an internal user
        (another reader, or a former member)."""
        if not partner or partner == member.partner_id or not self._pk_chat_viewer_is_reader(member):
            return False
        partner = partner.sudo()
        if partner.user_ids.filtered(lambda user: not user.share):
            return False
        return member.channel_id._pk_chat_member_of(partner).pk_role != 'poster'

    @api.model
    def _pk_chat_author_for(self, member, partner):
        """Task 5520: ``(name, avatar_url)`` of the author ``partner`` for
        the viewer ``member``: the alias and the neutral avatar when it is
        hidden (``_pk_chat_hides_author``), else the name and the kit's
        avatar route."""
        channel = member.channel_id.sudo()
        if not partner:
            return '', ''
        if self._pk_chat_hides_author(member, partner):
            return str(self._pk_chat_reader_alias(channel)), PK_CHAT_NEUTRAL_AVATAR
        return partner.sudo().name or '', self._pk_chat_avatar_url(channel, partner)

    @api.model
    def _pk_chat_avatar_url(self, channel, partner=None):
        if partner:
            return '/my/app/chat/%s/avatar/%s' % (channel.id, partner.id)
        return '/my/app/chat/%s/avatar' % channel.id

    @api.model
    def pk_chat_conversation_rows(self, user=None):
        """The viewer's conversations, the latest activity first:
        ``{id, kind, title, avatar_url, preview, author_is_me, when,
        unread, closed, closed_label}``. Task 5566: the open ones first,
        then the closed ones (each by its latest activity)."""
        user = user or self.env.user
        rows = []
        for member in self._pk_chat_members(user):
            channel = member.channel_id.sudo()
            last = self._pk_chat_comments(channel, limit=1)
            if channel.channel_type == 'chat' and not last and member.unpin_dt:
                continue  # a chat the other one opened and never wrote in
            avatar_partner = self._pk_chat_other(member) if channel.channel_type == 'chat' else None
            preview = pk_chat_excerpt(last.body) if last else ''
            author_is_me = bool(last) and last.author_id == user.partner_id
            if author_is_me:
                preview = self.env._("You: %(preview)s", preview=preview)
            rows.append({
                'id': channel.id,
                'kind': 'direct' if channel.channel_type == 'chat' else 'group',
                'title': self._pk_chat_title(member),
                'avatar_url': self._pk_chat_avatar_url(channel, avatar_partner),
                'preview': preview,
                'author_is_me': author_is_me,
                'when': pk_chat_when(self.env, last.date, user) if last else '',
                'unread': member.message_unread_counter or 0,
                'closed': bool(channel.pk_closed),
                'closed_label': channel._pk_chat_closed_label() if channel.pk_closed else '',
                '_sort': (last.date or channel.create_date) if last else channel.create_date,
            })
        rows.sort(key=lambda row: row['_sort'], reverse=True)
        rows.sort(key=lambda row: row['closed'])  # stable: open first, then closed
        for row in rows:
            del row['_sort']
        return rows

    @api.model
    def pk_chat_unread_count(self, user=None):
        return sum(self._pk_chat_members(user).mapped('message_unread_counter'))

    @api.model
    def _pk_chat_message_row(self, message, member, reader):
        user_partner = member.partner_id
        parent = message.parent_id
        author = message.author_id
        author_name, author_avatar_url = self._pk_chat_author_for(member, author)
        return {
            'id': message.id,
            'author_name': author_name,
            'author_avatar_url': author_avatar_url,
            'body_html': str(message.body or ''),
            'when': pk_chat_when(self.env, message.date),
            'own': author == user_partner,
            'parent': {
                'id': parent.id,
                'author_name': self._pk_chat_author_for(member, parent.author_id)[0],
                'excerpt': pk_chat_excerpt(parent.body, 120),
            } if parent and parent.model == 'discuss.channel' and parent.res_id == member.channel_id.id else None,
            'can_reply': bool(member.channel_id.pk_managed_key) and not member.channel_id.pk_closed,
        }

    @api.model
    def pk_chat_thread(self, member, before=None, after=None, limit=30):
        """The thread of ``member``'s channel for its viewer: ``{id, kind,
        title, managed, closed, closed_label, composer: 'full' | 'reply' |
        'none' (task 5566: a closed channel), messages: [...] (oldest
        first), more}``, plus ``members: [{name, role}]`` for a poster (never for a
        reader)."""
        channel = member.channel_id.sudo()
        reader = member.pk_role == 'reader' and bool(channel.pk_managed_key)
        domain = []
        if before:
            domain.append(('id', '<', int(before)))
        if after:
            domain.append(('id', '>', int(after)))
        limit = max(1, min(int(limit or 30), 100))
        messages = self._pk_chat_comments(channel, domain, order='id asc' if after else 'id desc', limit=limit + 1)
        more = len(messages) > limit
        messages = messages[:limit]
        if not after:
            messages = messages.sorted('id')
        data = {
            'id': channel.id,
            'kind': 'direct' if channel.channel_type == 'chat' else 'group',
            'title': self._pk_chat_title(member),
            'managed': bool(channel.pk_managed_key),
            'closed': bool(channel.pk_closed),
            'closed_label': channel._pk_chat_closed_label() if channel.pk_closed else '',
            'composer': 'none' if channel.pk_closed else ('reply' if reader else 'full'),
            'messages': [self._pk_chat_message_row(message, member, reader) for message in messages],
            'more': more,
        }
        if channel.pk_managed_key and member.pk_role == 'poster':
            data['members'] = [
                {'name': m.partner_id.name, 'role': m.pk_role or 'poster'}
                for m in channel.channel_member_ids.filtered('partner_id').sorted(lambda m: m.partner_id.name or '')
            ]
        return data

    @api.model
    def pk_chat_block_channel(self, channel_id=None, partner_id=None):
        """The channel id the block ``pk_conversation`` shows for the
        viewer: ``channel_id`` when they are a member; ``partner_id``: the
        direct chat with that contact (created after the contacts check);
        else False."""
        if channel_id:
            member = self._pk_chat_member(channel_id)
            return member.channel_id.id if member else False
        if partner_id:
            channel = self.pk_chat_start(partner_id)
            return channel.id if channel else False
        return False

    @api.model
    def pk_chat_start(self, partner_id):
        """The direct chat of the viewer with ``partner_id`` (one per pair:
        found or created), or False when the partner is not one of their
        contacts."""
        try:
            partner_id = int(partner_id)
        except (TypeError, ValueError):
            return False
        if partner_id not in self.pk_chat_contacts().ids:
            return False
        # sudo: a portal user may not create channels; the contacts check
        # above is the policy (the uid is kept: the chat is theirs).
        return self.env['discuss.channel'].sudo().with_context(pk_chat_start=True)._get_or_create_chat(
            [partner_id], pin=True)
