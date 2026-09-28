# -*- coding: utf-8 -*-
{
    "name": "Homeschool Portal",
    "version": "19.0.2.0.0",
    "category": "Education",
    "summary": "Portal pages for the home-schooled student and the outside teacher: "
    "the day and the week, the day's list to tick, traces to read or hand in, the reading log.",
    "description": """
Homeschool Portal
=================

The portal side of ``homeschool``: what the child and the personne-ressource see
and do from their own portal login. Everything here rides on the record rules and
access lines of ``homeschool`` (a portal user reaches his own student, or the
students he is attached to as a resource user); the pages never re-implement them.

Pages (``/my/homeschool``)
--------------------------

* **Home** — one card per student the user may see (his own, or the students he
  follows), with the way to today, the week, the traces and the reading log.
* **Day** — the blocks in sequence with their kind, times, intention, steps,
  success criteria and fallback (Markdown rendered through the sanitizing mixin),
  the material of the day with its files, the « liste du jour » with tick-boxes
  (the student ticks; the resource user reads), previous / next school day, a
  print-friendly layout.
* **Week** — the five-day grid (block, kind, duration) with a link to each day.
* **Traces** — the institutional traces of the student and the user's own traces
  waiting for validation, with their subjects, their files and the student's own
  words; a page per trace with the standard portal chatter (the outside teacher
  comments there); a
  **submission form** (title, files, own words) that creates a trace ``internal``,
  not validated, ``submitted_by`` student or resource — the core guard decides.
* **Reading log** — the student's books; per book the entries (two words, a
  question, its answer, the Friday page) and, for the student only, the form to
  write today's entry.

Access
------

* Reads run as the portal user: the ``homeschool`` record rules decide what is
  listed. The journal, the indicators and the reviews have no portal access at all.
* Writes run as the portal user too (tick a deliverable, write a reading entry,
  create a submitted trace and attach its files): the core access lines, rules
  and model guards apply.
* **Nothing runs as superuser.** The student record, the subjects shown on the
  blocks and the traces, the files of a trace or a material and the chatter post
  all come through the portal access of ``homeschool`` 19.0.5.0.0 (the student
  and subject read lines, the write on one's own pending trace, files stamped with
  their record, ``_mail_post_access = "read"`` on the trace). This module needs
  that core version or later.
* The block kinds and the day headers are the core's own labels (selection
  values, ``day.display_name``), in the user's language.

Language
--------

Source strings are English; ``i18n/fr_CA.po`` carries the French. The user's own
language drives the rendering (there is no website module here).
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["homeschool", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "views/portal_templates.xml",
        "views/portal_menu.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "homeschool_portal/static/src/scss/portal.scss",
        ],
    },
    "installable": True,
    "application": False,
}
