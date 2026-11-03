# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: a project manager shares an update with the client.

ACCEPTANCE CRITERIA
- "Share with Client" on an Internal update opens a wizard (driven through
  ``Form``) whose recipients are prefilled with the project's followers and
  its portal collaborators, each partner once. Recipients can be added and
  removed before confirming.
- Confirming makes the update Shared and posts ONE Discussion message
  (``mail.mt_comment``) on the project, addressed to exactly the chosen
  recipients (``partner_ids``), no one else notified. The message holds the
  update's title, status, date and full description, and a link to the
  project's portal updates page.
- The message's fixed wording (status label, link text) is in the project
  customer's language; the update's own content is sent as written.
- Confirming with no recipients shares the update on the portal only: it
  becomes Shared, and no message is posted.
- Editing a Shared update (title, status, description) sends nothing.
- Sharing an update that is already Shared is refused.
- Sharing again after "Make Internal" is a new share: the wizard opens again,
  prefilled, and confirming posts a new message to the recipients chosen
  then.
- Only users who can write the update can share it or make it internal.
"""
