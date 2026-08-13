Generic IMAP/SMTP `conversation.transport` provider (task #3965). Opt-in:
install this module on top of `conversation_base` to browse a mailbox
in-Odoo and send through it, over plain IMAP/SMTP credentials.

## Why

`conversation_base` defines the transport interface only (capability flags
+ abstract hooks); this module is the first concrete implementation, and the
portability proof that the interface is not Gmail-specific.

- `browsable`/`searchable`/`sendable` = `True`; `pushable` stays `False`
  (IMAP has no native push here -- polling only).
- `_browse`/`_search` list message stubs (headers only -- From/To/Cc/
  Subject/Date/Message-Id) a page at a time; `_fetch`/`_normalize` download
  and parse a single message's full body only when a human expands it in
  the inbox viewer (ingest-on-action: nothing is persisted until then).
- `_match_inbound` correlates a raw message's References/In-Reply-To
  against `mail.message.external_id` **within this same transport only**.
- `_send` composes and delivers over SMTP (STARTTLS by default), setting
  its own Message-Id and, when replying within a conversation, In-Reply-To/
  References so the reply threads on the recipient's side too.
- Connection handling is short-lived and connection-per-call: `_imap_
  connection()`/`_smtp_connection()` are context managers that log in,
  yield, and always log out/close in a `finally` -- no socket is ever held
  between two separate requests. A small per-process LRU cache
  (`_ENVELOPE_CACHE`) avoids re-parsing the same message headers/body
  across nearby page views without needing a live connection to do so.
- `_normalize` decodes MIME parts through `conversation_base.tools.mime`:
  `text/html` preferred, `text/plain` promoted to HTML as a fallback, both
  sanitized through Odoo's own `html_sanitize` before ever reaching the
  inbox viewer; attachments are listed as metadata (filename/content type/
  size), never inlined as encoded payloads.
- Registers `imap` on the shared `provider` Selection (`conversation_base`
  ships no options itself) via `selection_add`.

## The one hook an OAuth-capable provider needs

`_imap_oauth_string(force_refresh=False)` -- return a SASL XOAUTH2 string to
authenticate via OAuth instead of `login`/`password`, or `None` to use the
password path (the default here). `conversation_gmail` is the concrete
example: it depends on this module and overrides only this hook plus its
own credential/token plumbing, inheriting every other hook (`_browse`,
`_fetch`, `_normalize`, `_match_inbound`, `_send`, ...) unchanged -- one
implementation of the IMAP protocol, not one per provider. A future
`conversation_outlook` (Microsoft Graph OAuth, v1.1) would do the same.

## Security note

IMAP still requires a password (there is no universal IMAP OAuth); the
`password` field is an ordinary `Char`, scoped like the rest of
`conversation.transport` by the `conversation_base` `ir.rule` (own + shared
transports only). Left blank on an OAuth-connected account (the login
path above); prefer `conversation_gmail` (OAuth, no stored password)
wherever the provider supports it.
