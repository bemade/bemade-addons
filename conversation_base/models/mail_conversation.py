import ast
import re

import psycopg2
from markupsafe import Markup

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.mail import html_to_inner_content

# A message "counts" in the triage facets unless it is a log: a tracking /
# ``_message_log`` entry, i.e. ``notification`` typed *and* carrying neither
# a transport nor an external id. ``message_post`` defaults to
# ``notification``, so quiet-captured stubs and outbound replies (which get
# their ``external_id``/``transport_id`` right after posting) are told apart
# from logs by those two markers. ``user_notification`` is never counted.
_COUNTED_SQL = """
    m.message_type <> 'user_notification'
    AND (m.message_type <> 'notification'
         OR m.transport_id IS NOT NULL
         OR m.external_id IS NOT NULL)
"""
_PREVIEW_LENGTH = 140


class MailConversation(models.Model):
    """A first-class conversation: the triage unit. Independent of any
    single business record -- see ``mail.conversation.link`` for the
    reified, many-to-many relationship to the records a conversation is
    about.

    Owns its messages the ordinary Odoo way (``mail.message.model ==
    'mail.conversation'``, ``res_id == conversation.id``) via
    ``mail.thread``.
    """

    _name = "mail.conversation"
    _description = "Conversation"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "mail.alias.mixin",
    ]
    _order = "id desc"

    name = fields.Char(
        required=True,
        tracking=True,
        help="The conversation's subject/title, used for triage. There is "
        "deliberately no separate 'subject' field: per-message subjects "
        "stay native on mail.message.",
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("snoozed", "Snoozed"),
            ("waiting", "Waiting"),
            ("done", "Done"),
        ],
        default="open",
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Assignee",
        tracking=True,
    )
    team_id = fields.Many2one(
        "mail.conversation.team",
        tracking=True,
    )
    tag_ids = fields.Many2many(
        "mail.conversation.tag",
        "mail_conversation_tag_rel",
        "conversation_id",
        "tag_id",
        string="Tags",
    )
    primary_transport_id = fields.Many2one(
        "conversation.transport",
        help="Soft default transport for this conversation's outbound "
        "replies; individual messages may carry their own transport_id.",
    )
    link_ids = fields.One2many(
        "mail.conversation.link",
        "conversation_id",
        string="Linked Records",
    )
    participant_ids = fields.One2many(
        "mail.conversation.participant",
        "conversation_id",
        string="Participants",
    )
    member_ids = fields.One2many(
        "mail.conversation.member",
        "conversation_id",
        string="Members",
    )

    # ------------------------------------------------------------
    # Triage facets (epic 04). Stored so the list can filter and sort
    # on them. ``last_message_id``/``last_activity``/``unanswered`` are
    # recomputed explicitly from ``_message_post_after_hook`` (see
    # ``_trigger_message_facets``), not through a ``message_ids``
    # dependency: that one would fire for every same-``res_id`` message
    # of any model.
    # ------------------------------------------------------------
    last_message_id = fields.Many2one(
        "mail.message",
        compute="_compute_message_facets",
        store=True,
        readonly=True,
        ondelete="set null",
        help="Latest message on the conversation that is not a "
        "notification (tracking/log) message.",
    )
    last_activity = fields.Datetime(
        compute="_compute_message_facets",
        store=True,
        readonly=True,
        index=True,
        help="Date of the latest non-notification message, or the "
        "conversation's creation date when it has none.",
    )
    unanswered = fields.Boolean(
        compute="_compute_message_facets",
        store=True,
        readonly=True,
        index=True,
        help="True when the latest message that counts (ignoring "
        "notifications, automatic replies and internal notes written by "
        "an internal user) comes from a non-internal party.",
    )
    unassigned = fields.Boolean(
        compute="_compute_unassigned",
        store=True,
        index=True,
    )
    team_snooze_until = fields.Datetime(
        index=True,
        copy=False,
        help="When a team-level snoozed conversation returns to Open. "
        "Cleared whenever the state leaves 'snoozed'.",
    )
    last_message_preview = fields.Char(
        compute="_compute_last_message_preview",
        help="Plain-text snippet of the latest non-notification message.",
    )
    channel_provider = fields.Selection(
        related="primary_transport_id.provider",
        string="Channel",
        readonly=True,
    )
    my_unread = fields.Boolean(
        compute="_compute_my_member_state",
        search="_search_my_unread",
        string="Unread",
    )
    my_handled = fields.Boolean(
        compute="_compute_my_member_state",
        search="_search_my_handled",
        string="Handled by me",
    )
    my_snoozed = fields.Boolean(
        compute="_compute_my_member_state",
        search="_search_my_snoozed",
        string="Snoozed by me",
    )
    my_snooze_until = fields.Datetime(
        compute="_compute_my_member_state",
        string="My snooze until",
    )

    # ------------------------------------------------------------
    # Mail Alias Mixin
    # ------------------------------------------------------------

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values["alias_model_id"] = self.env["ir.model"]._get_id("mail.conversation")
        if self.id:
            values["alias_defaults"] = defaults = ast.literal_eval(
                self.alias_defaults or "{}"
            )
            if self.team_id:
                defaults["team_id"] = self.team_id.id
        return values

    # ------------------------------------------------------------
    # Gateway hygiene -- inbound mail creating/threading into a
    # conversation must populate participants, never followers (see
    # mail.conversation.participant docstring / project invariant).
    # ------------------------------------------------------------

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        conversation = super().message_new(msg_dict, custom_values)
        conversation._sync_participants_from_msg_dict(msg_dict)
        return conversation

    def _sync_participants_from_msg_dict(self, msg_dict):
        """Build ``mail.conversation.participant`` rows from a gateway
        ``msg_dict`` (as produced by ``mail.thread.message_parse``/
        ``message_route``: comma-joined ``to``/``cc`` strings, a resolved
        ``author_id``). Used by ``message_new`` (real inbound via the
        alias) and by ``_route_via_alias`` (a captured stub routed through
        the gateway).
        """
        self.ensure_one()
        author_id = msg_dict.get("author_id")
        author_partner = (
            self.env["res.partner"].browse(author_id) if author_id else False
        )
        self._sync_participants(
            from_email=msg_dict.get("email_from") or msg_dict.get("from"),
            from_partner=author_partner,
            to_emails=tools.email_split(msg_dict.get("to") or ""),
            cc_emails=tools.email_split(msg_dict.get("cc") or ""),
        )

    def _sync_participants_from_stub(self, stub):
        """Build ``mail.conversation.participant`` rows from a normalized
        transport stub (as produced by ``conversation.transport._normalize``:
        ``email_from``/``author``, ``to``/``cc`` as lists). Used when a
        human quiet-captures an inbox item (``_capture_stub``).
        """
        self.ensure_one()
        author_id = stub.get("author_id")
        author_partner = (
            self.env["res.partner"].browse(author_id) if author_id else False
        )
        self._sync_participants(
            from_email=stub.get("email_from") or stub.get("author"),
            from_partner=author_partner,
            to_emails=stub.get("to") or [],
            cc_emails=stub.get("cc") or [],
        )

    def _sync_participants(
        self, from_email=None, from_partner=None, to_emails=None, cc_emails=None
    ):
        """Correct-correspondent mapping (AC8): the From address/partner
        becomes the conversation's ``requester`` participant -- the actual
        correspondent/customer, never the acting/capturing user. To/Cc
        addresses are added as ``to``/``cc`` participants. Dedup and
        partner resolution both key off ``email_normalized``; never calls
        ``message_subscribe``.
        """
        self.ensure_one()
        Participant = self.env["mail.conversation.participant"]
        if from_email:
            partner = from_partner or self._find_partner_by_email(from_email)
            Participant._get_or_create(
                self, from_email, partner=partner, role="requester"
            )
        for email in to_emails or []:
            Participant._get_or_create(
                self, email, partner=self._find_partner_by_email(email), role="to"
            )
        for email in cc_emails or []:
            Participant._get_or_create(
                self, email, partner=self._find_partner_by_email(email), role="cc"
            )

    def _find_partner_by_email(self, email):
        normalized = tools.email_normalize(email)
        if not normalized:
            return self.env["res.partner"]
        return (
            self.env["res.partner"]
            .sudo()
            .search([("email_normalized", "=", normalized)], limit=1)
        )

    # ------------------------------------------------------------
    # Capture / GTD funnel (epic 03, task #3965). Quiet capture posts an
    # internal note (transport_id falsy) so no external party is
    # re-notified -- see the project's notification-safety invariant; the
    # generalized _notify_get_recipients override lands in epic 05 and is
    # deliberately NOT relied on here.
    # ------------------------------------------------------------

    @api.model
    def _capture_stub(self, transport, stub, mode="new", target=None):
        """Quiet-capture an inbox stub (a normalized envelope, as returned
        by ``transport._normalize``/``fetch_envelope``) into the hub,
        without persisting anything on the remote mailbox and without
        re-notifying the original recipients.

        :param transport: the ``conversation.transport`` the stub came
            from.
        :param dict stub: canonical envelope -- ``subject``, ``body``,
            ``email_from``/``author``, ``to``, ``cc``, ``external_id``,
            optionally ``author_id`` (a resolved ``res.partner`` id).
        :param str mode: ``'new'`` (default) creates a new conversation;
            ``'existing'`` threads into ``target`` (a ``mail.conversation``);
            ``'link'`` creates a new conversation and links it to ``target``
            (any business record) via ``mail.conversation.link``.
        :param target: see ``mode``.
        :return: the ``mail.conversation`` the stub was captured into.
        """
        if mode == "existing":
            if not target or target._name != "mail.conversation":
                raise UserError(
                    _("Pick an existing conversation to add this item to.")
                )
            conversation = target
        else:
            # mail_create_nolog: a captured conversation's timeline should
            # show the captured item, not Odoo's generic "Conversation
            # created" boilerplate on top of it. mail_create_nosubscribe:
            # quiet capture must not incidentally auto-follow the filing
            # user either -- conversation assignment is a deliberate
            # action (action_reassign), not a side effect of who happened
            # to triage the inbox.
            conversation = self.with_context(
                mail_create_nolog=True, mail_create_nosubscribe=True
            ).create(
                {
                    "name": stub.get("subject") or _("(no subject)"),
                    "primary_transport_id": transport.id,
                }
            )
            if mode == "link":
                if not target:
                    raise UserError(
                        _("Pick a record to link this captured item to.")
                    )
                self.env["mail.conversation.link"].create(
                    {
                        "conversation_id": conversation.id,
                        "res_model": target._name,
                        "res_id": target.id,
                        "reason": "manual",
                    }
                )

        conversation._sync_participants_from_stub(stub)

        post_kwargs = {
            # stub bodies come from transport._normalize(), already HTML
            # (or plaintext already escaped/converted via
            # odoo.tools.plaintext2html) -- wrap in Markup so
            # message_post doesn't re-escape it a second time.
            "body": Markup(stub.get("body") or ""),
            "subject": stub.get("subject"),
            "subtype_xmlid": "mail.mt_note",
        }
        author_id = stub.get("author_id")
        if author_id:
            post_kwargs["author_id"] = author_id
        else:
            # No resolved partner: pass email_from so _message_compute_author
            # can look one up (or fall back to a bare-email author) instead
            # of raising -- passing author_id=False without an email_from
            # would otherwise be treated as "no author at all".
            post_kwargs["email_from"] = stub.get("email_from") or stub.get(
                "author"
            )
        message = conversation.message_post(**post_kwargs)
        # transport_id stays FALSY here by design: it is the model-contract
        # marker for "internal note" (mail.message docstring), and the
        # notification-safety invariant this quiet capture leans on is the
        # subtype (mt_note) + a falsy transport_id -- the generalized
        # _notify_get_recipients override that would make a non-falsy
        # transport_id safe too lands in epic 05, not here (see Risks in
        # the task design). external_id still records provenance/dedup;
        # conversation.primary_transport_id records which transport this
        # came from at the conversation level.
        # message_id records the captured email's real RFC822 Message-Id,
        # overwriting the one message_post just minted for an Odoo-native
        # message: it is what a correspondent's client quotes back in
        # In-Reply-To/References, so it is the only id an outbound reply
        # can thread against (see _imap_reply_headers). external_id keeps
        # holding the transport's own native id -- an IMAP UID, which is
        # meaningless outside that one mailbox -- for provenance and
        # capture-idempotency lookups.
        message.write(
            {
                "external_id": stub.get("external_id"),
                "message_id": stub.get("message_id") or message.message_id,
            }
        )
        # external_id is what makes the note count in the triage facets
        conversation._trigger_message_facets()
        return conversation

    @api.model
    def _find_captured(self, transport, external_id):
        """Idempotent-capture lookup: has this transport's ``external_id``
        already been filed into a conversation? Captured notes carry a
        falsy ``transport_id`` by design (AC7/AC8's notify-safety marker),
        so provenance is matched on ``external_id`` + the conversation's
        ``primary_transport_id`` instead of ``mail.message.transport_id``.
        Returns an empty ``mail.conversation`` recordset if not found.
        """
        message = self.env["mail.message"].search(
            [("model", "=", self._name), ("external_id", "=", external_id)],
            limit=1,
        )
        if message and message.res_id:
            conversation = self.browse(message.res_id)
            if conversation.primary_transport_id == transport:
                return conversation
        return self.browse()

    @api.model
    def _capture_or_find(self, transport, external_id):
        """Fetch+normalize+capture ``external_id`` as a new conversation,
        unless it was already captured earlier -- then return that same
        conversation instead of filing a duplicate. Used by the inbox GTD
        actions (reply/forward/reassign/dismiss) so acting twice on the
        same inbox item never creates two conversations.
        """
        existing = self._find_captured(transport, external_id)
        if existing:
            return existing
        raw = transport._fetch(external_id)
        stub = transport._normalize(raw)
        return self._capture_stub(transport, stub, mode="new")

    def _all_participant_emails(self, roles=("to", "cc", "requester")):
        """Deduplicated participant emails for the given roles, in
        participant order. Used to build an explicit reply-all recipient
        list (roles including ``cc``) as distinct from a plain reply
        (``transport._send``'s own default recipients, to/requester only,
        when no explicit ``recipients`` are passed to ``action_reply``).
        """
        self.ensure_one()
        participants = self.participant_ids.filtered(
            lambda p: p.role in roles and p.email_normalized
        )
        return list(dict.fromkeys(participants.mapped("email_normalized")))

    @api.model
    def _route_via_alias(self, raw_rfc822, model="mail.conversation"):
        """Feed a raw RFC822 message (captured from a browsable transport)
        into the ordinary mail gateway (``mail.thread.message_process``) so
        alias-based routing and In-Reply-To/References threading fire
        exactly as they would for a real inbound -- the 'route through an
        alias' GTD action.
        """
        thread_id = self.env["mail.thread"].message_process(model, raw_rfc822)
        return self.browse(thread_id) if thread_id else self.browse()

    # ------------------------------------------------------------
    # GTD actions -- reply / forward / reassign / archive. Outbound
    # delivery always goes through the transport's explicit _send, never
    # Odoo's notification pipeline (notification-safety invariant).
    # ------------------------------------------------------------

    def _get_sendable_transport(self, transport=None):
        self.ensure_one()
        transport = transport or self.primary_transport_id
        if not transport or not transport.sendable:
            raise UserError(
                _("This conversation has no sendable transport configured.")
            )
        return transport

    def action_reply(self, body, recipients=None, transport=None, subtype_xmlid="mail.mt_comment"):
        """Reply (or reply-all, when ``recipients`` includes the Cc
        participants) on this conversation's primary transport (or the
        explicit ``transport``). ``recipients``: optional explicit list of
        email strings; defaults to the transport's own recipient
        computation from the conversation's participants.
        """
        self.ensure_one()
        transport = self._get_sendable_transport(transport)
        # body comes from the composer (rich-text HTML), not a plain
        # string to be escaped -- wrap in Markup to avoid a double-escape.
        message = self.message_post(
            body=Markup(body or ""), subtype_xmlid=subtype_xmlid
        )
        message.write({"transport_id": transport.id})
        self._trigger_message_facets()
        external_id = transport._send(self, message, recipients=recipients)
        if external_id:
            message.external_id = external_id
        return message

    def action_forward(self, body, to_emails, transport=None):
        """Forward-like-email: send to any address (partner or not),
        without requiring the recipient to already be a participant. This
        is a lightweight "compose + transport._send" action distinct from
        the conversation-level Forward shipped in epic 08
        (``mail_manual_routing_ux``) -- see task design notes.
        """
        self.ensure_one()
        transport = self._get_sendable_transport(transport)
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        # An empty body is legitimate on a forward: the original alone
        # is the message.
        message = self.message_post(
            body=Markup(body or ""), subtype_xmlid="mail.mt_note"
        )
        message.write({"transport_id": transport.id})
        self._trigger_message_facets()
        external_id = transport._send(self, message, recipients=to_emails)
        if external_id:
            message.external_id = external_id
        return message

    def _record_outbound(
        self,
        transport,
        subject,
        body,
        message_id,
        to_emails=None,
        cc_emails=None,
        attachment_ids=None,
    ):
        """Record a message that has ALREADY been sent over ``transport``
        (by ``_send_raw``) onto this conversation, without sending it a
        second time.

        The composer sends first and files second, because filing is
        optional: only the filed path reaches this, and by then the mail
        is on the wire. ``message_id`` is the id that actually went out,
        so a reply quoting it correlates back here.

        ``attachment_ids`` are the files that went out with it, so the
        filed conversation reads as what was actually sent rather than as
        a body whose "see attached" refers to nothing. They are re-homed
        onto this conversation first: ``message_post`` only re-points
        attachments that came from ``mail.compose.message`` or
        ``mail.scheduled.message``, so anything composed elsewhere would
        otherwise stay pointing at a record that is about to cease to
        exist.

        Bcc recipients are deliberately NOT recorded. Filing an exchange
        into a shared hub must not disclose who was blind-copied -- that
        is the one thing a Bcc promises.
        """
        self.ensure_one()
        attachments = self.env["ir.attachment"].browse(attachment_ids or [])
        if attachments:
            attachments.sudo().write({"res_model": self._name, "res_id": self.id})
        message = self.message_post(
            body=Markup(body or ""),
            subject=subject,
            subtype_xmlid="mail.mt_comment",
            attachment_ids=attachments.ids,
        )
        message.write(
            {
                "transport_id": transport.id,
                "message_id": message_id,
                "external_id": (message_id or "").strip("<>") or False,
            }
        )
        self._trigger_message_facets()
        self._sync_participants(
            to_emails=list(to_emails or []), cc_emails=list(cc_emails or [])
        )
        return message

    def action_reassign(self, user=None, team=None):
        """Hand this conversation to a colleague and/or a team."""
        self.ensure_one()
        vals = {}
        if user is not None:
            vals["user_id"] = user.id if user else False
        if team is not None:
            vals["team_id"] = team.id if team else False
        if vals:
            self.write(vals)
        return True

    def action_archive(self):
        """Mark the conversation done -- the closest single-item
        equivalent to "archive" on the existing ``state`` field. The
        durable per-user 'handled' checkmark and bulk-archive UX are
        epic 04's (#3966) job.
        """
        self.write({"state": "done"})
        return True

    # ------------------------------------------------------------
    # Triage facets: computes
    # ------------------------------------------------------------

    @api.depends()
    def _compute_message_facets(self):
        """Compute ``last_message_id``, ``last_activity`` and ``unanswered``.

        Queries ``mail.message`` directly (two ``DISTINCT ON`` selects)
        instead of walking ``message_ids``. The dependency list is empty
        on purpose: Odoo computes the fields for every existing row when
        the module is upgraded, and ``_trigger_message_facets`` re-queues
        them after each post.
        """
        self.env["mail.message"].flush_model(
            [
                "model",
                "res_id",
                "message_type",
                "subtype_id",
                "author_id",
                "date",
                "transport_id",
                "external_id",
            ]
        )
        self.env["res.users"].flush_model(["partner_id", "share"])
        ids = [rec.id for rec in self if rec.id]
        last, inbound = {}, {}
        if ids:
            cr = self.env.cr
            cr.execute(
                """
                SELECT DISTINCT ON (m.res_id) m.res_id, m.id
                  FROM mail_message m
                 WHERE m.model = %s AND m.res_id IN %s
                   AND """
                + _COUNTED_SQL
                + """
                 ORDER BY m.res_id, m.date DESC, m.id DESC
                """,
                [self._name, tuple(ids)],
            )
            last = dict(cr.fetchall())
            note_id = self.env["ir.model.data"]._xmlid_to_res_id(
                "mail.mt_note", raise_if_not_found=False
            )
            cr.execute(
                """
                SELECT DISTINCT ON (m.res_id) m.res_id,
                       (m.author_id IS NOT NULL AND EXISTS (
                            SELECT 1 FROM res_users u
                             WHERE u.partner_id = m.author_id
                               AND u.share IS NOT TRUE)) AS internal
                  FROM mail_message m
                 WHERE m.model = %(model)s AND m.res_id IN %(ids)s
                   AND """
                + _COUNTED_SQL
                + """
                   AND m.message_type <> 'auto_comment'
                   AND NOT (
                        m.subtype_id IS NOT DISTINCT FROM %(note)s
                        AND m.author_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM res_users u
                             WHERE u.partner_id = m.author_id
                               AND u.share IS NOT TRUE))
                 ORDER BY m.res_id, m.date DESC, m.id DESC
                """,
                {
                    "model": self._name,
                    "ids": tuple(ids),
                    "note": note_id,
                },
            )
            inbound = {res_id: not internal for res_id, internal in cr.fetchall()}
        messages = self.env["mail.message"].browse(list(last.values())).sudo()
        messages.fetch(["date"])
        for rec in self:
            message = messages.browse(last[rec.id]) if rec.id in last else messages.browse()
            rec.last_message_id = message
            rec.last_activity = message.date or rec.create_date or fields.Datetime.now()
            rec.unanswered = bool(inbound.get(rec.id))

    @api.depends("user_id")
    def _compute_unassigned(self):
        for rec in self:
            rec.unassigned = not rec.user_id

    @api.depends("last_message_id")
    def _compute_last_message_preview(self):
        for rec in self:
            body = rec.last_message_id.sudo().body
            text = html_to_inner_content(body) if body else ""
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > _PREVIEW_LENGTH:
                text = text[: _PREVIEW_LENGTH - 1].rstrip() + "\u2026"
            rec.last_message_preview = text

    @api.depends_context("uid")
    @api.depends(
        "member_ids.user_id",
        "member_ids.unread",
        "member_ids.is_handled",
        "member_ids.snooze_until",
    )
    def _compute_my_member_state(self):
        uid = self.env.uid
        now = fields.Datetime.now()
        for rec in self:
            member = rec.member_ids.filtered(lambda m: m.user_id.id == uid)[:1]
            snooze = member.snooze_until
            rec.my_unread = bool(member.unread)
            rec.my_handled = bool(member.is_handled)
            rec.my_snooze_until = snooze or False
            rec.my_snoozed = bool(snooze and snooze > now)

    def _search_my_member(self, operator, value, member_domain):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(
                _("Unsupported search on a per-user conversation flag.")
            )
        positive = (operator == "=") == value
        domain = [("user_id", "=", self.env.uid)] + member_domain
        return [("member_ids", "any" if positive else "not any", domain)]

    def _search_my_unread(self, operator, value):
        return self._search_my_member(operator, value, [("unread", "=", True)])

    def _search_my_handled(self, operator, value):
        return self._search_my_member(operator, value, [("is_handled", "=", True)])

    def _search_my_snoozed(self, operator, value):
        return self._search_my_member(
            operator, value, [("snooze_until", ">", fields.Datetime.now())]
        )

    # ------------------------------------------------------------
    # Triage facets: message hook
    # ------------------------------------------------------------

    @api.model
    def _is_internal_partner(self, partner):
        """Whether ``partner`` is (the partner of) an internal, non-share
        user. A falsy partner (bare ``email_from``) is external."""
        return bool(partner) and any(not u.share for u in partner.sudo().user_ids)

    def _trigger_message_facets(self):
        """Queue ``last_message_id``/``last_activity``/``unanswered`` for
        recomputation. ``_message_post_after_hook`` calls it after every
        post; code that moves or removes messages without ``message_post``
        (split/merge, unlink) must call it on every affected conversation.
        """
        for fname in ("last_message_id", "last_activity", "unanswered"):
            self.env.add_to_compute(self._fields[fname], self)

    def _message_post_after_hook(self, message, msg_values):
        res = super()._message_post_after_hook(message, msg_values)
        self._trigger_message_facets()
        author = message.author_id
        author_users = author.sudo().user_ids
        external = not self._is_internal_partner(author)
        Member = self.env["mail.conversation.member"].sudo()
        for rec in self:
            rows = Member.search(
                [
                    ("conversation_id", "=", rec.id),
                    ("user_id", "not in", (author_users | self.env.user).ids),
                    ("unread", "=", False),
                ]
            )
            if rows:
                rows.write({"unread": True})
            if external and rec.state == "waiting":
                rec.sudo().write({"state": "open"})
        return res

    # ------------------------------------------------------------
    # Members
    # ------------------------------------------------------------

    def _get_or_create_members(self, users, unread=None):
        """Return the member rows of ``users`` on ``self``, creating the
        missing ones.

        New rows start unread for everyone but the acting user. With
        ``unread=None`` existing rows are left alone; a boolean forces that
        value on new and existing rows alike.
        """
        Member = self.env["mail.conversation.member"].sudo()
        users = users.sudo().filtered("id")
        if not self or not users:
            return Member
        existing = Member.search(
            [("conversation_id", "in", self.ids), ("user_id", "in", users.ids)]
        )
        have = {(m.conversation_id.id, m.user_id.id) for m in existing}
        for rec in self:
            for user in users:
                if (rec.id, user.id) in have:
                    continue
                vals = {
                    "conversation_id": rec.id,
                    "user_id": user.id,
                    "unread": (
                        user != self.env.user if unread is None else unread
                    ),
                }
                try:
                    with self.env.cr.savepoint():
                        existing |= Member.create(vals)
                except psycopg2.IntegrityError:  # concurrent insert: the unique key won
                    existing |= Member.search(
                        [
                            ("conversation_id", "=", rec.id),
                            ("user_id", "=", user.id),
                        ]
                    )
        if unread is not None:
            to_write = existing.filtered(lambda m: m.unread != unread)
            if to_write:
                to_write.write({"unread": unread})
        return existing

    def _seed_members(self):
        """Give the assignee and the team's members a member row so the
        Unread facet works for them before they first open a conversation.
        """
        for rec in self:
            users = rec.user_id | rec.team_id.member_ids.filtered("active")
            if users:
                rec._get_or_create_members(users)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # An empty ``@api.depends()`` is not triggered by create: queue the
        # message facets so a new conversation never keeps NULL columns.
        records._trigger_message_facets()
        records.filtered(lambda r: r.user_id or r.team_id)._seed_members()
        return records

    def write(self, vals):
        if "state" in vals and vals["state"] != "snoozed":
            vals = dict(vals, team_snooze_until=False)
        res = super().write(vals)
        if "user_id" in vals or "team_id" in vals:
            self._seed_members()
        return res

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        if self.env.context.get("conversation_triage"):
            return []
        return super()._message_auto_subscribe_followers(
            updated_values, default_subtype_ids
        )

    def web_read(self, specification):
        """Opening a conversation (``conversation_mark_read`` in the context,
        set by the Conversations action) marks it read for the opener.

        Deliberately not ``@api.readonly``: it writes the opener's member
        row. Only a single-record read marks, so lists and dialogs never do.
        """
        if self.env.context.get("conversation_mark_read") and len(self) == 1:
            self._get_or_create_members(self.env.user, unread=False)
        return super().web_read(specification)

    # ------------------------------------------------------------
    # Triage actions (RPC). All act on ``self`` only, never on a domain.
    # ------------------------------------------------------------

    def _own_members(self):
        return self._get_or_create_members(self.env.user)

    def action_triage_handle(self):
        """Per-user "remove from my list"."""
        self._own_members().write({"is_handled": True, "snooze_until": False})
        return True

    def action_triage_unhandle(self):
        self._own_members().write({"is_handled": False})
        return True

    def action_triage_done(self):
        self.write({"state": "done"})
        return True

    def action_triage_reopen(self):
        self.write({"state": "open"})
        return True

    def action_triage_snooze(self, until, team=False):
        """Snooze until ``until`` (UTC datetime or string, in the future):
        for the calling user only, or for the whole team (``team=True``).
        """
        until = fields.Datetime.to_datetime(until)
        if not until or until <= fields.Datetime.now():
            raise UserError(_("Pick a snooze time in the future."))
        if team:
            self.write({"state": "snoozed", "team_snooze_until": until})
        else:
            self._own_members().write({"snooze_until": until, "is_handled": False})
        return True

    def action_triage_unsnooze(self):
        self._own_members().write({"snooze_until": False})
        self.filtered(lambda c: c.state == "snoozed").write({"state": "open"})
        return True

    def action_triage_assign(self, user_id=None, team_id=None):
        """``None`` leaves the assignee/team unchanged, ``False`` clears it.
        Adds no follower and sends no assignment mail."""
        user = None if user_id is None else self.env["res.users"].browse(user_id)
        team = (
            None
            if team_id is None
            else self.env["mail.conversation.team"].browse(team_id)
        )
        for rec in self.with_context(conversation_triage=True):
            rec.action_reassign(user=user, team=team)
        return True

    def action_triage_assign_me(self):
        return self.action_triage_assign(user_id=self.env.user.id)

    @api.model
    def _cron_resurface_snoozed(self):
        """Bring snoozed conversations back. Idempotent; never touches
        ``is_handled``."""
        now = fields.Datetime.now()
        Member = self.env["mail.conversation.member"].sudo()
        Member.search(
            [("snooze_until", "!=", False), ("snooze_until", "<=", now)]
        ).write({"snooze_until": False, "unread": True})
        due = self.sudo().search(
            [("state", "=", "snoozed"), ("team_snooze_until", "<=", now)]
        )
        if due:
            due.write({"state": "open"})
            Member.search([("conversation_id", "in", due.ids)]).write({"unread": True})
        return True
