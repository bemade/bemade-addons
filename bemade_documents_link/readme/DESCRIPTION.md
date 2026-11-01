Adds two generic, reusable entry points for linking an **existing** document
(including a spreadsheet) to one or more business records, without uploading
a new file:

* **From the record side** -- a *Link existing document* item appears in the
  cog menu of every `mail.thread` form view. It opens a checked-picker
  wizard defaulting to the documents already linked to the current record;
  saving reconciles the selection (adds newly-checked documents, unlinks
  unchecked ones) and reloads the form.
* **From the Documents side** -- a generic *Link to Record* item is added to
  the Documents app's "Action" dropdown. It lets the user first choose the
  target model (limited to `mail.thread` models) and then the record, reusing
  the stock Documents `link_to_record_wizard`, even for documents already
  linked elsewhere. The dialog closes once the link is made.

A document can be linked to **any number of records across any number of
models** (a plain M2M can't express this, since Odoo M2M targets a single
comodel): a polymorphic `bemade.documents.link` model is the source of truth
for these links. The stock `res_model`/`res_id` pointer is kept in sync as a
"primary" link so the native Documents card keeps working.

Where a link shows up:

* the chatter attachment box of every `mail.thread` record lists the files of
  the documents linked to it, next to its own attachments;
* the *Documents* button of a contact counts and opens the documents linked to
  it, without changing the document's owner contact;
* the *Documents* buttons of products and employees are handled by the thin
  auto-installed glue modules `bemade_documents_link_product` and
  `bemade_documents_link_hr`.

Removing a link only removes it from that record. Deleting, from a chatter, a
file shared by several records is refused, to avoid deleting it everywhere.
