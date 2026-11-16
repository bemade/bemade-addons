# -*- coding: utf-8 -*-
{
    "name": "Homeschool Portal",
    "version": "19.0.3.0.0",
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

The app (Bemade portal kit)
---------------------------

Since 19.0.3.0.0 the portal is an app on ``bemade_portal_kit``, with its installable
app (``bemade_portal_kit_pwa``) and its dashboard (``bemade_portal_kit_dashboard``).
While the kit's switch is on (Settings › Portal App), a portal user who is a student's
own login (role ``learner``) or attached to a student as a resource user (role
``tutor``) gets every page above in the app's shell:

* **Today** (``/my/home``) — the kit's dashboard of the learner's day: today's list
  (the learner ticks it from the card), today's blocks, today's reading entry (and,
  with ``homeschool_practice``, today's quests). Each widget links to its page; each
  user may arrange his own.
* **Week**, **Traces** (list, page with its comments, hand-in form), **Reading**
  (books, book page, today's entry) — the pages above, inside the shell; « Practice »
  comes with ``homeschool_practice``.
* A tutor who follows several learners switches between them from the app bar; the
  URLs keep naming the student.
* Roles come from the students (``res.users._pk_extra_roles``), never from groups; a
  user may hold both. Internal users (the parents) keep the stock portal.
* The brand name is the company's; the installed app opens on Today
  (``/my/app.webmanifest`` where it is the database's default app — the homeschool
  instance — else ``/my/app/homeschool.webmanifest``).
* It is the kit app ``homeschool`` (kit 19.0.1.15.0 or later): its roles, menu, pages,
  widgets, layout, home and installable app are registered for that app only, so
  another kit app installed in the same database never mixes with it. An upgrade over
  an older kit stops before anything is written: upgrade the kit in the same run
  (``-u bemade_portal_kit,bemade_portal_kit_pwa,bemade_portal_kit_dashboard,homeschool_portal``).

Switch off (or a user without a homeschool role): every route answers the same pages
on the stock portal layout. Routes, URLs, data and record rules are the same in both.

Language
--------

Source strings are English; ``i18n/fr.po`` carries the French (it serves every French
locale, ``fr_CA`` included). The user's own language drives the rendering.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "homeschool",
        "portal",
        "bemade_portal_kit",
        "bemade_portal_kit_pwa",
        "bemade_portal_kit_dashboard",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/portal_templates.xml",
        "views/portal_menu.xml",
        "views/hs_app.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "homeschool_portal/static/src/scss/portal.scss",
        ],
    },
    "installable": True,
    "application": False,
}
