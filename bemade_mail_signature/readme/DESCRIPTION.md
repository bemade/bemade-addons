Whenever an email leaves Odoo with the sender's signature, this module makes that
signature visible in the composer exactly as it will be sent, and keeps it in the
message logged in the chatter. What is shown is what is sent is what is logged, so
users know what goes out and never type their signature a second time.

## Behaviour

- **Chatter « Send message »** (compact composer): the signature block is shown
  under the text box, read-only, with an « Edit » link that opens the full
  composer and a « Remove signature » link for this message only. In « Log note » mode nothing is shown and nothing is added (no email
  leaves). The block is computed by the server, so it is the exact HTML that is
  appended to the message.
- **Posting**: a comment posted by an internal user with a signature (subtype
  *Discussions*, message type *comment*) gets the signature block appended to its
  body, and the notification layout no longer adds its own copy. The email carries
  the signature exactly once; the chatter shows it folded under « … ».
  Every message gets it, replies included.
- **Full composer with a template** (e.g. « Send by Email » on a document, in
  single-record comment mode): exactly one signature, always the sender's (the
  user who sends, even when the template's sender address is another user's).
  Many templates print a user's signature themselves (salesperson, buyer, current
  user...): every such signature is removed from the rendered text, i.e. the
  signature of the current user and of any user in a stored many2one field of the
  record (``user_id``, ``invoice_user_id``...), with or without the ``--``
  separator. Then the sender's signature block is appended, where it stays
  editable. Nothing else is added at send. A user whose signature is only their
  name (Odoo's default) is removed only after ``--``: a bare name in the text is
  not a signature. Mass mailing mode is unchanged.

## Opt-outs respected

Nothing is added when:

- the caller passes ``email_add_signature=False`` (e.g. the user removed the
  signature in the full composer);
- a custom notification layout (``email_layout_xmlid``) is used on a direct post:
  that layout decides which signature it prints;
- the record's ``_notify_by_email_prepare_rendering_context`` turns the signature
  off (any module that suppresses the author signature for a given flow through
  that hook is honoured by the composer preview, the template composer and the
  post);
- the author is not an internal user, has no signature, or the thread is a
  Discuss channel;
- the body already contains the sender's signature block.

When the signature is turned off for a template flow (e.g. a report email that
carries its own fixed team signature), the rendered text is left exactly as the
template produced it.

## Other signature previews

If another addon already shows a client-side signature preview in the chatter
composer (an element with class ``o-mail-Composer-signaturePreview``), it is
hidden while this module's preview is shown, so the user sees one block only.
This module's preview offers the same « Remove signature » / « Add signature »
switch (the composer's ``emailAddSignature``): removed, the message is posted
with ``email_add_signature=False`` and the server adds nothing.

## Scope

Depends on ``mail`` only. Invoice sending goes through the Accounting send
wizard (``account.move.send.wizard``), not through ``mail.compose.message``: it is
covered by the bridge ``bemade_mail_signature_account`` (auto-installed with
Invoicing).
