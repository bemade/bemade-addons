#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Calendar Busy Subscriptions: CalDAV Sync",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Productivity",
    "summary": "Glue: CalDAV Sync never pushes subscribed busy blocks to the user's server",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["calendar_busy_subscription", "caldav_sync"],
    "description": """
Calendar Busy Subscriptions: CalDAV Sync
========================================

Glue between ``calendar_busy_subscription`` and ``caldav_sync``; installed
automatically when both are.

A busy block is a ``calendar.event`` whose organizer and attendee is the
subscribing user. ``caldav_sync`` pushes such events to that user's CalDAV
calendar -- which would copy every outside calendar's busy time into the
user's synced one, and, when that synced calendar is itself subscribed,
echo it back as a second block.

This module excludes busy blocks from everything ``caldav_sync`` sends to a
server: creation, update and deletion. Nothing else about either module
changes.
""",
    "installable": True,
    "application": False,
    "auto_install": True,
}
