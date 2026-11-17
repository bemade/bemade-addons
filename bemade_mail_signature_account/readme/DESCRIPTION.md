Invoicing opt-out for `bemade_mail_signature`, installed automatically when both
are present.

Invoice templates usually carry their own signature (e.g. the billing team's).
Customer invoices and credit notes sent from the invoice send window
(`account.move.send.wizard`, the « Send » button, and batch sending through the
same model) therefore carry **no personal signature**:

- the text of the template, built-in signature included, is shown in the send
  window and sent exactly as rendered: nothing is appended and nothing is
  removed;
- Odoo's own author signature (added by the notification layout, invisible in
  the send window) is turned off on that path, as is the responsible user's
  signature of the invoice layout;
- `bemade_mail_signature` adds nothing either.

Messages written in the invoice's chatter (« Send message ») keep the normal
`bemade_mail_signature` behaviour.
