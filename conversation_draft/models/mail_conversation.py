from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.mail import is_html_empty

from .mail_conversation_draft import (
    ACTIVE_STATES,
    DIALOG_CONTEXT_KEY,
    conversation_templates_exist,
)


class MailConversation(models.Model):
    """Draft awareness on the conversation.

    Every field here is non-stored on purpose: a stored compute would
    ``UPDATE mail_conversation`` when a draft flips to ``sent``, after the
    external send, and could trip a serialization retry.
    """

    _inherit = "mail.conversation"

    draft_ids = fields.One2many("mail.conversation.draft", "conversation_id")
    active_draft_id = fields.Many2one(
        "mail.conversation.draft",
        compute="_compute_active_draft",
        search="_search_active_draft_id",
    )
    has_pending_draft = fields.Boolean(
        compute="_compute_active_draft", search="_search_has_pending_draft"
    )
    draft_editor_id = fields.Many2one(
        "res.users",
        compute="_compute_active_draft",
        help="Who is working on the pending draft right now, if anyone.",
    )

    has_reply_templates = fields.Boolean(
        compute="_compute_has_reply_templates",
        help="Whether any reply template exists for conversations.",
    )

    # No ``@api.depends`` and not stored: evaluated on every read, so a
    # template created or deleted shows up without an upgrade or restart.
    def _compute_has_reply_templates(self):
        exists = conversation_templates_exist(self.env)
        for conversation in self:
            conversation.has_reply_templates = exists

    @api.depends("draft_ids.state", "draft_ids.editor_id", "draft_ids.editing_last_seen")
    def _compute_active_draft(self):
        for conversation in self:
            draft = conversation.draft_ids.filtered(
                lambda d: d.state in ACTIVE_STATES
            )[:1]
            conversation.active_draft_id = draft
            conversation.has_pending_draft = bool(draft)
            conversation.draft_editor_id = (
                draft.editor_id if draft and draft.is_being_edited else False
            )

    def _search_active_draft_id(self, operator, value):
        active = Domain("state", "in", ACTIVE_STATES)
        pending = Domain("draft_ids", "any", active)
        # The ORM may hand a falsy comparison over as ``in [False]``.
        if operator in ("in", "not in") and isinstance(value, (list, tuple, set)):
            if set(value) <= {False}:
                operator, value = ("=" if operator == "in" else "!="), False
        if operator in ("=", "!=") and not value:
            return pending if operator == "!=" else ~pending
        return Domain("draft_ids", "any", active & Domain("id", operator, value))

    def _search_has_pending_draft(self, operator, value):
        pending = Domain("draft_ids", "any", Domain("state", "in", ACTIVE_STATES))
        if operator in ("in", "not in"):
            wanted = True in value
            return pending if wanted == (operator == "in") else ~pending
        return pending if (operator == "=") == bool(value) else ~pending

    # ------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------

    def _draft_form_action(self, draft):
        """What the Reply entry points hand to the client: the draft in the
        reply pop-up, over the conversation."""
        return self._draft_dialog_action(draft)

    def _draft_dialog_action(self, draft):
        view = self.env.ref("conversation_draft.mail_conversation_draft_view_form_dialog")
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reply"),
            "res_model": draft._name,
            "res_id": draft.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "new",
            "context": {DIALOG_CONTEXT_KEY: True, "dialog_size": "extra-large"},
        }

    def _is_reply_target(self, message):
        """Whether ``message`` is one a correspondent has seen -- the same
        rule the transports thread an outgoing mail by: an inbound email, a
        captured inbound (it has an ``external_id``) or something we sent
        (it has a ``transport_id``). Never an internal note, a tracking
        message or a message of another record."""
        self.ensure_one()
        message = message.sudo()
        return bool(
            message.exists()
            and message.model == self._name
            and message.res_id == self.id
            and message.message_type != "user_notification"
            and message.message_id
            and (
                message.message_type == "email"
                or message.external_id
                or message.transport_id
            )
        )

    def reply_target_message_ids(self, message_ids):
        """Which of ``message_ids`` the thread offers a per-message Reply
        on. Read-only: the client calls it for each batch of messages it
        loads."""
        self.ensure_one()
        self.check_access("read")
        messages = self.env["mail.message"].sudo().browse(message_ids).exists()
        return [m.id for m in messages if self._is_reply_target(m)]

    def action_open_draft(self, message_id=None):
        """Open the conversation's active reply draft in the reply pop-up,
        creating it when there is none. With ``message_id`` the reply
        answers that message: it is quoted in the draft and the outgoing mail
        threads under it."""
        self.ensure_one()
        self.check_access("write")
        draft = self.env["mail.conversation.draft"]._get_or_create_for(self)
        if message_id:
            message = self.env["mail.message"].sudo().browse(message_id).exists()
            if not self._is_reply_target(message):
                raise UserError(
                    self.env._("This message cannot be answered from the conversation.")
                )
            draft._set_reply_target(message)
        draft._touch_editing()
        return self._draft_form_action(draft)

    def action_open_draft_with_template(self):
        self.ensure_one()
        self.check_access("write")
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation.draft.template",
            "view_mode": "form",
            "target": "new",
            "context": {"default_conversation_id": self.id},
        }

    # ------------------------------------------------------------
    # Defaults for a new draft
    # ------------------------------------------------------------

    def _internal_partner_ids(self):
        return (
            self.env["res.users"]
            .sudo()
            .search([("share", "=", False)])
            .partner_id.ids
        )

    def _draft_outbound_messages(self):
        """Messages that went out over a transport, newest first."""
        self.ensure_one()
        return (
            self.env["mail.message"]
            .sudo()
            .search(
                [
                    ("model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("transport_id", "!=", False),
                ],
                order="id desc",
            )
        )

    def _draft_default_transport(self):
        """The transport the correspondent last wrote to us on, else the
        conversation's primary one -- kept only if the current user may
        read and send from it."""
        self.ensure_one()
        internal = set(self._internal_partner_ids())
        candidates = self.env["conversation.transport"]
        for message in self._draft_outbound_messages():
            if message.author_id.id not in internal:
                candidates |= message.transport_id
                break
        candidates |= self.sudo().primary_transport_id
        for transport in candidates:
            transport = transport.with_env(self.env)
            if transport.exists() and transport._filtered_access("read"):
                if transport.sudo().sendable:
                    return transport
        return self.env["conversation.transport"]

    def _draft_default_body(self, transport):
        """The initial body of a new draft sent from ``transport``: the
        acting user's signature as ordinary, editable text between two empty
        paragraphs (the inbox reply wizard's layout), so nothing has to be
        appended when the reply goes out. Empty when the user has no
        signature or the transport is a team mailbox."""
        self.ensure_one()
        signature = self.env.user.signature
        if is_html_empty(signature):
            return False
        if transport and not transport._draft_prefills_user_signature():
            return False
        return Markup("<p><br/></p>%s<p><br/></p>") % Markup(signature)

    def _draft_default_recipients(self):
        """Value dicts for the draft's recipient rows, derived from the
        external participants. Unreachable participants (no address) are
        kept and flagged by the row's ``is_reachable``."""
        self.ensure_one()
        participants = self.participant_ids.filtered(lambda p: p.kind == "external")
        scoped = hasattr(self, "_next_message_recipients")
        if scoped:
            partners, emails = self._next_message_recipients()
            keep = participants.filtered(
                lambda p: p.partner_id in partners
                if p.partner_id
                else p.email_normalized in emails
            )
            keep |= self._draft_pending_cc_once(participants)
        else:
            keep = participants.filtered(lambda p: p.role != "watcher")
        recipients = []
        for participant in keep:
            mode = "to" if participant.role in ("to", "requester") else "cc"
            recipients.append(
                {
                    "participant_id": participant.id,
                    "partner_id": participant.partner_id.id,
                    "email": participant.email_normalized or participant.email,
                    "mode": mode,
                }
            )
        return recipients

    def _draft_pending_cc_once(self, participants):
        """One-off Cc participants that have not yet had their outbound
        message: ``_add_cc_once`` promises "the next outbound message
        only", and the next-recipients helper alone drops them. A
        participant is still pending while it was created after the latest
        message an internal user sent out (or there is none)."""
        self.ensure_one()
        internal = set(self._internal_partner_ids())
        last_outbound = next(
            (m for m in self._draft_outbound_messages() if m.author_id.id in internal),
            None,
        )
        return participants.filtered(
            lambda p: not p.receives_updates
            and p.role == "cc"
            and (not last_outbound or p.create_date > last_outbound.create_date)
        )
