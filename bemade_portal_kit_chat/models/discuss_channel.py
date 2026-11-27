# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5516: managed channels, the reply-only rule and the core gates on
``discuss.channel``.

* ``pk_managed_key``: set = a channel the consumer manages
  (``portal.kit._pk_chat_sync``); unique when set.
* Reply-only (uid-based, every route): in a managed channel a member whose
  role is ``reader`` may only post a ``comment`` whose parent is a message
  of the same channel (``message_post``; raw ``mail.message.create`` in
  ``mail_message.py``). Posters and internal users are unrestricted.
* Direct chats: a share user never creates one through Discuss
  (``_get_or_create_chat``); the kit's route does, after its contacts check
  (context ``pk_chat_start``).
* Discuss's own mention / ``@everyone`` e-mail to SHARE partners is dropped
  in chats and groups: their e-mail comes from the kit's preferences only.
* Task 5546, phone (Web Push) in chats and groups: Discuss pushes every
  member's devices; a SHARE member keeps the push only when the chat is on
  for their app and the phone switch of THIS message's kind for THEM
  (``portal.kit._pk_chat_kind``, the e-mail's logic: a reader hears only
  announcements and the replies in their threads) is on. Their payload
  carries ``data.pk_url`` (the conversation) and never lists member names;
  a member whose phone was pushed gets ``pk_pushed_message_id`` (the « each »
  e-mail skips it). Internal members: Odoo's own push, payload and all,
  exactly as before.
