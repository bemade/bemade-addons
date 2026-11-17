Bridge between `bemade_mail_signature` and Invoicing, installed automatically
when both are present.

Customer invoices and credit notes are sent through the invoice send wizard
(`account.move.send.wizard`), not through the mail composer. This module applies
the same rule there: the email carries exactly one signature, the sender's,
shown at the end of the text in the wizard, where it can be edited before
sending.

- The user signatures the template printed (the invoice's salesperson, the
  current user) are removed from the rendered text, then the sender's signature
  block is appended. In the chatter it is folded under « … ».
- Nothing else is added at send: the email shows the signature exactly once.
- Any module that turns the author signature off for a flow through
  `_notify_by_email_prepare_rendering_context` is honoured: the rendered text is
  then left as it is.
- Invoices sent in batch (without the wizard) are unchanged.
