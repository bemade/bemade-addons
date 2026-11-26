# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: the chat's e-mails, driven by each user's notification
preferences (kit 1.17).

* « each » (cron every 5 minutes): for each member of a chat / group, the
  comment messages newer than ``max(seen, already e-mailed, the unread
  separator)``, not their own, older than ``PK_CHAT_MAIL_DELAY`` (10
  minutes; a conversation read in the meantime is not mailed), that the
  member's mode for the message's kind is « each » for: ONE e-mail per
  conversation, then ``pk_emailed_message_id`` moves past them.
* « digest » (cron hourly): at 07:00 in the user's time (or the first run
  after), once per day (``pk_digest_date``), one e-mail listing every
  unread conversation of a kind in « digest » mode; nothing when nothing
  is unread.
* « off »: nothing.
* Task 5546: a message sent to the member's phone (Web Push, up to
  ``pk_pushed_message_id``) is not « each » e-mailed; the digest ignores the
  phone (owner decision).

Kinds: a direct chat's messages are ``chat.direct``; in a group a message
without parent is ``chat.announcement``, a reply ``chat.reply`` (a poster
or normal member hears every reply; a reader the replies to a message they
replied to or wrote).
"""
import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models

from .discuss_channel import PK_CHAT_TYPES
from .portal_kit import KIND_ANNOUNCEMENT, KIND_DIRECT, KIND_REPLY
from .pk_chat_data import pk_chat_excerpt

_logger = logging.getLogger(__name__)

PK_CHAT_MAIL_DELAY = timedelta(minutes=10)
PK_CHAT_DIGEST_HOUR = 7


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_mail_members(self):
        """Every member (sudo) of an active chat / group whose partner has
        an active user."""
        return self.env['discuss.channel.member'].sudo().search([
            ('channel_id.channel_type', 'in', PK_CHAT_TYPES),
            ('channel_id.active', '=', True),
            ('partner_id.user_ids.active', '=', True),
        ])

    @api.model
    def _pk_chat_user(self, member):
        return member.partner_id.user_ids.filtered('active')[:1]

    @api.model
    def _pk_chat_kind(self, member, message):
        """The kind of ``message`` for ``member``, or None when the member
        is not told about it (a reader and someone else's thread)."""
        if member.channel_id.channel_type == 'chat':
            return KIND_DIRECT
        if not message.parent_id:
            return KIND_ANNOUNCEMENT
        if member.pk_role != 'reader':
            return KIND_REPLY
        parent = message.parent_id
        partner = member.partner_id
        if parent.author_id == partner:
            return KIND_REPLY
        mine = self.env['mail.message'].sudo().search_count([
            ('model', '=', 'discuss.channel'), ('res_id', '=', member.channel_id.id),
            ('parent_id', '=', parent.id), ('author_id', '=', partner.id)], limit=1)
        return KIND_REPLY if mine else None

    @api.model
    def _pk_chat_floor(self, member):
        return max(member.seen_message_id.id or 0, member.pk_emailed_message_id.id or 0,
                   (member.new_message_separator or 1) - 1)

    @api.model
    def _pk_chat_url(self, channel=None):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        path = '/my/app/conversations' + ('/%s' % channel.id if channel else '')
        return base.rstrip('/') + path

    @api.model
    def _pk_chat_send(self, user, subject, template, values, record_name):
        """One e-mail to ``user``: ``template`` (QWeb) in the light layout,
        in the user's language. A plain ``mail.mail`` (internal users who
        chose a mode get an e-mail too, not an inbox notice)."""
        env = self.with_context(lang=user.lang).env
        body = env['ir.qweb']._render(template, dict(values, user=user))
        company = user.company_id or env.company
        html = env['mail.render.mixin']._render_encapsulate('mail.mail_notification_light', body, add_context={
            'company': company,
            'model_description': env._("conversation"),
            'record_name': record_name,
        })
        email_from = company.partner_id.email_formatted or env['ir.mail_server']._get_default_from_address()
        return env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': html,
            'email_from': email_from,
            'recipient_ids': [(4, user.partner_id.id)],
            'auto_delete': True,
        })

    # ------------------------------------------------------------------
    # « each »
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_cron_each(self, now=None):
        now = now or fields.Datetime.now()
        cutoff = now - PK_CHAT_MAIL_DELAY
        sent = 0
        for member in self._pk_chat_mail_members():
            user = self._pk_chat_user(member)
            if not user:
                continue
            channel = member.channel_id
            messages = self._pk_chat_comments(channel, [
                ('id', '>', self._pk_chat_floor(member)), ('date', '<=', cutoff)], order='id asc')
            if not messages:
                continue
            pushed = member.pk_pushed_message_id.id or 0
            mail = messages.filtered(
                lambda m: m.author_id != member.partner_id
                and m.id > pushed  # task 5546: on the phone already
                and (kind := self._pk_chat_kind(member, m))
                and user._pk_notification_mode(kind) == 'each')
            if mail:
                with self.env.cr.savepoint():
                    self._pk_chat_mail_each(user, member, mail)
                sent += 1
            member.pk_emailed_message_id = messages[-1]
        return sent

    @api.model
    def _pk_chat_mail_each(self, user, member, messages):
        env = self.with_context(lang=user.lang).env
        title = env['portal.kit']._pk_chat_title(member)
        subject = env._("New messages: %s", title) if len(messages) > 1 else env._("New message: %s", title)
        return self._pk_chat_send(user, subject, 'bemade_portal_kit_chat.pk_chat_mail_each', {
            'title': title,
            'messages': [{'author': m.author_id.name or '', 'text': pk_chat_excerpt(m.body, 600),
                          'reply_to': m.parent_id.author_id.name if m.parent_id else ''} for m in messages],
            'url': self._pk_chat_url(member.channel_id),
        }, title)

    # ------------------------------------------------------------------
    # « digest »
    # ------------------------------------------------------------------
    @api.model
    def _pk_chat_member_kinds(self, member):
        if member.channel_id.channel_type == 'chat':
            return (KIND_DIRECT,)
        return (KIND_ANNOUNCEMENT, KIND_REPLY)

    @api.model
    def _pk_chat_cron_digest(self, now=None):
        now = now or fields.Datetime.now()
        sent = 0
        members_by_user = {}
        for member in self._pk_chat_mail_members():
            user = self._pk_chat_user(member)
            if user:
                members_by_user.setdefault(user, self.env['discuss.channel.member'].sudo())
                members_by_user[user] |= member
        for user, members in members_by_user.items():
            tz = pytz.timezone(user.tz or self.env.company.partner_id.tz or 'UTC')
            local = pytz.utc.localize(now).astimezone(tz)
            if local.hour < PK_CHAT_DIGEST_HOUR:
                continue
            today = local.date()
            if any(member.pk_digest_date == today for member in members):
                continue
            rows = []
            for member in members:
                if member.message_unread_counter <= 0:
                    continue
                if not any(user._pk_notification_mode(kind) == 'digest' for kind in self._pk_chat_member_kinds(member)):
                    continue
                last = self._pk_chat_comments(member.channel_id, limit=1)
                rows.append({
                    'title': self.with_context(lang=user.lang)._pk_chat_title(member),
                    'count': member.message_unread_counter,
                    'author': last.author_id.name or '',
                    'excerpt': pk_chat_excerpt(last.body),
                    'url': self._pk_chat_url(member.channel_id),
                })
            members.write({'pk_digest_date': today})
            if not rows:
                continue
            env = self.with_context(lang=user.lang).env
            with self.env.cr.savepoint():
                self._pk_chat_send(user, env._("Your unread conversations"), 'bemade_portal_kit_chat.pk_chat_mail_digest', {
                    'rows': rows, 'url': self._pk_chat_url(),
                }, env._("Your conversations"))
            sent += 1
        return sent
