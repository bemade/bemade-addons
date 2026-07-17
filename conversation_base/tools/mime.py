"""Pure RFC822/MIME parsing helpers shared by IMAP-speaking transport
providers (``conversation_imap``, ``conversation_gmail`` -- Gmail's
browse/fetch also happen over IMAP, just with XOAUTH2 auth instead of a
password). Plain functions, no ORM/model dependency, so both provider
modules can import them without depending on each other -- only on
``conversation_base``, which they already do.
"""

from email.utils import getaddresses, parsedate_to_datetime

from odoo.tools.mail import plaintext2html


def addresses(header_value):
    """A ``To``/``Cc`` header value -> list of bare email addresses."""
    return [addr for _name, addr in getaddresses([header_value or ""]) if addr]


def first_address(header_value):
    """A ``From`` header value -> its single bare email address, or ''."""
    found = addresses(header_value)
    return found[0] if found else ""


def parse_date(date_header):
    """An RFC822 ``Date`` header -> an aware ``datetime``, or ``False``."""
    if not date_header:
        return False
    try:
        return parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return False


def extract_body(message):
    """Prefer the HTML part of a parsed ``email.message.Message``, fall
    back to plaintext -- escaped and converted via
    ``odoo.tools.plaintext2html`` (never raw-interpolated into HTML, to
    avoid a plaintext body's own angle brackets being rendered as markup);
    never raise on an unusual MIME layout."""
    if message.is_multipart():
        html_part = message.get_body(preferencelist=("html",))
        if html_part is not None:
            return html_part.get_content()
        text_part = message.get_body(preferencelist=("plain",))
        if text_part is not None:
            return plaintext2html(text_part.get_content())
        return ""
    content_type = message.get_content_type()
    content = message.get_content()
    if content_type == "text/html":
        return content
    return plaintext2html(content)


def correlation_candidates(message):
    """A parsed message's In-Reply-To + References headers -> the set of
    message-ids a within-transport ``_match_inbound`` should search
    ``mail.message.external_id`` for."""
    candidates = set()
    in_reply_to = (message.get("In-Reply-To") or "").strip()
    if in_reply_to:
        candidates.add(in_reply_to)
    references = (message.get("References") or "").split()
    candidates.update(ref.strip() for ref in references if ref.strip())
    return candidates