* Task 5566, a CLOSED managed channel (``pk_closed``, set by the sync from
  the hook's ``closed: True``): still listed and readable, but nobody posts,
  edits or deletes in it (``_pk_chat_check_open``: ``message_post``, raw
  ``mail.message.create``, ``_message_update_content``, a new sub-thread;
  reactions stay).
  The rule is by uid, so the core's ``sudo()`` routes refuse too; only the
  superuser (``__system__``: crons, server code run as it) may still post.
  A message newer than the closing (``pk_closed_message_id``, the last
  message when it closed) notifies nobody: no e-mail, inbox or push.
  Discuss gets ``pk_closed`` / ``pk_closed_label`` in its store (and live,
  ``_sync_field_names``) to hide its composer.
* Task 5520, a READER (share user, ``pk_role='reader'``) of a managed
  channel uses the KIT only and never learns the other members:
  - ``security/pk_chat_reader_rules.xml`` (global rules): the channel and its
    sub-channels are invisible to them through the ORM (so every Discuss
    route, ``/mail/data`` and call_kw on it answer « not found » / access
    error, and its messages fail the core's document check), and of its
    members they read only their own row. The kit reads in ``sudo()``.
  - the store sent to them (``_to_store_defaults`` with a reader target)
    drops the members, the count, the invitations, the calls and the uuid
    (``PK_READER_HIDDEN_FIELDS``), a backstop to the rules;
  - their posts never carry ``partner_ids`` / ``special_mentions`` (the
    mention oracle), ``execute_command_who`` / ``_help`` are refused;
  - the bus (``bus_bus.py``, ``ir_websocket.py``) gives them a content-free
    ``pk_chat.ping`` instead of the channel's broadcasts;
  - the phone's title of another reader's message is ``<group> - <alias>``
    with the neutral avatar (``portal.kit._pk_chat_author_for``).
  Posters and internal users: vanilla.
"""
from odoo import SUPERUSER_ID, _, fields, models
from odoo.exceptions import AccessError

from odoo.addons.mail.tools.discuss import Store

PK_CHAT_TYPES = ('chat', 'group')
PK_CHAT_NEUTRAL_AVATAR = '/base/static/img/avatar_grey.png'  # task 5520: the alias's avatar
# Task 5520: what a reader's store never carries about a managed channel.
PK_READER_HIDDEN_FIELDS = frozenset({
    'channel_member_ids', 'channel_name_member_ids', 'invited_member_ids', 'member_count',
    'rtc_session_ids', 'uuid', 'create_uid', 'from_message_id', 'parent_channel_id', 'description',
})


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    pk_managed_key = fields.Char(
        string="Portal Kit Managed Key", index='btree_not_null', copy=False, readonly=True,
        help="Set: a group channel managed by a portal kit consumer (members and roles are synced).")

    pk_closed = fields.Boolean(
        string="Portal Kit Closed", copy=False, readonly=True,
        help="A managed channel the consumer closed: listed and readable, nobody may write in it.")
    pk_closed_label = fields.Char(
        string="Portal Kit Closed Label", copy=False, readonly=True,
        help="The consumer's label of the closed state (empty: « Ended »).")
    pk_closed_message_id = fields.Many2one(
        'mail.message', string="Portal Kit Last Message Before Closing", copy=False, readonly=True,
        ondelete='set null', help="Messages after this one notify nobody.")

    _pk_managed_key_unique = models.Constraint(
        'UNIQUE(pk_managed_key)',
        'A managed key names one channel only.',
    )

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------
    def _pk_chat_member_of(self, partner):
        """The member of ``partner`` in this channel (sudo), or an empty
        recordset."""
        self.ensure_one()
        return self.env['discuss.channel.member'].sudo().search(
            [('channel_id', '=', self.id), ('partner_id', '=', partner.id)], limit=1)

    def _pk_chat_is_reader(self, user=None):
        """Is ``user`` (default: the current user) a reader of this managed
        channel? Internal users never are."""
        self.ensure_one()
        user = user or self.env.user
        if not self.sudo().pk_managed_key or user._is_internal() or user._is_public():
            return False
        return self._pk_chat_member_of(user.partner_id).pk_role == 'reader'

    def _pk_chat_managed_root(self):
        """Task 5520: the managed channel this channel is (or is a
        sub-channel of), sudo; else an empty recordset."""
        self.ensure_one()
        channel = self.sudo()
        if channel.pk_managed_key:
            return channel
        if channel.parent_channel_id.pk_managed_key:
            return channel.parent_channel_id
        return self.browse().sudo()

    def _pk_chat_reader_channel_ids(self, user=None):
        """Task 5520: the ids of the channels of ``self`` hidden from
        ``user`` (default: the current user): a SHARE user who is a reader of
        the managed channel (or of the managed parent of a sub-channel).
        Internal users and posters: none."""
        user = user if user is not None else self.env.user
        if not self or not user or not user.share or user._is_public():
            return set()
        roots = {}
        for channel in self:
            root = channel._pk_chat_managed_root()
            if root:
                roots[channel.id] = root.id
        if not roots:
            return set()
        readers = set(self.env['discuss.channel.member'].sudo().search([
            ('channel_id', 'in', list(set(roots.values()))),
            ('partner_id', '=', user.partner_id.id),
            ('pk_role', '=', 'reader'),
        ]).channel_id.ids)
        return {channel_id for channel_id, root_id in roots.items() if root_id in readers}

    def _pk_chat_check_not_reader(self):
        """Task 5520: raise ``AccessError`` for a reader of this managed
        channel (or of its managed parent)."""
        if self._pk_chat_reader_channel_ids():
            raise AccessError(_("This is not available in this group."))

    def _pk_chat_check_open(self):
        """Task 5566: raise ``AccessError`` when this managed channel is
        closed, for every user (internal included, ``sudo()`` included: the
        uid decides) but the superuser."""
        self.ensure_one()
        if self.sudo().pk_closed and self.env.uid != SUPERUSER_ID:
            raise AccessError(_("This conversation is closed."))

    def _pk_chat_closed_label(self):
        """The closed chip's text: the consumer's label, else « Ended »."""
        self.ensure_one()
        return self.sudo().pk_closed_label or self.env._("Ended")

    def _pk_chat_after_close(self, message):
        """Task 5566: ``message`` came after the closing of this channel
        (it notifies nobody)."""
        self.ensure_one()
        channel = self.sudo()
        return bool(channel.pk_closed and message and message.id > (channel.pk_closed_message_id.id or 0))

    def _pk_chat_check_post(self, message_type, parent_id):
        """Raise ``AccessError`` when the current user may not post this
        message here: a closed channel (task 5566), or a reader's anything
        but a reply (``comment`` whose parent is a message of this
        channel)."""
        self.ensure_one()
        self._pk_chat_check_open()
        if not self._pk_chat_is_reader():
            return
        if message_type == 'comment' and parent_id:
            parent = self.env['mail.message'].sudo().browse(int(parent_id)).exists()
            if parent and parent.model == self._name and parent.res_id == self.id:
                return
        raise AccessError(_("In this group you can only reply to a message."))

    def message_post(self, *, message_type="notification", partner_ids=None, **kwargs):
        for channel in self:
            channel._pk_chat_check_post(message_type, kwargs.get('parent_id'))
        if self._pk_chat_reader_channel_ids():
            # Task 5520: a reader mentions nobody (``_get_allowed_message_partner_ids``
            # keeps only members: a membership oracle), nor « @everyone ».
            partner_ids = None
            kwargs.pop('special_mentions', None)
        return super().message_post(message_type=message_type, partner_ids=partner_ids, **kwargs)

    def _message_update_content(self, message, /, **kwargs):
        # Task 5566: no edit, no delete (an empty update) in a closed channel.
        self._pk_chat_check_open()
        return super()._message_update_content(message, **kwargs)

    def execute_command_who(self, **kwargs):
        # Task 5520: the member list, refused to a reader.
        self._pk_chat_check_not_reader()
        return super().execute_command_who(**kwargs)

    def execute_command_help(self, **kwargs):
        # Task 5520: « a private conversation with <members> », refused to a reader.
        self._pk_chat_check_not_reader()
        return super().execute_command_help(**kwargs)

    def _create_sub_channel(self, from_message_id=None, name=None):
        # Task 5566: no new sub-thread (a place to write) in a closed channel.
        self._pk_chat_check_open()
        return super()._create_sub_channel(from_message_id=from_message_id, name=name)

    # ------------------------------------------------------------------
    # Task 5566: the closed state in Discuss's store
    # ------------------------------------------------------------------
    def _pk_chat_store_fields(self):
        managed = lambda channel: bool(channel.pk_managed_key)  # noqa: E731
        return [Store.Attr('pk_closed', predicate=managed), Store.Attr('pk_closed_label', predicate=managed)]

    def _to_store_defaults(self, target):
        fields = super()._to_store_defaults(target) + self._pk_chat_store_fields()
        hidden = self._pk_chat_reader_channel_ids(target.get_user(self.env))
        return self._pk_chat_strip_store_fields(fields, hidden) if hidden else fields

    @staticmethod
    def _pk_chat_strip_store_fields(fields, hidden_ids):
        """Task 5520: ``fields`` without ``PK_READER_HIDDEN_FIELDS`` for the
        channels of ``hidden_ids`` (a predicate per record: a store may mix
        channels)."""
        def keep(channel):
            return channel.id not in hidden_ids

        res = []
        for field in fields:
            name = field if isinstance(field, str) else getattr(field, 'field_name', None)
            if name not in PK_READER_HIDDEN_FIELDS:
                res.append(field)
            elif isinstance(field, str):
                res.append(Store.Attr(field, predicate=keep))
            else:
                original = field.predicate
                field.predicate = (lambda c, original=original: keep(c) and original(c)) if original else keep
                res.append(field)
        return res

    def _sync_field_names(self):
        res = super()._sync_field_names()
        res[None] += self._pk_chat_store_fields()
        return res

    # ------------------------------------------------------------------
    # Direct chats: through the kit route only for share users
    # ------------------------------------------------------------------
    def _get_or_create_chat(self, partners_to, pin=True):
        if self.env.user.share and not self.env.context.get('pk_chat_start'):
            raise AccessError(_("Start a conversation from the portal."))
        return super()._get_or_create_chat(partners_to, pin=pin)

    # ------------------------------------------------------------------
    # No Discuss mention e-mail to share partners in chats and groups
    # ------------------------------------------------------------------
    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals=msg_vals, **kwargs)
        if self.channel_type not in PK_CHAT_TYPES:
            return recipients
        if self._pk_chat_after_close(message):
            return []  # task 5566: nothing after the closing (e-mail, inbox, push)
        return [r for r in recipients if not (r.get('notif') == 'email' and (r.get('share') or r.get('ushare')))]

    # ------------------------------------------------------------------
    # Task 5546: the phone (Web Push)
    # ------------------------------------------------------------------
    def _pk_chat_push_members(self, message, recipients):
        """The members (sudo) of the SHARE partners of ``recipients`` (web
        push recipients) whose phone hears ``message``."""
        self.ensure_one()
        kit = self.env['portal.kit']
        members = self.env['discuss.channel.member'].sudo()
        if not kit._pk_shell_enabled() or not recipients:
            return members
        candidates = members.search([
            ('channel_id', '=', self.id), ('partner_id', 'in', [r['id'] for r in recipients])])
        for member in candidates:
            user = kit._pk_chat_user(member)
            if not user or not user.share:
                continue
            if not kit._pk_chat_enabled(kit._pk_app(user) or None):
                continue
            kind = kit._pk_chat_kind(member, message)
            if kind and user._pk_notification_push(kind):
                members |= member
        return members

    def _notify_thread_by_web_push(self, message, recipients_data, msg_vals=False, **kwargs):
        if self.channel_type not in PK_CHAT_TYPES:
            return super()._notify_thread_by_web_push(message, recipients_data, msg_vals=msg_vals, **kwargs)
        share = [r for r in recipients_data if r.get('share') or r.get('ushare')]
        internal = [r for r in recipients_data if not (r.get('share') or r.get('ushare'))]
        super()._notify_thread_by_web_push(message, internal, msg_vals=msg_vals, **kwargs)
        members = self._pk_chat_push_members(message, [r for r in share if r.get('notif') == 'web_push'])
        if not members:
            return None
        devices = self.env['mail.push.device'].sudo().search([('partner_id', 'in', members.partner_id.ids)])
        if devices:
            members.filtered(lambda m: m.partner_id in devices.partner_id).write(
                {'pk_pushed_message_id': message.id})
        # Task 5520: the readers for whom the author is another reader get
        # the alias (title and icon), in their own batch.
        author = self.env['res.partner'].sudo().browse((msg_vals or {}).get('author_id') or message.author_id.id)
        kit = self.env['portal.kit']
        aliased = members.filtered(lambda m: kit._pk_chat_hides_author(m, author))
        for batch, alias in ((members - aliased, False), (aliased, True)):
            kept = [r for r in share if r.get('notif') == 'web_push' and r['id'] in batch.partner_id.ids]
            if kept:
                super(DiscussChannel, self.with_context(pk_chat_push=True, pk_chat_push_alias=alias)
                      )._notify_thread_by_web_push(message, kept, msg_vals=msg_vals, **kwargs)
        return None

    def _notify_by_web_push_prepare_payload(self, message, msg_vals=False, force_record_name=False):
        payload = super()._notify_by_web_push_prepare_payload(
            message, msg_vals=msg_vals, force_record_name=force_record_name)
        if not self.env.context.get('pk_chat_push') or self.channel_type not in PK_CHAT_TYPES:
            return payload
        payload['options']['data']['pk_url'] = '/my/app/conversations/%s' % self.id
        alias = self.env.context.get('pk_chat_push_alias')
        author_id = (msg_vals or {}).get('author_id') or message.author_id.id
        if self.channel_type == 'group':
            if alias:  # task 5520: another reader's message, for a reader
                author = self.env['portal.kit']._pk_chat_reader_alias(self)
            else:
                author = self.env['res.partner'].browse(author_id).name if author_id else ''
            name = self.name or _("Conversation")
            payload['title'] = '%s - %s' % (name, author) if author else name
        if alias:
            payload['options']['icon'] = PK_CHAT_NEUTRAL_AVATAR
        elif author_id:
            payload['options']['icon'] = '/my/app/chat/%s/avatar/%s' % (self.id, author_id)
        return payload
