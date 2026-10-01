import logging
import re
from datetime import timedelta

import psycopg2.errors

from odoo import Command, _, api, fields, models
from odoo.addons.html_editor.tools import handle_history_divergence
from odoo.exceptions import ConcurrencyError, UserError
from odoo.http import request
from odoo.tools.misc import mute_logger

_logger = logging.getLogger(__name__)

# A draft in one of these states occupies the conversation's single slot.
ACTIVE_STATES = ("draft", "sending")
# A draft claimed for sending for longer than this is considered stuck: the
# process that claimed it died before it could record the outcome.
STUCK_SENDING_MINUTES = 10
IDLE_PARAM = "conversation_draft.editing_idle_minutes"
DEFAULT_IDLE_MINUTES = 15
HISTORY_ATTRIBUTE = re.compile(r'\s*data-last-history-steps="[0-9,]*"')

# Writing any of these is refused once the draft has left the ``draft`` state.
CONTENT_FIELDS = {"body", "subject", "transport_id", "recipient_ids", "attachment_ids"}


class MailConversationDraft(models.Model):
    """A reply being prepared on a conversation, shared by everyone who can
    work the conversation.

    At most one draft per conversation is *active* (``draft`` or
    ``sending``). The body is a collaborative HTML field, so several people
    edit it live; review comments are the draft's own chatter.

    Sending is exactly-once in every non-crash path: the draft is claimed
    with a *committed* compare-and-set (``draft`` -> ``sending``) before any
    external I/O, and the send itself runs in a dedicated cursor that
    Odoo's request retry loop never replays. See :meth:`action_send`.
    """

    _name = "mail.conversation.draft"
    _description = "Conversation Reply Draft"
    _inherit = ["mail.thread", "conversation.draft.access.mixin"]
    _order = "id desc"
    _delegated_access_field = "conversation_id"

    conversation_id = fields.Many2one(
        "mail.conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sending", "Sending"),
            ("sent", "Sent"),
            ("discarded", "Discarded"),
        ],
        default="draft",
        required=True,
        index=True,
        readonly=True,
        copy=False,
    )
    subject = fields.Char(
        help="Leave empty to use the conversation's name as the subject."
    )
    body = fields.Html()
    transport_id = fields.Many2one(
        "conversation.transport",
        domain=[("sendable", "=", True)],
        string="Send From",
    )
    recipient_ids = fields.One2many(
        "mail.conversation.draft.recipient",
        "draft_id",
        string="Recipients",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mail_conversation_draft_ir_attachment_rel",
        "draft_id",
        "attachment_id",
        string="Attachments",
    )
    # Deliberately NOT tracked: tracking would subscribe the editor and make
    # every keystroke-adjacent save noisy in the chatter.
    editor_id = fields.Many2one("res.users", string="Last Edited By", copy=False)
    editing_since = fields.Datetime(copy=False)
    editing_last_seen = fields.Datetime(copy=False)
    is_being_edited = fields.Boolean(compute="_compute_is_being_edited")
    sent_message_id = fields.Many2one("mail.message", readonly=True, copy=False)
    sent_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    sent_date = fields.Datetime(readonly=True, copy=False)
    has_unreachable_recipients = fields.Boolean(
        compute="_compute_has_unreachable_recipients"
    )
    is_send_stuck = fields.Boolean(compute="_compute_is_send_stuck")

    _one_active_draft_per_conversation = models.UniqueIndex(
        "(conversation_id) WHERE state IN ('draft', 'sending')"
    )

    # ------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------

    @api.depends("conversation_id")
    def _compute_display_name(self):
        for draft in self:
            draft.display_name = self.env._(
                "Reply on %(conversation)s",
                conversation=draft.conversation_id.display_name or "",
            )

    @api.model
    def _editing_idle_delta(self):
        minutes = self.env["ir.config_parameter"].sudo().get_param(
            IDLE_PARAM, DEFAULT_IDLE_MINUTES
        )
        try:
            return timedelta(minutes=float(minutes))
        except (TypeError, ValueError):
            return timedelta(minutes=DEFAULT_IDLE_MINUTES)

    @api.depends("editing_last_seen", "editor_id")
    def _compute_is_being_edited(self):
        limit = fields.Datetime.now() - self._editing_idle_delta()
        for draft in self:
            draft.is_being_edited = bool(
                draft.state == "draft"
                and draft.editor_id
                and draft.editing_last_seen
                and draft.editing_last_seen > limit
            )

    @api.depends("recipient_ids.is_reachable")
    def _compute_has_unreachable_recipients(self):
        for draft in self:
            draft.has_unreachable_recipients = any(
                not recipient.is_reachable for recipient in draft.recipient_ids
            )

    @api.depends("state", "sent_date")
    def _compute_is_send_stuck(self):
        limit = fields.Datetime.now() - timedelta(minutes=STUCK_SENDING_MINUTES)
        for draft in self:
            draft.is_send_stuck = bool(
                draft.state == "sending" and draft.sent_date and draft.sent_date < limit
            )

    # ------------------------------------------------------------
    # Write: read-only once settled, history divergence, editing signal
    # ------------------------------------------------------------

    def _editing_signal_vals(self):
        """Values recording that the current user is editing this draft. The
        ``editing_since`` timestamp only restarts when the editor changes or
        the previous editing session went stale."""
        self.ensure_one()
        now = fields.Datetime.now()
        vals = {"editor_id": self.env.uid, "editing_last_seen": now}
        stale = (
            not self.editing_last_seen
            or self.editing_last_seen < now - self._editing_idle_delta()
        )
        if self.editor_id != self.env.user or stale or not self.editing_since:
            vals["editing_since"] = now
        return vals

    def _touch_editing(self):
        for draft in self.filtered(lambda d: d.state == "draft"):
            draft.write(draft._editing_signal_vals())

    def write(self, vals):
        touches_content = bool(CONTENT_FIELDS & vals.keys())
        if touches_content:
            settled = self.filtered(lambda draft: draft.state != "draft")
            if settled:
                raise UserError(
                    self.env._(
                        "This reply was already sent or discarded and can no "
                        "longer be edited."
                    )
                )
        if len(self) == 1:
            handle_history_divergence(self, "body", vals)
        if touches_content and "editor_id" not in vals:
            result = True
            for draft in self:
                result &= super(MailConversationDraft, draft).write(
                    {**vals, **draft._editing_signal_vals()}
                )
            return result
        return super().write(vals)

    # ------------------------------------------------------------
    # Get or create the conversation's active draft
    # ------------------------------------------------------------

    @api.model
    def _active_for(self, conversation):
        return self.search(
            [
                ("conversation_id", "=", conversation.id),
                ("state", "in", ACTIVE_STATES),
            ],
            limit=1,
        )

    @api.model
    def _get_or_create_for(self, conversation):
        """Return the conversation's active draft, creating it (with the
        default transport and recipients) when there is none.

        Concurrent callers are serialized on the conversation row. If the
        create still loses a race against a commit our snapshot cannot see,
        the failure is surfaced in the way that lets the caller recover:
        ``ConcurrencyError`` inside an HTTP/RPC request (the request is
        retried on a fresh snapshot and finds the winner's draft), a clear
        ``UserError`` anywhere else.
        """
        conversation.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM mail_conversation WHERE id = %s FOR UPDATE",
            [conversation.id],
        )
        draft = self._active_for(conversation)
        if draft:
            return draft
        transport = conversation._draft_default_transport()
        vals = {
            "conversation_id": conversation.id,
            "transport_id": transport.id or False,
            "recipient_ids": [
                Command.create(recipient_vals)
                for recipient_vals in conversation._draft_default_recipients()
            ],
        }
        try:
            with self.env.cr.savepoint(), mute_logger("odoo.sql_db"):
                return self.with_context(
                    mail_create_nolog=True, mail_create_nosubscribe=True
                ).create(vals)
        except psycopg2.errors.UniqueViolation as exc:
            if request:
                raise ConcurrencyError(
                    "A reply draft was just created on this conversation."
                ) from exc
            raise UserError(
                self.env._(
                    "A colleague has just started a reply on this conversation. "
                    "Open it again to join their draft."
                )
            ) from exc

    # ------------------------------------------------------------
    # State transitions. Every transition is a compare-and-set in SQL so
    # two actors can never both win, whatever happens to either request.
    # ------------------------------------------------------------

    @api.model
    def _cas_state(self, cr, draft_id, expected, new_state, extra=None):
        """Atomically move a draft from one of ``expected`` states to
        ``new_state`` on ``cr``. Returns whether this call won."""
        assignments = ["state = %s"]
        params = [new_state]
        for column, value in (extra or {}).items():
            assignments.append(f"{column} = %s")
            params.append(value)
        params += [draft_id, tuple(expected)]
        cr.execute(
            "UPDATE mail_conversation_draft SET " + ", ".join(assignments) + " "  # noqa: S608
            "WHERE id = %s AND state IN %s RETURNING id",
            params,
        )
        return bool(cr.fetchone())

    def _lost_claim_error(self, cr):
        """The error for a draft that is no longer in the state we need,
        built from the committed truth read on ``cr``."""
        cr.execute(
            "SELECT state, sent_by_id FROM mail_conversation_draft WHERE id = %s",
            [self.id],
        )
        row = cr.fetchone()
        if not row:
            return UserError(self.env._("This reply no longer exists."))
        state, sent_by_id = row
        if state == "discarded":
            return UserError(self.env._("This reply was discarded."))
        user = self.env["res.users"].sudo().browse(sent_by_id).exists()
        return UserError(
            self.env._(
                "This reply was already sent (or is being sent) by %(user)s.",
                user=user.name or self.env._("someone"),
            )
        )

    def action_discard(self):
        for draft in self:
            if not self._cas_state(
                self.env.cr,
                draft.id,
                ("draft",),
                "discarded",
                {"write_uid": self.env.uid},
            ):
                raise draft._lost_claim_error(self.env.cr)
        self.invalidate_recordset()
        return True

    def action_mark_sent(self):
        """Stuck-send recovery: the user confirms the email did go out."""
        self.ensure_one()
        self._require_stuck()
        if not self._cas_state(self.env.cr, self.id, ("sending",), "sent"):
            raise self._lost_claim_error(self.env.cr)
        self.invalidate_recordset()
        return True

    def action_return_to_draft(self):
        """Stuck-send recovery: put the draft back in editing. May send
        twice if the email did in fact go out."""
        self.ensure_one()
        self._require_stuck()
        if not self._cas_state(
            self.env.cr,
            self.id,
            ("sending",),
            "draft",
            {"sent_by_id": None, "sent_date": None},
        ):
            raise self._lost_claim_error(self.env.cr)
        self.invalidate_recordset()
        return True

    def _require_stuck(self):
        self.check_access("write")
        self.invalidate_recordset(["state", "sent_date"])
        if not self.is_send_stuck:
            raise UserError(
                self.env._("This reply is still being sent, give it a few minutes.")
            )

    # ------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------

    def _send_envelope(self):
        """Validate the draft is sendable by the current user and return
        ``(transport, to, cc, bcc)`` with lists of normalized emails.
        Unreachable recipients (no address) are dropped."""
        self.ensure_one()
        transport = self.transport_id
        if not (
            transport
            and transport.exists()
            and transport._filtered_access("read")
            and transport.sudo().sendable
        ):
            raise UserError(
                self.env._("Pick a transport you can send from before sending.")
            )
        by_mode = {"to": [], "cc": [], "bcc": []}
        for recipient in self.recipient_ids:
            if recipient.is_reachable:
                by_mode[recipient.mode].append(recipient.email_normalized)
        to, cc, bcc = (list(dict.fromkeys(by_mode[mode])) for mode in ("to", "cc", "bcc"))
        if not to:
            raise UserError(
                self.env._("Add at least one reachable To recipient before sending.")
            )
        return transport, to, cc, bcc

    def action_send(self):
        """Send this draft over its transport and record the outcome.

        1. Validate in the request environment (writes nothing).
        2. Claim the draft with a committed ``draft`` -> ``sending``
           compare-and-set in its own cursor, *before* any external I/O.
        3. Post, send and finalize in a second dedicated cursor.
        4. On failure, roll that cursor back (post, attachment copies and
           participant syncs vanish) and reset the draft to ``draft``.

        The send is synchronous SMTP, so a request transaction that is
        rolled back and replayed by Odoo's retry loop must never re-send:
        the committed claim makes a replay hit "already sent". Neither
        dedicated cursor is wrapped by that retry loop.

        Callers must not hold uncommitted writes on this draft row in the
        same request, or the claim would wait on their row lock (it fails
        with a clear error after a short ``lock_timeout`` instead of
        hanging). The form saves through a separate RPC before the button
        fires, so the UI never hits this.
        """
        self.ensure_one()
        self.check_access("write")
        transport, to, cc, bcc = self._send_envelope()
        self._claim_for_sending()
        try:
            with self.env.registry.cursor() as cr_send:
                draft = self.with_env(self.env(cr=cr_send))
                draft._send_and_record(transport, to, cc, bcc)
        except Exception as exc:  # noqa: BLE001 - any failure must release the claim
            _logger.warning("Sending draft %s failed", self.id, exc_info=True)
            self._release_claim()
            raise UserError(self.env._("Sending failed: %s", str(exc))) from exc
        self.invalidate_recordset()
        return self._after_send_action()

    def _after_send_action(self):
        """What the client does once the send is recorded. Everything the
        request transaction does *after* the dedicated cursors committed
        lives here: a replay of the request must land on "already sent"."""
        return {"type": "ir.actions.client", "tag": "reload"}

    def _claim_for_sending(self):
        with self.env.registry.cursor() as cr_claim:
            cr_claim.execute("SET LOCAL lock_timeout = '5s'")
            try:
                won = self._cas_state(
                    cr_claim,
                    self.id,
                    ("draft",),
                    "sending",
                    {
                        "sent_by_id": self.env.uid,
                        "sent_date": fields.Datetime.now(),
                    },
                )
            except psycopg2.errors.LockNotAvailable as exc:
                raise UserError(
                    self.env._(
                        "This draft is being saved by someone else, try again "
                        "in a moment."
                    )
                ) from exc
            if not won:
                raise self._lost_claim_error(cr_claim)
        self.invalidate_recordset()

    def _release_claim(self):
        """Put a claimed draft back to ``draft`` after a failed send. Safe
        against the unique index: ``sending`` is inside its predicate, so no
        other active draft can exist for the conversation meanwhile."""
        with self.env.registry.cursor() as cr_reset:
            self._cas_state(
                cr_reset,
                self.id,
                ("sending",),
                "draft",
                {"sent_by_id": None, "sent_date": None},
            )
        self.invalidate_recordset()

    def _send_and_record(self, transport, to, cc, bcc):
        """Runs inside the dedicated send cursor (``self`` carries its
        environment): lock the row, file attachments and participants,
        post + send through the conversation's reply seam, record the
        result."""
        self.invalidate_recordset()
        self.env.cr.execute(
            "SELECT id FROM mail_conversation_draft WHERE id = %s FOR UPDATE",
            [self.id],
        )
        conversation = self.conversation_id
        transport = transport.with_env(self.env)
        attachments = self.attachment_ids.copy(
            {"res_model": conversation._name, "res_id": conversation.id}
        )
        conversation._sync_participants(to_emails=to, cc_emails=cc)
        body = HISTORY_ATTRIBUTE.sub("", self.body or "")
        message = conversation.action_reply(
            body,
            recipients=to,
            transport=transport,
            subject=self.subject or None,
            cc=cc,
            bcc=bcc,
            attachment_ids=attachments.ids,
        )
        self.write({"state": "sent", "sent_message_id": message.id})
        return message

    # ------------------------------------------------------------
    # Wizard entry
    # ------------------------------------------------------------

    def action_use_template(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation.draft.template",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_conversation_id": self.conversation_id.id,
                "default_draft_id": self.id,
            },
        }

    # ------------------------------------------------------------
    # Notification safety: comments on a draft are internal review chatter.
    # They must never reach an external party, even when one is @mentioned.
    # ------------------------------------------------------------

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals, **kwargs)
        return [
            data
            for data in recipients
            if data.get("type") == "user" and not data.get("ushare")
        ]

    def _message_subscribe(self, partner_ids=None, subtype_ids=None, customer_ids=None):
        if partner_ids:
            internal = (
                self.env["res.users"]
                .sudo()
                .search([("partner_id", "in", partner_ids), ("share", "=", False)])
                .partner_id
            )
            partner_ids = [pid for pid in partner_ids if pid in internal.ids]
            if not partner_ids:
                return True
        return super()._message_subscribe(
            partner_ids=partner_ids, subtype_ids=subtype_ids, customer_ids=customer_ids
        )
