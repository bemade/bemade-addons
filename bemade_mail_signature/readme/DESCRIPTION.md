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
  single-record comment mode): the sender's signature is appended at the end of the
  rendered template text, where it stays editable. Nothing else is added at send.
  When the rendered text already ends with the sender's signature (templates that
  print the responsible user's signature, when that user is the sender), nothing
  is appended. Mass mailing mode is unchanged.

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

## Other signature previews

If another addon already shows a client-side signature preview in the chatter
composer (an element with class ``o-mail-Composer-signaturePreview``), it is
hidden while this module's preview is shown, so the user sees one block only.
This module's preview offers the same « Remove signature » / « Add signature »
switch (the composer's ``emailAddSignature``): removed, the message is posted
with ``email_add_signature=False`` and the server adds nothing.

## Scope

Depends on ``mail`` only. Invoice sending goes through the Accounting send
wizard (``account.move.send.wizard``), not through ``mail.compose.message``, and
is not covered.
