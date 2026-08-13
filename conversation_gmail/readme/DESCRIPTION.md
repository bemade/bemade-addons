Gmail `conversation.transport` provider (task #3965). Opt-in: install this
module on top of `conversation_base` to browse/send through a Gmail account
in-Odoo, authenticated with OAuth2/XOAUTH2 -- no password is ever stored
(Gmail killed app-passwords).

## Why

Same interface as `conversation_imap` (browsable/searchable/sendable =
True, pushable = False for v1), but Gmail's endpoints (`imap.gmail.com`,
`smtp.gmail.com`) are fixed and authentication is `google.gmail.mixin`'s
XOAUTH2 (RFC 7628) built from an OAuth2 refresh token -- Odoo's own Gmail
OAuth scaffolding, reused as-is rather than reimplemented. RFC822 parsing
(`_normalize`/`_match_inbound`) is shared with `conversation_imap` via
`conversation_base.tools.mime` instead of being duplicated a second time.

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

## Prerequisite -- instance-level Google OAuth Client ID/Secret

Before *any* account can be connected, an administrator must first register
a Google OAuth Client ID/Secret for the whole instance under Settings ▸
General Settings ▸ Emails ▸ Custom Email Servers ▸ Use a Gmail Server (this
sets the `google_gmail_client_id`/`google_gmail_client_secret`
`ir.config_parameter`s that `google.gmail.mixin` needs to build the consent
URL). If those are missing, clicking "Connect to Gmail" on a
`conversation.transport` record now raises a `RedirectWarning` that takes
the admin straight to General Settings with an explanation, instead of the
bare "Please configure your Gmail credentials." dead end the mixin raises
by default (task #3965 staging-review fix, 2026-08-13). Registering the
Google Cloud OAuth app itself (the actual Client ID/Secret values) is a
one-time, per-instance ops/infra task, not something any module can do for
you.

## Security note

No password field exists on this provider at all -- only the OAuth token
columns inherited from `google.gmail.mixin`.
