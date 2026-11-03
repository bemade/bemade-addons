# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: the client reads a project's updates on the portal (HttpCase).

ACCEPTANCE CRITERIA
- ``/my/projects/<id>/updates``, logged in as a portal user who can open the
  project, renders the project's updates that user can read (shared with
  them, see test_portal_access) newest first, each with title, date, status
  and description, and no other update. With none, it says there are no
  updates yet.
- A portal user who cannot open the project, or an anonymous visitor, is
  sent away (redirect to ``/my`` or login) and sees no update content.
- It is NOT redirected to Project Sharing for collaborators: the link in the
  share email lands on the updates page for every recipient.
- The classic portal project page (``/my/projects/<id>``, for followers
  without Project Sharing) shows an "Updates" button at the top that leads
  to the page.
"""
