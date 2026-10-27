#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Collective Appointments",
    "version": "19.0.1.0.1",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Services/Appointment",
    "summary": "Appointment types where every staff member attends: a slot needs all of them free",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["appointment"],
    "description": """
Collective Appointments
=======================

With several staff users on a user-based appointment type, Odoo books **one**
of them: it offers a slot when any one is free, and the booked meeting holds
that one person, the customer and the customer's guests. A call that needs two
or more people from your side -- a kickoff, a joint review -- cannot be
booked.

This module adds a third way to staff an appointment type: **everyone
attends**.

Configuration
-------------

On a user-based appointment type, *All staff attend* (``is_collective``)
turns collective mode on, and *Organizer* picks which of the staff users
organizes the booked meetings -- whose name sends the invitations and whose
synced calendar the meeting lands in first. The organizer must be one of the
staff users.

Collective mode leaves no person to choose, so the "choose a staff member"
and automatic assignment options do not apply; it cannot be combined with
resource-based scheduling.

Behaviour
---------

* **Slots**: a slot is offered only when **every** staff user is available
  for it -- working schedule, existing meetings shown as busy, and per-user
  booking limits all apply to each of them.
* **Booking check**: at confirmation the slot is re-verified for every staff
  user, so a meeting booked for one of them in the meantime makes the
  booking fail rather than double-book the others.
* **Meeting**: the booked event has the organizer as ``user_id`` and every
  staff user as an attendee, alongside the customer and their guests; each
  staff user receives the invitation.

Everything that decides whether one user is available is untouched, so other
modules that change it -- Flexible (one-off) slots, busy time imported by
``calendar_busy_subscription`` -- apply to every staff user of a collective
type unchanged.
""",
    "installable": False,  # until implemented (#4935)
    "application": False,
    "auto_install": False,
}
