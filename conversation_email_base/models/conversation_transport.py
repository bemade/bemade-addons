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
from odoo.tools.mail import html2plaintext

_logger = logging.getLogger(__name__)

# Per-process, per-(transport, uid) envelope cache. Deliberately module-level
# (not per-record/per-request): the point is to avoid re-parsing the same
# message twice within a short span of page views, without ever holding an
# IMAP/SMTP socket open between requests -- the cache stores parsed dicts
# only, never a connection.
_ENVELOPE_CACHE = LRU(512)

DEFAULT_PAGE_SIZE = 25


class ConversationTransport(models.Model):
    """The *one* IMAP/SMTP browse/fetch/normalize/match/send implementation,
    shared by every email-speaking provider (``conversation_imap``,
    ``conversation_gmail``, a future ``conversation_outlook``, ...). Only
    the connection layer differs between them -- endpoints and
    authentication -- so that is all a provider module supplies:

    * ``_email_providers()`` -- register the provider's ``provider`` code,
      so the engine knows this transport is one of its own;
    * ``_email_connection_params()`` -- the IMAP/SMTP endpoints and the
      password (if any) for that provider;
    * ``_imap_oauth_string()`` -- optional; return a SASL XOAUTH2 string to
      authenticate via OAuth instead of ``login``/``password``.

    **Dispatch is on the ``provider`` value, never on module load order.**
    Two provider modules installed side by side both extend
    ``conversation.transport``, so whichever module Odoo happens to load
    last would otherwise silently shadow the other's overrides (which is
    exactly how a Gmail transport ended up being asked for a generic
    ``imap_host`` it has no reason to carry). Every provider override
    therefore early-returns ``super()`` when ``self.provider`` is not its
    own -- the ``payment.provider`` pattern -- and the engine's own
    overrides likewise defer to ``super()`` for a non-email transport, so a
    non-email provider (SMS, WhatsApp, ...) still gets
    ``conversation_base``'s abstract hooks untouched.
    """

    _inherit = "conversation.transport"

    imap_folder = fields.Char(string="IMAP Folder", default="INBOX")

    # ------------------------------------------------------------
    # Provider registration + dispatch
    # ------------------------------------------------------------

    def _email_providers(self):
        """Provider codes served by this IMAP/SMTP engine. Each provider
        module appends its own (``super()._email_providers() + ["imap"]``);
        this module implements no provider itself."""
        return []

    def _is_email_transport(self):
        """Whether the engine below owns this record, i.e. whether its
        ``provider`` is one an installed email provider module
        registered."""
        self.ensure_one()
        return self.provider in self._email_providers()

    def _email_connection_params(self):
        """Endpoints + credentials for this transport's provider, as a
        dict: ``imap_host``, ``imap_port``, ``imap_ssl``, ``smtp_host``,
        ``smtp_port``, ``smtp_starttls``, ``password``. Overridden by each
        provider module, guarded on its own ``provider`` value.

        ``login`` is not part of this: it lives on ``conversation.transport``
        itself and is the same field for every provider.
        """
        self.ensure_one()
        raise NotImplementedError(
            "%s registered provider %r on the email engine but implements "
            "no _email_connection_params for it."
            % (self._name, self.provider)
        )

    # ------------------------------------------------------------
    # Connection helpers -- short-lived, connection-per-call. Never stored
    # on self / never held across two separate hook invocations, so an
    # inbox page view or a send never keeps a socket open between requests.
    # The client classes are looked up through small factory methods so
    # tests can substitute fakes without patching the stdlib.
    # ------------------------------------------------------------

    def _get_imap_client_class(self, use_ssl=True):
        return imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4

    def _get_smtp_client_class(self):
        return smtplib.SMTP

    def _imap_oauth_string(self, force_refresh=False):
        """Hook: return a SASL XOAUTH2 string to authenticate this
        transport via OAuth, or ``None`` to fall back to a plain
        ``login``/``password`` login. Generic IMAP has no OAuth of its
        own, so the default is ``None``; OAuth-capable providers
        (``conversation_gmail``, a future ``conversation_outlook``, ...)
        override this and do **not** need to touch ``_imap_connection``/
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
        params = self._email_connection_params()
        if not params.get("imap_host") or not self.login:
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
        client_cls = self._get_imap_client_class(use_ssl=params.get("imap_ssl", True))
        connection = client_cls(params["imap_host"], params.get("imap_port") or 993)
        try:
            if oauth_string:
                self._imap_xoauth2_login(connection, oauth_string)
            else:
                connection.login(self.login, params.get("password") or "")
            self._imap_select(connection)
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
        params = self._email_connection_params()
        if not params.get("smtp_host") or not self.login:
            raise UserError(
                self.env._(
                    "Configure the SMTP host and login before sending from "
                    "%(transport)s.",
                    transport=self.display_name,
                )
            )
        oauth_string = self._imap_oauth_string()  # pylint: disable=assignment-from-none
        client_cls = self._get_smtp_client_class()
        connection = client_cls(params["smtp_host"], params.get("smtp_port") or 587)
        try:
            if params.get("smtp_starttls", True):
                connection.starttls()
            if oauth_string:
                self._smtp_xoauth2_login(connection, oauth_string)
            else:
                connection.login(self.login, params.get("password") or "")
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

    def _imap_mailbox(self):
        """The configured folder as an IMAP mailbox argument, **quoted**.
        imaplib passes the name through verbatim, so an unquoted folder
        containing a space is parsed as two arguments and the SELECT
        fails -- which is every one of Gmail's own special folders
        (``[Gmail]/Sent Mail``, ``[Gmail]/All Mail``, ...). The embedded
        quote/backslash strip keeps a hand-typed folder name from
        breaking out of the quoted string."""
        self.ensure_one()
        folder = (self.imap_folder or "INBOX").replace("\\", "").replace('"', "")
        return '"%s"' % folder

    def _imap_select(self, connection):
        """SELECT the configured mailbox; return how many messages it
        holds (the untagged EXISTS count, which is what ``select`` returns
        on success)."""
        self.ensure_one()
        typ, data = connection.select(self._imap_mailbox())
        if typ != "OK":
            raise UserError(
                self.env._(
                    "Could not open folder %(folder)s on %(transport)s.",
                    folder=self.imap_folder or "INBOX",
                    transport=self.display_name,
                )
            )
        try:
            return int(data[0])
        except (IndexError, TypeError, ValueError):
            return 0

    # ------------------------------------------------------------
    # conversation.transport hooks
    # ------------------------------------------------------------

    def _browse(self, query=None, page=1):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._browse(query=query, page=page)
        page = max(page, 1)
        page_size = self._imap_page_size()
        with self._imap_connection() as connection:
            if query:
                page_uids, has_more = self._imap_query_page(
                    connection, query, page, page_size
                )
            else:
                page_uids, has_more = self._imap_sequence_page(
                    connection, page, page_size
                )
            items = [self._imap_fetch_stub(connection, uid) for uid in page_uids]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }

    def _imap_sequence_page(self, connection, page, page_size):
        """One page of UIDs, newest first, without ever asking the server
        for the whole mailbox.

        The obvious ``UID SEARCH ALL`` is unusable on a real mailbox: the
        server answers with *every* UID on a single line, and imaplib
        refuses to read a line past ``_MAXLINE`` (1 MB), which a mailbox
        of a few hundred thousand messages exceeds -- so opening the inbox
        failed outright, having transferred megabytes to display 25 rows.

        Sequence numbers are 1..EXISTS in mailbox order (oldest first), so
        the newest page is the top of that range, and searching within
        that range bounds the response to at most ``page_size`` UIDs. The
        subsequent FETCH still goes by UID, so nothing downstream changes.
        Sequence numbers do shift if mail arrives or is expunged between
        two page requests -- the same small race every IMAP client paging
        this way accepts, and the ingest-on-action design means nothing is
        persisted from a browse page anyway.
        """
        # Re-SELECT (the connection context manager already selected once)
        # purely to read a fresh EXISTS count: one round trip against the
        # per-message FETCHes this page is about to do.
        total = self._imap_select(connection)
        start = (page - 1) * page_size
        if start >= total:
            return [], False
        high = total - start
        low = max(1, high - page_size + 1)
        typ, data = connection.uid("search", None, "%d:%d" % (low, high))
        if typ != "OK":
            raise UserError(
                self.env._(
                    "IMAP search failed for %(transport)s.",
                    transport=self.display_name,
                )
            )
        uids = (data[0] or b"").split()
        uids.reverse()  # newest first
        return uids, low > 1

    def _imap_query_page(self, connection, query, page, page_size):
        """One page of UIDs matching an explicit search query. A query is
        the user's own narrowing, so it is issued as-is and paged in
        Python; a query broad enough to still overrun imaplib's line limit
        surfaces as an ask-for-something-narrower error rather than an
        opaque protocol failure."""
        try:
            typ, data = connection.uid("search", None, query)
        except imaplib.IMAP4.error as error:
            raise UserError(
                self.env._(
                    "The search returned too many results on "
                    "%(transport)s. Narrow it down (add a sender, a "
                    "subject or a date) and try again.",
                    transport=self.display_name,
                )
            ) from error
        if typ != "OK":
            raise UserError(
                self.env._(
                    "IMAP search failed for %(transport)s.",
                    transport=self.display_name,
                )
            )
        uids = (data[0] or b"").split()
        uids.reverse()  # newest first
        start = (page - 1) * page_size
        return uids[start : start + page_size], len(uids) > start + page_size

    def _search_remote(self, criteria):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._search_remote(criteria)
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
        if not self._is_email_transport():
            return super()._fetch(external_id)
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
        """A message's ``external_id`` on an IMAP-speaking provider *is*
        its IMAP UID (see ``_imap_fetch_stub``/``_normalize``), so no extra
        round trip is needed to resolve one from the other."""
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
        if not self._is_email_transport():
            return super()._normalize(raw)
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
        if not self._is_email_transport():
            return super()._match_inbound(raw)
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
        if not self._is_email_transport():
            return super()._send(conversation, message, recipients=recipients)
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
        # Put the message's OWN Message-Id on the wire rather than
        # minting a second one (what mail.mail does too): the id a
        # recipient will quote back in In-Reply-To is then the one
        # mail.message already stores, so a later inbound reply correlates
        # against it with nothing extra to persist.
        native_message_id = message.message_id or make_msgid()
        outgoing["Message-Id"] = native_message_id
        in_reply_to = self._imap_reply_headers(conversation, message)
        if in_reply_to:
            outgoing["In-Reply-To"] = in_reply_to
            outgoing["References"] = in_reply_to
        body = self._email_prepare_body(message.body or "")
        # multipart/alternative: a text/plain part alongside the HTML.
        # An HTML-only message is treated as a spam signal by several
        # filters and is unreadable in a plaintext client.
        outgoing.set_content(html2plaintext(body) if body else "")
        outgoing.add_alternative(body, subtype="html")

        with self._smtp_connection() as connection:
            connection.send_message(outgoing)
        return native_message_id.strip("<>")

    def _email_prepare_body(self, body):
        """Make an Odoo-composed HTML body safe to read outside Odoo:
        rewrite root-relative links to absolute ones, exactly as
        ``mail_mail`` does before sending. Without it a link to an
        attachment or an inline image goes out as ``/web/content/...``,
        which resolves against the recipient's own mail client (``mail://
        vfolder/...`` in Thunderbird) and arrives dead."""
        self.ensure_one()
        if not body:
            return body
        return self.env["mail.render.mixin"]._replace_local_links(body)

    def _imap_default_recipients(self, conversation):
        participants = conversation.participant_ids.filtered(
            lambda p: p.role in ("to", "requester") and p.email_normalized
        )
        return [p.email_normalized for p in participants]

    def _imap_reply_headers(self, conversation, message):
        """The RFC822 Message-Id to thread an outbound reply against:
        the most recent message on this conversation that actually
        travelled over this transport.

        ``external_id`` is deliberately *not* that id. On an inbound
        capture it holds the IMAP UID (a per-mailbox integer like
        ``227398``), so using it produced an ``In-Reply-To: 227398`` that
        matches nothing in the recipient's client and threads nowhere;
        ``message_id`` is the real, angle-bracketed RFC id. It is still
        ``external_id`` that marks a message as having come over a
        transport at all, which is why it is required here -- an ordinary
        internal note also carries an Odoo-generated ``message_id``, but
        no correspondent has ever seen it.

        Provenance follows ``_find_captured``'s convention: a quiet-
        captured inbound note carries a falsy ``transport_id`` by design
        (the notification-safety marker), so for those the conversation's
        ``primary_transport_id`` is what identifies the transport.
        """
        previous = conversation.message_ids.filtered(
            lambda m: m.id != message.id
            and m.external_id
            and m.message_id
            and (
                m.transport_id == self
                or (
                    not m.transport_id
                    and conversation.primary_transport_id == self
                )
            )
        ).sorted("id")
        return previous[-1:].message_id if previous else False

    def _subscribe_push(self):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._subscribe_push()
        raise NotImplementedError(
            "The IMAP/SMTP engine is poll/browse-only; pushable stays False."
        )
