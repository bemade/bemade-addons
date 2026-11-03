# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: an update is internal, or shared with chosen recipients.

ACCEPTANCE CRITERIA
- Internal only (``internal_only``) is True on a new update, whether created
  from the form or by code. An internal update behaves exactly as in core
  Odoo: no message on the project chatter, no notified partner.
- On the form (driven through ``Form``), unticking Internal only shows the
  recipients (``recipient_ids``), prefilled with the project's followers and
  its portal collaborators, each partner once. They can be edited before
  saving. Ticking it again hides them. Code creating or writing
  ``internal_only=False`` without recipients gets the same prefill.
- Each recipient is emailed ONCE, the first time the update is shared with
  them, by one Discussion message (``mail.mt_comment``) on the project
  addressed to those recipients only. The message holds the update's title,
  status, date and full description, and a link to the project's portal
  updates page. Its fixed wording (status label, link text) is in the
  project customer's language; the update's own content is sent as written.
  * Saving an update shared, on creation or by unticking Internal only,
    emails all its recipients.
  * Adding recipients to a shared update emails only the added ones.
  * Removing recipients, editing the title, status or description, or
    ticking Internal only sends nothing.
  * Unticking Internal only again later emails only recipients never
    emailed about this update.
- A shared update with no recipients sends nothing and is visible to no
  portal user.
"""
