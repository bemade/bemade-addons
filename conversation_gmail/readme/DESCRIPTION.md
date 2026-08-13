Gmail `conversation.transport` provider (task #3965). Opt-in: install this
module on top of `conversation_imap` to browse/send through a Gmail account
in-Odoo, authenticated with OAuth2/XOAUTH2 -- no password is ever stored
(Gmail killed app-passwords).

## Why

Depends on `conversation_imap` and reuses its browse/search/fetch/normalize/
match/send implementation as-is -- Gmail is IMAP under the hood, so there is
exactly one implementation of each, not a second copy. This module supplies
only what actually differs: OAuth credentials/tokens (`google.gmail.mixin`'s
XOAUTH2, RFC 7628 -- Odoo's own Gmail OAuth scaffolding, reused rather than
reimplemented) and the one hook (`_imap_oauth_string`) `conversation_imap`'s
connection helpers call to authenticate with a token instead of a password.

The moment an account connects, `imap_host`/`imap_port`/`smtp_host`/
`smtp_port` are populated to Gmail's fixed endpoints (`imap.gmail.com`,
`smtp.gmail.com`) and `login` is derived from Google's own userinfo response
for the connected account -- never typed by the user. This is also what
fixes the original "Configure the IMAP host and login" crash on browsing a
connected Gmail account (task #3965 staging-review, 2026-08-13): that bug
was two provider modules each independently overriding the same method
names (`_browse`, `_imap_connection`, ...) on the shared
`conversation.transport` model, with whichever module happened to load last
clobbering the other's implementation for every transport, Gmail included.
Making Gmail depend on and extend `conversation_imap`, instead of
duplicating it, removes that hazard structurally.

## Per-account OAuth credentials (AC4)

`client_id`/`client_secret` on the account override the instance-wide
`google_gmail_client_id`/`google_gmail_client_secret` (Settings ▸ General
Settings ▸ Emails ▸ "Use a Gmail Server") when set, falling back to them
otherwise. One Gmail provider, not two: a Google Workspace org shares the
instance-wide pair (the common case, both fields left blank on the account);
an individual user connecting a personal Gmail account brings their own
Google Cloud OAuth client instead. Both resolve correctly side by side on
the same instance. `client_secret` is `groups="base.group_system"`, matching
the OAuth token fields -- a credential, not readable by an ordinary user.

## Known limitation -- admin-only OAuth connect

`google.gmail.mixin`'s OAuth fields (`google_gmail_refresh_token` and
friends) are `groups='base.group_system'`, and `open_google_gmail_uri()`
explicitly requires `base.group_system` -- this mixin was built for a
single shared company mail server (`ir.mail_server`/`fetchmail.server`),
configured once by an administrator. Reused here for a *per-user* personal
Gmail transport, that means only an administrator can actually run the
"Connect to Gmail" OAuth flow on a `conversation.transport` record today,
even though the record itself may carry a `user_id` (i.e. any user's
Settings ▸ My Mail Accounts transport must currently be connected *for*
them by an admin, not by the user themselves). This is a real product gap
against the design's "a user can connect their own mail account(s)" intent
(AC4) -- flagged in the task's implementation notes for a follow-up
decision (e.g. a thin controller that lets a user complete their own
consent flow while still writing the group_system-restricted token fields
via `sudo()`).

## Prerequisite -- OAuth Client ID/Secret (instance-wide or per-account)

Before *any* account can be connected, either the account itself needs its
own Client ID/Secret (see above), or an administrator must register a
Google OAuth Client ID/Secret for the whole instance under Settings ▸
General Settings ▸ Emails ▸ Custom Email Servers ▸ Use a Gmail Server (this
sets the `google_gmail_client_id`/`google_gmail_client_secret`
`ir.config_parameter`s `google.gmail.mixin` falls back to). If neither is
configured, clicking "Connect to Gmail" on a `conversation.transport` record
raises a `RedirectWarning` that takes the admin straight to General
Settings with an explanation, instead of the bare "Please configure your
Gmail credentials." dead end the mixin raises by default (task #3965
staging-review fix, 2026-08-13). Registering the Google Cloud OAuth app
itself (the actual Client ID/Secret values) is a one-time, per-client/
per-instance ops task, not something any module can do for you.

## Security note

The `password` field is inherited from `conversation_imap` (it's the same
`conversation.transport` model) but is never populated or read for a Gmail
account -- authentication is XOAUTH2 only, built fresh per connection from
`google.gmail.mixin`'s OAuth tokens. `client_secret` is field-security
restricted like those tokens (see above).
