import base64
import email
import email.policy
import imaplib
import logging
import smtplib
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import make_msgid

from odoo import fields, models
from odoo.addons.conversation_base.tools import mime
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools.lru import LRU

_logger = logging.getLogger(__name__)

# Gmail's IMAP/SMTP endpoints are fixed -- unlike conversation_imap, there
# is no host/port to configure.
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587

# Per-process, per-(transport, uid) envelope cache -- same rationale as
# conversation_imap's: avoid re-parsing the same message across nearby page
# views without ever holding a connection open between requests.
_ENVELOPE_CACHE = LRU(512)

DEFAULT_PAGE_SIZE = 25


class ConversationTransport(models.Model):
    """Gmail provider: browse/fetch/send over IMAP/SMTP, authenticated with
    XOAUTH2 (RFC 7628) built from ``google.gmail.mixin``'s OAuth2 refresh
    token -- reused as-is from ``google_gmail`` (Odoo's own Gmail OAuth
    scaffolding), never a stored password (Gmail killed app-passwords).
    RFC822 parsing is shared with ``conversation_imap`` via
    ``conversation_base.tools.mime`` rather than duplicated.
    """

    # Odoo only infers _name from _inherit[0] when _inherit has exactly one
    # entry (see odoo.models.MetaModel.__new__) -- with two entries it
    # would otherwise fall back to the raw Python class name and silently
    # register a bogus new model, so _name must be given explicitly here.
    _name = "conversation.transport"
    _inherit = ["conversation.transport", "google.gmail.mixin"]

    provider = fields.Char(default="gmail")
    imap_folder = fields.Char(string="IMAP Folder", default="INBOX")

    # ------------------------------------------------------------
    # Connect-to-Gmail entrypoint -- wraps google.gmail.mixin's
    # open_google_gmail_uri() (only on OUR OWN conversation.transport
    # model; ir.mail_server/fetchmail.server, the mixin's other
    # consumers, are completely untouched) to fix a real UX dead end:
    # when the instance-level OAuth Client ID/Secret
    # (google_gmail_client_id/_secret ir.config_parameters, set under
    # Settings > General Settings > Emails > Custom Email Servers > Use a
    # Gmail Server) were never configured, the mixin's own
    # open_google_gmail_uri() just raises a bare UserError("Please
    # configure your Gmail credentials.") with no indication of where
    # that is. An admin clicking "Connect to Gmail" on a conversation
    # transport had nowhere to go from there. Detect that case up front
    # and redirect straight to General Settings with an actionable
    # message instead.
    # ------------------------------------------------------------

    def open_google_gmail_uri(self):
        self.ensure_one()
        config = self.env["ir.config_parameter"].sudo()
        # Only pre-empt with the friendlier redirect for users who could
        # actually act on it -- everyone else keeps the mixin's own
        # AccessError, unchanged, via super() below.
        if self.env.user.has_group("base.group_system") and (
            not config.get_param("google_gmail_client_id")
            or not config.get_param("google_gmail_client_secret")
        ):
            settings_action = self.env.ref("base_setup.action_general_configuration")
            raise RedirectWarning(
                self.env._(
                    "Gmail OAuth is not set up on this instance yet: no "
                    "Google Client ID/Secret is configured. An "
                    "administrator must go to Settings, then General "
                    "Settings, then under Emails enable 'Custom Email "
                    "Servers', then fill in the Gmail Client ID and "
                    "Client Secret under 'Use a Gmail Server' and "
                    "save. Come back here afterwards and click 'Connect "
                    "to Gmail' again."
                ),
                settings_action.id,
                self.env._("Go to General Settings"),
            )
        return super().open_google_gmail_uri()

    # ------------------------------------------------------------
    # Connection helpers -- short-lived, connection-per-call, exactly like
    # conversation_imap: no socket is ever held between two requests. Auth
    # is XOAUTH2 instead of a password login.
    # ------------------------------------------------------------

    def _get_imap_client_class(self):
        return imaplib.IMAP4_SSL

    def _get_smtp_client_class(self):
        return smtplib.SMTP

    def _gmail_oauth2_string(self):
        self.ensure_one()
        if not self.login or not self.google_gmail_refresh_token:
            raise UserError(
                self.env._(
                    "Connect %(transport)s to Gmail (Settings) before "
                    "using it.",
                    transport=self.display_name,
                )
            )
        return self._generate_oauth2_string(self.login, self.google_gmail_refresh_token)

    @contextmanager
    def _imap_connection(self):
        self.ensure_one()
        auth_string = self._gmail_oauth2_string()
        client_cls = self._get_imap_client_class()
        connection = client_cls(GMAIL_IMAP_HOST, GMAIL_IMAP_PORT)
        try:
            connection.authenticate("XOAUTH2", lambda _resp: auth_string.encode())
            connection.select(self.imap_folder or "INBOX")
            yield connection
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("Gmail IMAP close failed (ignored)", exc_info=True)
            try:
                connection.logout()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("Gmail IMAP logout failed (ignored)", exc_info=True)

    @contextmanager
    def _smtp_connection(self):
        self.ensure_one()
        auth_string = self._gmail_oauth2_string()
        client_cls = self._get_smtp_client_class()
        connection = client_cls(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT)
        try:
            connection.starttls()
            code, _response = connection.docmd(
                "AUTH",
                "XOAUTH2 " + base64.b64encode(auth_string.encode()).decode(),
            )
            if code != 235:
                raise UserError(
                    self.env._(
                        "Gmail SMTP authentication failed for "
                        "%(transport)s.",
                        transport=self.display_name,
                    )
                )
            yield connection
        finally:
            try:
                connection.quit()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("Gmail SMTP quit failed (ignored)", exc_info=True)

    def _imap_page_size(self):
        return DEFAULT_PAGE_SIZE

    # ------------------------------------------------------------
    # Hooks -- structurally identical to conversation_imap's (both are
    # IMAP under the hood), only the connection/auth layer differs, so the
    # RFC822 parsing itself is shared via conversation_base.tools.mime.
    # ------------------------------------------------------------

    def _browse(self, query=None, page=1):
        self.ensure_one()
        page = max(page, 1)
        page_size = self._imap_page_size()
        with self._imap_connection() as connection:
            typ, data = connection.uid("search", None, query or "ALL")
            if typ != "OK":
                raise UserError(
                    self.env._(
                        "Gmail search failed for %(transport)s.",
                        transport=self.display_name,
                    )
                )
            uids = data[0].split()
            uids.reverse()  # newest first
            start = (page - 1) * page_size
            page_uids = uids[start : start + page_size]
            items = [self._imap_fetch_stub(connection, uid) for uid in page_uids]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "has_more": len(uids) > start + page_size,
        }

    def _search_remote(self, criteria):
        self.ensure_one()
        query = self._imap_build_search_query(criteria or {})
        return self._browse(query=query, page=1)

    def _imap_build_search_query(self, criteria):
        parts = []
        if criteria.get("subject"):
            parts.append('SUBJECT "%s"' % criteria["subject"].replace('"', ""))
        if criteria.get("from_"):
            parts.append('FROM "%s"' % criteria["from_"].replace('"', ""))
        if criteria.get("to"):
            parts.append('TO "%s"' % criteria["to"].replace('"', ""))
        if criteria.get("since"):
            parts.append("SINCE %s" % criteria["since"])
        return " ".join(parts) if parts else "ALL"

    def _fetch(self, external_id):
        self.ensure_one()
        cache_key = (self.id, external_id)
        cached = _ENVELOPE_CACHE.get(cache_key)
        if cached is not None:
            return cached
        uid = external_id.encode() if isinstance(external_id, str) else external_id
        with self._imap_connection() as connection:
            typ, data = connection.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not data or data[0] is None:
                raise UserError(
                    self.env._(
                        "Could not fetch message %(external_id)s on "
                        "%(transport)s.",
                        external_id=external_id,
                        transport=self.display_name,
                    )
                )
            raw_bytes = data[0][1]
        raw = {"external_id": external_id, "rfc822": raw_bytes}
        _ENVELOPE_CACHE[cache_key] = raw
        return raw

    def _imap_fetch_stub(self, connection, uid):
        cache_key = (self.id, uid.decode() if isinstance(uid, bytes) else uid)
        cached = _ENVELOPE_CACHE.get(("stub", *cache_key))
        if cached is not None:
            return cached
        typ, data = connection.uid(
            "fetch",
            uid,
            "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID)])",
        )
        header_bytes = b""
        if typ == "OK" and data and data[0]:
            header_bytes = data[0][1]
        headers = email.message_from_bytes(header_bytes, policy=email.policy.default)
        external_id = uid.decode() if isinstance(uid, bytes) else str(uid)
        stub = {
            "external_id": external_id,
            "subject": headers.get("Subject", ""),
            "email_from": mime.first_address(headers.get("From", "")),
            "to": mime.addresses(headers.get("To", "")),
            "cc": mime.addresses(headers.get("Cc", "")),
            "date": mime.parse_date(headers.get("Date")),
            "message_id": (headers.get("Message-Id") or "").strip(),
        }
        _ENVELOPE_CACHE[("stub", *cache_key)] = stub
        return stub

    def _normalize(self, raw):
        self.ensure_one()
        message = email.message_from_bytes(
            raw["rfc822"], policy=email.policy.default
        )
        return {
            "external_id": raw.get("external_id"),
            "message_id": (message.get("Message-Id") or "").strip(),
            "subject": message.get("Subject", ""),
            "email_from": mime.first_address(message.get("From", "")),
            "to": mime.addresses(message.get("To", "")),
            "cc": mime.addresses(message.get("Cc", "")),
            "date": mime.parse_date(message.get("Date")),
            "body": mime.extract_body(message),
            "in_reply_to": (message.get("In-Reply-To") or "").strip(),
            "references": (message.get("References") or "").strip(),
        }

    def _match_inbound(self, raw):
        """Within-transport correlation only -- see conversation_imap's
        equivalent hook; identical logic, shared via tools.mime."""
        self.ensure_one()
        message = email.message_from_bytes(
            raw["rfc822"], policy=email.policy.default
        )
        candidates = mime.correlation_candidates(message)
        if not candidates:
            return self.env["mail.message"]
        return self.env["mail.message"].search(
            [
                ("transport_id", "=", self.id),
                ("external_id", "in", list(candidates)),
            ],
            limit=1,
        )

    def _send(self, conversation, message, recipients=None):
        self.ensure_one()
        to_emails = recipients or self._imap_default_recipients(conversation)
        if not to_emails:
            raise UserError(
                self.env._(
                    "No recipient to send to on %(transport)s.",
                    transport=self.display_name,
                )
            )
        outgoing = EmailMessage()
        outgoing["Subject"] = message.subject or conversation.name
        outgoing["From"] = self.login
        outgoing["To"] = ", ".join(to_emails)
        native_message_id = make_msgid()
        outgoing["Message-Id"] = native_message_id
        in_reply_to = self._imap_reply_headers(conversation, message)
        if in_reply_to:
            outgoing["In-Reply-To"] = in_reply_to
            outgoing["References"] = in_reply_to
        outgoing.set_content(message.body or "", subtype="html")

        with self._smtp_connection() as connection:
            connection.send_message(outgoing)
        return native_message_id.strip("<>")

    def _imap_default_recipients(self, conversation):
        participants = conversation.participant_ids.filtered(
            lambda p: p.role in ("to", "requester") and p.email_normalized
        )
        return [p.email_normalized for p in participants]

    def _imap_reply_headers(self, conversation, message):
        previous = conversation.message_ids.filtered(
            lambda m: m.transport_id == self and m.external_id and m.id != message.id
        ).sorted("id")
        return previous[-1:].external_id if previous else False

    def _subscribe_push(self):
        self.ensure_one()
        raise NotImplementedError(
            "conversation_gmail is v1: browse/fetch/send over IMAP/SMTP-"
            "XOAUTH2 only. Native Gmail API push (X-GM-RAW, watch) is a "
            "v1.1 follow-up; pushable stays False."
        )
