import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools import display, mime

_logger = logging.getLogger(__name__)


class ConversationTransport(models.Model):
    """The channel a conversation/message travels over (email, SMS,
    WhatsApp, ...). This module defines the capability-flag + abstract-hook
    *interface* (modeled on ``payment.provider``): it never hardcodes a
    provider. Concrete providers (``conversation_imap``,
    ``conversation_gmail``, ...) ``_inherit`` this model, turn on the flags
    they support, and implement the matching hooks.

    Identity == the transport config record: a personal inbox is a
    ``conversation.transport`` with ``user_id`` set; a falsy ``user_id`` is
    a shared/team-level identity (e.g. a team-monitored mailbox).
    """

    _name = "conversation.transport"
    _description = "Conversation Transport"

    name = fields.Char(required=True)
    provider = fields.Selection(
        selection=[],
        help="The concrete transport implementation providing this "
        "connection (generic IMAP/SMTP, Gmail OAuth, ...). This base "
        "module defines no options itself -- each opt-in provider module "
        "(conversation_imap, conversation_gmail, ...) registers its own "
        "via selection_add, so the dropdown only ever offers a provider "
        "that is actually installed and implemented.",
    )
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------
    # Capability flags -- default False; a provider module turns on the
    # ones it actually implements so the UI (conversation_inbox) and the
    # RPC entry points below can gate on them instead of guessing.
    # ------------------------------------------------------------
    browsable = fields.Boolean(
        default=False,
        help="Can list/paginate a remote mailbox for the in-Odoo inbox "
        "viewer (browse_page/_browse). The viewer surface only appears "
        "for browsable transports.",
    )
    searchable = fields.Boolean(
        default=False,
        help="Supports server-side search of the remote mailbox "
        "(_search_remote) beyond simple pagination.",
    )
    pushable = fields.Boolean(
        default=False,
        help="Can subscribe to push/webhook notifications instead of "
        "polling (_subscribe_push).",
    )
    sendable = fields.Boolean(
        default=False,
        help="Can send outbound messages (_send). The composer only "
        "offers send for sendable transports.",
    )
    mailbox_writable = fields.Boolean(
        default=False,
        help="Allow users of this account to archive, trash or mark "
        "messages read on the REAL mailbox from the inbox viewer "
        "(_archive_remote/_trash_remote/_mark_read_remote). Off by "
        "default: mailbox writes must be enabled explicitly per account, "
        "shared accounts included.",
    )
    artifact_only = fields.Boolean(
        default=False,
        help="This transport only ever produces read-only artifacts "
        "(e.g. an imported attachment) -- no live browse/search/send "
        "capability, so the other flags stay False by design.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Owner",
        help="The user this personal mail-account connection belongs to. "
        "Falsy = a shared/team-level transport identity.",
    )
    login = fields.Char(help="Account address/login on the remote transport.")
    default_file_in_odoo = fields.Boolean(
        string="File Replies in Odoo by Default",
        default=False,
        help="Whether the composer pre-selects 'file this exchange into a "
        "conversation' for this account. Off by default, and deliberately: "
        "a personal mailbox's traffic must not land in the shared hub "
        "unless a human says so each time. Turn it on for a shared or team "
        "mailbox, where filing is the point.",
    )

    record_link_mode = fields.Selection(
        [("auto", "Automatic"), ("suggest", "Suggest"), ("off", "Off")],
        string="Link Replies to Odoo Records",
        default="suggest",
        required=True,
        help="What to do when an inbound message in this mailbox is a "
        "reply to mail Odoo itself sent (its headers name an Odoo record). "
        "Applies to personal mailboxes only: a shared mailbox is always "
        "Off. Suggest: preselect that record in the capture dialog; you "
        "still confirm. Automatic: file and link the message without the "
        "dialog, but only when 'File Replies in Odoo by Default' is also "
        "on (otherwise it behaves like Suggest); filing still needs a "
        "click on New Conversation or Link to a Record. Off: do nothing.",
    )

    archive_on_capture = fields.Boolean(
        string="Archive After Filing",
        default=False,
        help="Also archive the source message in the real mailbox once it "
        "has been filed in Odoo (new conversation, added to a "
        "conversation, linked to a record, or a filed reply). Off by "
        "default. A transport whose provider cannot archive reports a warning.",
    )

    # ------------------------------------------------------------
    # Abstract hook interface. Every hook raises NotImplementedError on the
    # base record; a provider submodule overrides the ones its capability
    # flags claim to support. Hooks persist nothing in Odoo themselves --
    # that is the caller's job (see mail.conversation._capture_stub).
    # ------------------------------------------------------------

    def _browse(self, query=None, page=1):
        """Return a page of message stubs (plain, JSON-serializable dicts:
        external_id, subject, email_from, date, snippet, ...) from the
        remote mailbox. Must not persist anything in Odoo."""
        self.ensure_one()
        raise NotImplementedError

    def _search_remote(self, criteria):
        """Server-side search of the remote mailbox; same stub shape as
        ``_browse``. Named ``_search_remote`` rather than ``_search`` --
        the latter is ``BaseModel``'s own private query-building method
        (called on every field fetch/search of *any* model), so reusing
        that name here would silently break ORM access to
        ``conversation.transport`` itself."""
        self.ensure_one()
        raise NotImplementedError

    def _fetch(self, external_id):
        """Return the full raw envelope for a single message, by its
        native id on this transport (e.g. an IMAP UID or Gmail message
        id)."""
        self.ensure_one()
        raise NotImplementedError

    def _normalize(self, raw):
        """raw (transport-native envelope, as returned by ``_fetch``) ->
        canonical dict: ``author`` / ``email_from``, ``to`` (list),
        ``cc`` (list), ``subject``, ``body``, ``external_id``
        (message-id on the transport), ``date``."""
        self.ensure_one()
        raise NotImplementedError

    def _match_inbound(self, raw):
        """Within-transport correlation: return the existing
        ``mail.message`` whose thread this raw message continues, or an
        empty ``mail.message`` recordset if none. Never crosses
        transports -- correlation across channels is always a deliberate
        human action.

        What the raw message is matched *against* is the transport's
        business: an email transport correlates References/In-Reply-To
        with ``mail.message.message_id``, since its ``external_id`` is the
        IMAP UID rather than an RFC id."""
        self.ensure_one()
        raise NotImplementedError

    def _send(self, conversation, message, recipients=None, cc=None, bcc=None):
        """Send ``message`` (an already-posted ``mail.message`` on
        ``conversation``) out over this transport, to the explicit
        ``recipients`` (list of email strings) when given, else the
        recipients computed from ``message``/``conversation``
        participants. ``cc``/``bcc`` (lists of email strings) are optional
        extra recipients; Bcc must never be disclosed to the others. This is the *only* place external email is ever
        produced for a conversation message -- never Odoo's notification
        pipeline."""
        self.ensure_one()
        raise NotImplementedError

    def _send_raw(
        self,
        subject,
        body,
        to_emails,
        cc=None,
        bcc=None,
        in_reply_to=None,
        attachments=None,
        message_id=None,
    ):
        """Send one message over this transport from plain values, with no
        Odoo record of any kind involved -- no ``mail.conversation``, no
        ``mail.message``, no ``mail.mail``. Returns the RFC822 Message-Id
        it put on the wire.

        This is the primitive; ``_send`` is a thin wrapper that derives
        these values from a posted message. Triage from a personal mailbox
        must be able to reply without filing the body into the shared hub
        (task #3965), which is only possible if sending and persisting are
        separable.

        :param attachments: list of dicts with ``filename``, ``content``
            (bytes) and optionally ``mimetype``.
        :param message_id: reuse this Message-Id instead of minting one --
            for the filed path, where a ``mail.message`` already carries
            the id the recipient will quote back.
        """
        self.ensure_one()
        raise NotImplementedError

    def _subscribe_push(self):
        """Subscribe to push/webhook notifications for this transport, for
        providers with ``pushable = True``."""
        self.ensure_one()
        raise NotImplementedError

    def _archive_remote(self, external_id):
        """Archive the message in the real mailbox: it leaves the browse
        folder but stays retrievable (e.g. Gmail All Mail, an Archive
        folder). Persists nothing in Odoo."""
        self.ensure_one()
        raise NotImplementedError

    def _trash_remote(self, external_id):
        """Move the message to the real mailbox's Trash (recoverable).
        Must never permanently destroy it (no bare EXPUNGE)."""
        self.ensure_one()
        raise NotImplementedError

    def _mark_read_remote(self, external_id):
        """Mark the message as read in the real mailbox."""
        self.ensure_one()
        raise NotImplementedError

    # ------------------------------------------------------------
    # Odoo-origin header resolution (task #4144). Transport-agnostic: it
    # works on the normalized stub, so every provider benefits.
    # ------------------------------------------------------------

    def _record_link_active(self):
        """Single gate: personal mailbox and not switched Off. Shared or
        Off means no fetch, no parse and no query."""
        self.ensure_one()
        return bool(self.user_id) and self.record_link_mode != "off"

    def _resolve_record_from_headers(self, stub):
        """Resolve a normalized stub's Odoo-origin headers to the record it
        replies to. Header-only and bounded; never raises.

        Returns ``("link", record)``, ``("existing", conversation)`` or
        ``(False, None)``. A tattoo is only trusted when an exact local
        ``mail.message.message_id`` matches (the foreign or deleted case
        degrades to no suggestion); the record is the local message's own
        ``model``/``res_id`` and must exist and be readable by the current
        user (never sudo), so nothing unreadable is ever disclosed. A match
        on a conversation message stops the scan: the reply belongs to that
        conversation, not to an older business record.
        """
        self.ensure_one()
        try:
            candidates = mime.odoo_header_candidates(
                stub.get("message_id"),
                stub.get("in_reply_to"),
                stub.get("references"),
                stub.get("x_odoo_objects"),
            )
            msgids = [c["msgid"] for c in candidates if c["msgid"]]
            if not msgids:
                return False, None
            found = {}
            for msg in (
                self.env["mail.message"]
                .sudo()
                .search_fetch(
                    [("message_id", "in", msgids)],
                    ["message_id", "model", "res_id"],
                    order="id desc",
                )
            ):
                found.setdefault(msg.message_id, msg)
            for candidate in candidates:
                msg = found.get(candidate["msgid"]) if candidate["msgid"] else None
                if not msg:
                    continue
                model, res_id = msg.model, msg.res_id
                if not model or not res_id or model not in self.env:
                    continue
                if model == "mail.conversation":
                    conv = self.env[model].browse(res_id)
                    if conv.exists() and conv.has_access("read"):
                        return "existing", conv
                    # Unreadable or gone: still the conversation's reply,
                    # so do not fall through to an older record.
                    return False, None
                comodel = self.env[model]
                if (
                    comodel._transient
                    or comodel._abstract
                    or not self.env["ir.model"]._get(model)
                ):
                    continue
                record = comodel.browse(res_id)
                if record.exists() and record.has_access("read"):
                    return "link", record
        except Exception:  # noqa: BLE001 - any failure means no suggestion
            _logger.debug("Odoo-origin header resolution failed", exc_info=True)
        return False, None

    # ------------------------------------------------------------
    # RPC entry points for the OWL inbox viewer (conversation_inbox).
    # Explicit-id @api.model entry points rather than instance methods, so
    # the client can call them without first browsing/loading the record.
    # Stub dicts only -- persist nothing in Odoo.
    # ------------------------------------------------------------

    @api.model
    def browse_page(self, transport_id, query=None, page=1):
        transport = self.browse(transport_id)
        if not transport.browsable:
            raise UserError(
                self.env._(
                    "%(transport)s cannot be browsed as an inbox.",
                    transport=transport.display_name,
                )
            )
        return transport._browse(query=query, page=page)

    @api.model
    def fetch_envelope(self, transport_id, external_id):
        transport = self.browse(transport_id)
        if not transport.browsable:
            raise UserError(
                self.env._(
                    "%(transport)s cannot be browsed as an inbox.",
                    transport=transport.display_name,
                )
            )
        raw = transport._fetch(external_id)
        stub = transport._normalize(raw)
        # The viewer renders the body as HTML: whatever the provider's
        # _normalize produced, the browser only ever gets the strict
        # display profile (see tools/display.py). Every other key stays
        # plain data that the client escapes.
        if isinstance(stub, dict) and "body" in stub:
            stub = dict(stub, body=display.sanitize_display_html(stub["body"]))
        return stub

    def _mailbox_action(self, hook, external_id):
        """Gate + dispatch one mailbox write (AC5): the transport must be
        browsable and ``mailbox_writable``; an unimplemented hook becomes
        a clear UserError rather than a traceback or a silent no-op."""
        self.ensure_one()
        if not (self.browsable and self.mailbox_writable):
            raise UserError(
                self.env._(
                    "%(transport)s does not allow mailbox actions.",
                    transport=self.display_name,
                )
            )
        try:
            return getattr(self, hook)(external_id)
        except NotImplementedError:
            raise UserError(
                self.env._(
                    "%(transport)s does not support mailbox actions.",
                    transport=self.display_name,
                )
            ) from None

    @api.model
    def archive_item(self, transport_id, external_id):
        return self.browse(transport_id)._mailbox_action(
            "_archive_remote", external_id
        )

    @api.model
    def trash_item(self, transport_id, external_id):
        return self.browse(transport_id)._mailbox_action("_trash_remote", external_id)

    @api.model
    def mark_read_item(self, transport_id, external_id):
        return self.browse(transport_id)._mailbox_action(
            "_mark_read_remote", external_id
        )
