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
from odoo.exceptions import UserError
from odoo.tools.lru import LRU

_logger = logging.getLogger(__name__)

# Per-process, per-(transport, uid) envelope cache. Deliberately module-level
# (not per-record/per-request): the point is to avoid re-parsing the same
# message twice within a short span of page views, without ever holding an
# IMAP/SMTP socket open between requests -- the cache stores parsed dicts
# only, never a connection.
_ENVELOPE_CACHE = LRU(512)

DEFAULT_PAGE_SIZE = 25


class ConversationTransport(models.Model):
    """Generic IMAP/SMTP transport -- the *one* browse/fetch/normalize/send
    implementation for every IMAP-speaking provider. A manually-configured
    account authenticates with ``login``/``password``; an OAuth-connected
    account (``conversation_gmail``, a future ``conversation_outlook``, ...)
    authenticates with XOAUTH2 instead by overriding ``_imap_oauth_string``
    -- the connection/browse/fetch/normalize/send code path itself is never
    duplicated per provider (task #3965, blocking issue #1)."""

    _inherit = "conversation.transport"

    provider = fields.Selection(
        selection_add=[("imap", "IMAP / Generic Email")],
        ondelete={"imap": "cascade"},
        default="imap",
    )

    imap_host = fields.Char(string="IMAP Server")
    imap_port = fields.Integer(string="IMAP Port", default=993)
    imap_ssl = fields.Boolean(string="IMAP over SSL", default=True)
    imap_folder = fields.Char(string="IMAP Folder", default="INBOX")
    smtp_host = fields.Char(string="SMTP Server")
    smtp_port = fields.Integer(string="SMTP Port", default=587)
    smtp_ssl = fields.Boolean(
        string="SMTP over STARTTLS",
        default=True,
        help="Use STARTTLS on the SMTP connection (the common case on port "
        "587). Leave off only for a plain/legacy relay.",
    )
    password = fields.Char(
        help="IMAP/SMTP account password. Generic IMAP has no universal "
        "OAuth mechanism, so this stays a plain stored secret -- scoped "
        "like the rest of conversation.transport by the conversation_base "
        "ir.rule (own + shared transports only). Left blank on an "
        "OAuth-connected account (conversation_gmail, ...): those "
        "authenticate with a token instead, never a stored password.",
    )

    # ------------------------------------------------------------
    # Connection helpers -- short-lived, connection-per-call. Never stored
    # on self / never held across two separate hook invocations, so an
    # inbox page view or a send never keeps a socket open between requests.
    # The client classes are looked up through small factory methods so
    # tests can substitute fakes without patching the stdlib.
    # ------------------------------------------------------------

    def _get_imap_client_class(self):
        return imaplib.IMAP4_SSL if self.imap_ssl else imaplib.IMAP4

    def _get_smtp_client_class(self):
        return smtplib.SMTP

    def _imap_oauth_string(self, force_refresh=False):
        """Hook: return a SASL XOAUTH2 string to authenticate this
        transport via OAuth, or ``None`` to fall back to a plain
        ``login``/``password`` login. Generic IMAP has no OAuth of its
        own -- always ``None`` here. OAuth-capable providers
        (``conversation_gmail``, a future ``conversation_outlook``, ...)
        override this; they do **not** need to touch ``_imap_connection``/
        ``_smtp_connection`` themselves.

        ``force_refresh=True`` asks the provider to discard any cached
        access token and fetch a fresh one -- used for the
        retry-once-on-auth-failure path below, for the case a token goes
        stale between the provider's own pre-flight expiry check and the
        actual IMAP/SMTP round trip (e.g. revoked/rotated out of band).
        """
        self.ensure_one()
        return None

    @contextmanager
    def _imap_connection(self):
        self.ensure_one()
        if not self.imap_host or not self.login:
            raise UserError(
                self.env._(
                    "Configure the IMAP host and login before browsing "
                    "%(transport)s.",
                    transport=self.display_name,
                )
            )
        # pylint: disable=assignment-from-none
        # _imap_oauth_string is a soft/optional hook (unlike the
        # abstract, NotImplementedError-raising hooks on
        # conversation.transport): the base always returns None by
        # design, an OAuth-capable provider module (conversation_gmail,
        # ...) overrides it -- pylint only sees this file's own
        # definition, not the cross-module override.
        oauth_string = self._imap_oauth_string()
        client_cls = self._get_imap_client_class()
        connection = client_cls(self.imap_host, self.imap_port or 993)
        try:
            if oauth_string:
                self._imap_xoauth2_login(connection, oauth_string)
            else:
                connection.login(self.login, self.password or "")
            connection.select(self.imap_folder or "INBOX")
            yield connection
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("IMAP close failed (ignored)", exc_info=True)
            try:
                connection.logout()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("IMAP logout failed (ignored)", exc_info=True)

    def _imap_xoauth2_login(self, connection, oauth_string):
        """XOAUTH2 SASL authenticate; on an auth failure, ask the provider
        for a freshly-refreshed token and retry exactly once."""
        try:
            connection.authenticate("XOAUTH2", lambda _resp: oauth_string.encode())
        except imaplib.IMAP4.error:
            refreshed = self._imap_oauth_string(  # pylint: disable=assignment-from-none
                force_refresh=True
            )
            if not refreshed:
                raise
            connection.authenticate("XOAUTH2", lambda _resp: refreshed.encode())

    @contextmanager
    def _smtp_connection(self):
        self.ensure_one()
        if not self.smtp_host or not self.login:
            raise UserError(
                self.env._(
                    "Configure the SMTP host and login before sending from "
                    "%(transport)s.",
                    transport=self.display_name,
                )
            )
        oauth_string = self._imap_oauth_string()  # pylint: disable=assignment-from-none
        client_cls = self._get_smtp_client_class()
        connection = client_cls(self.smtp_host, self.smtp_port or 587)
        try:
            if self.smtp_ssl:
                connection.starttls()
            if oauth_string:
                self._smtp_xoauth2_login(connection, oauth_string)
            else:
                connection.login(self.login, self.password or "")
            yield connection
        finally:
            try:
                connection.quit()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("SMTP quit failed (ignored)", exc_info=True)

    def _smtp_xoauth2_login(self, connection, oauth_string):
        """SMTP has no built-in XOAUTH2 SASL helper (unlike imaplib), so
        this issues the raw ``AUTH XOAUTH2`` command directly; on failure,
        ask the provider for a freshly-refreshed token and retry once."""
        code, _response = connection.docmd(
            "AUTH", "XOAUTH2 " + base64.b64encode(oauth_string.encode()).decode()
        )
        if code != 235:
            refreshed = self._imap_oauth_string(  # pylint: disable=assignment-from-none
                force_refresh=True
            )
            if refreshed:
                code, _response = connection.docmd(
                    "AUTH",
                    "XOAUTH2 " + base64.b64encode(refreshed.encode()).decode(),
                )
        if code != 235:
            raise UserError(
                self.env._(
                    "SMTP XOAUTH2 authentication failed for %(transport)s.",
                    transport=self.display_name,
                )
            )

    def _imap_page_size(self):
        return DEFAULT_PAGE_SIZE

    # ------------------------------------------------------------
    # Hooks
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
                        "IMAP search failed for %(transport)s.",
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
        """Translate a light criteria dict (``subject``, ``from_``, ``to``,
        ``since``) into an IMAP SEARCH query string. Unrecognized/empty
        criteria fall back to ``ALL``."""
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
        uid = self._imap_uid_for_external_id(external_id)
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

    def _imap_uid_for_external_id(self, external_id):
        """A message's ``external_id`` on this provider *is* its IMAP UID
        (see ``_imap_fetch_stub``/``_normalize``), so no extra round trip
        is needed to resolve one from the other."""
        return external_id.encode() if isinstance(external_id, str) else external_id

    def _imap_fetch_stub(self, connection, uid):
        """Cheap per-message metadata for a browse page: headers only, no
        body download (the body is fetched lazily via ``_fetch``/
        ``fetch_envelope`` only when a human expands the item)."""
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
            "attachments": mime.extract_attachments(message),
            "in_reply_to": (message.get("In-Reply-To") or "").strip(),
            "references": (message.get("References") or "").strip(),
        }

    def _match_inbound(self, raw):
        """Within-transport correlation only: look up an existing
        ``mail.message`` on *this* transport whose ``external_id`` matches
        one of the raw message's References/In-Reply-To message-ids."""
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
        """The most recent inbound message on this conversation carrying an
        ``external_id`` on this same transport, used to thread an outbound
        reply's In-Reply-To/References (within-transport correlation)."""
        previous = conversation.message_ids.filtered(
            lambda m: m.transport_id == self and m.external_id and m.id != message.id
        ).sorted("id")
        return previous[-1:].external_id if previous else False

    def _subscribe_push(self):
        self.ensure_one()
        raise NotImplementedError(
            "conversation_imap is poll/browse-only; pushable stays False."
        )
