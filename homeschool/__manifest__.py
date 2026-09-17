# -*- coding: utf-8 -*-
{
    "name": "Homeschool",
    "version": "19.0.1.0.0",
    "category": "Education",
    "summary": "Plan, teach and track a home-schooled child: curriculum items, "
    "days built from movable blocks, material, traces (portfolio), indicators, journal.",
    "description": """
Homeschool
==========

The record layer for a family running home education under the Québec DEM
regime (enseignement à la maison), designed so that everything a parent,
a personne-ressource or the child needs is a *link away* rather than a folder
away. Documents with an audit trail (the canonical needs inventory, the projet
d'apprentissage, decision records, clinical sources) stay in the family's git
repository; this module holds the **records** and cites those documents by
reference.

What it models
--------------

* **Student and school year** — the child (a partner), the year with its
  review points (6-week, January, June).
* **Subjects and curriculum items** — the matières and the items of the
  *Progression des apprentissages* (PDA) plus the family's internal items,
  each with a stable external id (``FLE-E-SYN-C-E.2.a.i``, ``K1-ENGAGE``),
  its hierarchy, priority, target year, source reference and dependencies.
* **Projects** — mini-projects and projects that carry curriculum content
  "by the side", with a status (candidate, pilot, active, parked, done) and
  the child's own vote.
* **Blocks and days** — the **block** is the unit of planning: a kind
  (opening, bloc, pause, reading, projects, ressource, debrief, bonus), a
  subject, a planned duration, a sequence within its day, intention, steps,
  success criteria and fallback in Markdown, the curriculum items and
  material it targets, the project it serves, and — filled in at the end of
  the day — the **actual minutes and adult-present minutes** and a status
  (planned, done, partial, skipped, moved). Start times are computed from
  the day's start and the preceding blocks (pauses are blocks too); a block
  may anchor itself to a fixed time (reading at 14:00) and the computation
  resumes from there. Blocks are moved between days and reordered within a
  day by drag and drop (kanban grouped by day, sequence handle, calendar
  week view); the chatter keeps the history of every move. The **day** is
  the light container: date, opening plan, "the evening before" checklist,
  debrief, day note. **Weekday templates** generate a week's blocks from the
  household grid; an unplanned session is a *bonus* block added at journal
  time, with its minutes.
* **Material** — the catalogue of home-made fiches and worksheets: the PDF as
  attachment, the path of its HTML source in git, the items it serves.
* **Traces** — dated learning artifacts for the portfolio, with a stable id
  (``TR-2026-09-09-a``), the items they evidence, attachments, a diffusion
  level (``internal`` / ``institutional``) that governs what leaves the house,
  the child's own comment, and the segment or project they came from.
* **Indicators** — definitions (unit, period, direction, threshold) and dated
  values; weekly and periodic **reviews** with their answers.
* **Journal** — the parent's blunt daily view (what worked, what went badly,
  notes). A separate model on purpose: it never appears in any portal.

Coverage of the curriculum is computed from traces and blocks, per subject
and per item, with the evidence one click away.

Access
------

* Internal group *Homeschool manager* (the parent) sees and edits everything.
* Portal users (a ressource, the child) are served by the companion module
  ``homeschool_portal``; this module ships the record rules that restrict
  traces and material to their diffusion level and gives the journal and the
  indicators **no portal rule at all**; the child's portal shows his day and
  week as blocks, read-only.

Conventions
-----------

* Ids from the family repository are preserved as external ids so the CSV
  exports and the imports stay symmetric.
* Markdown is stored as text and rendered read-only in the form views.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "external_dependencies": {"python": ["markdown"]},
    "data": [
        "security/homeschool_security.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}
