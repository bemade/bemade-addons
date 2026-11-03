# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: an update is internal unless someone shares it.

ACCEPTANCE CRITERIA
- A new update is Internal, whether created from the form or by code (e.g. a
  module that posts release notes). Creating one sends nothing: no message
  on the project chatter, no notified partner, exactly as in core Odoo.
- Visibility cannot be switched to Shared by editing the field: the form shows
  it read-only, and only the Share action (see test_update_share) shares, so
  an update can never become client-visible without its recipients being
  chosen.
- Code may create an update already shared by calling the share action with
  explicit recipients; nothing else makes it shared.
- "Make Internal" on a shared update sets it back to Internal: it leaves the
  portal at once (see test_portal_access). The chatter message already posted
  stays, and nothing new is sent.
"""
