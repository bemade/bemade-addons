Forward one message, or a whole conversation, like an email.

* The forward is composed as a classic "Fwd:" email (quoted
  `---------- Forwarded message ---------` blocks, original attachments
  optional) and delivered **only** through the conversation transport's own
  send primitive, to any To / Cc / Bcc address -- the recipient does not
  need to be a partner or a participant. The recipients are never added to
  the conversation's participants.
* The forward goes out from the selected transport's own identity, never
  from the original sender.
* The exchange is recorded as a quiet internal note without any transport
  or external id, so it can never become the anchor a later reply threads
  against. Bcc recipients are never recorded.

Notification safety: Odoo's native Forward and Reply-All message actions
send email to external partners through the notification pipeline. They are
hidden on conversation chatters only (every other model is unchanged); use
this module's "Forward" action instead.
