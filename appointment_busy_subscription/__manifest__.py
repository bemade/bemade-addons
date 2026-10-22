#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Appointments: Busy Subscriptions",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Services/Appointment",
    "summary": "Glue: appointment slots respect busy subscriptions beyond their horizon",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["calendar_busy_subscription", "appointment"],
    "description": """
Appointments: Busy Subscriptions
================================

Glue between ``calendar_busy_subscription`` and ``appointment``; installed
automatically when both are.

Inside a staff user's horizon nothing here is needed: busy blocks are
``calendar.event`` records shown as busy, which the Appointments app already
excludes, both when it offers slots and when it confirms a booking. This
module covers what lies **beyond** the horizon, where the absence of a block
means *not yet read*, not *free*.

* **Unknown counts as busy.** For a staff user with at least one active
  subscription, a slot that ends after their horizon is not offered, and a
  booking for it is refused at confirmation.
* **The horizon follows demand.** When a booking page asks for slots past a
  staff user's horizon -- a visitor browsing further ahead -- and the
  appointment type's booking window (*Schedule not after*) reaches that far,
  the user's horizon is extended to cover it, in whole weeks, and the refresh
  is queued right away. The page request itself never calls an outside
  calendar; the extra weeks appear on the next load, typically within a
  minute.

The horizon is never extended beyond the furthest booking window that asked
for it, so a user who is staff only on short-window appointment types keeps
the default horizon.
""",
    "installable": True,
    "application": False,
    "auto_install": True,
}
