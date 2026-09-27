# -*- coding: utf-8 -*-
{
    "name": "Homeschool",
    "version": "19.0.4.0.0",
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
* **Deliverables** — the paper « liste du jour » as data: each day carries the
  lines the child is expected to hand over (what, when, bonus or not), and the
  child ticks them from the portal — ``done``, stamped with who ticked and when.
* **Reading log** — the « carnet de lecture »: a book per student, one entry per
  book per day (two words, a question and its answer, the Friday page), written
  by the child himself.
* **Material** — the catalogue of home-made fiches and worksheets: the PDF as
  attachment, the path of its HTML source in git, the items it serves.
* **Traces** — dated learning artifacts for the portfolio, with a stable id
  (``TR-2026-01-05-a``), the items they evidence, attachments, a diffusion
  level (``internal`` / ``institutional``) that governs what leaves the house,
  the child's own comment, and the segment or project they came from. A trace
  **submitted from the portal** (by the child or by a personne-ressource) is
  stored internal and *not validated*; the parent validates it, and only a
  validated trace may become institutional.
* **Indicators** — definitions (unit, period, direction, threshold) and dated
  values; weekly and periodic **reviews** with their answers.
* **Journal** — the parent's blunt daily view (what worked, what went badly,
  notes). A separate model on purpose: it never appears in any portal.

Coverage of the curriculum is computed from traces and blocks, per subject
and per item, with the evidence one click away.

Several families on one instance
--------------------------------

* Each family is a **company** (``res.company``). Students, school years, days,
  blocks, traces, reviews, projects, material, block templates, indicators,
  indicator values and journal entries carry a ``company_id``; a manager sees
  the companies he is attached to and nothing else. The curriculum (subjects,
  PDA and internal items, dependencies) is **shared** by every family.
* **Coverage is per family**: what a family has done about a shared item is a
  ``homeschool.item.coverage`` row keyed (item, company) — computed status from
  that family's traces and blocks, manual status, note, date, evidence refs. The
  item's coverage fields, the *evidenced / not started* filters and the coverage
  pivot show the **current company**; the item form lists every family's row for
  a manager of several companies. ``coverage.csv`` is exported per family.
* A student has a **portal user** (his own login) and **resource users**
  (portal users: outside teachers) who see his days and blocks and the
  institutional traces and material of his family.
* Each family has its own repository path (``homeschool.repo_path.<company_id>``,
  falling back to ``homeschool.repo_path``); the nightly export writes each
  student's files under his family's path, with the one-student file layout.
* A new family starts empty: it defines its own weekday templates and indicators
  (the shipped default grid belongs to the main company).

Access
------

* Internal group *Homeschool manager* (the parent) sees and edits everything
  of his own company (or companies).
* Portal users (a ressource, the child) read days, blocks, deliverables, reading
  books and entries, and the institutional traces and material of their students.
  The child ticks his own deliverables (``done`` only), writes his own reading
  entries and submits traces; a ressource submits traces; each sees the traces he
  submitted while they wait for validation. Nothing else: the journal, the
  indicators and the reviews have **no portal access at all**. The portal views
  themselves are served by the companion module ``homeschool_portal``.

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
        "security/homeschool_rules.xml",
        "data/subject_data.xml",
        "data/block_template_data.xml",
        "data/ir_cron_data.xml",
        "views/block_views.xml",
        "views/day_views.xml",
        "views/deliverable_views.xml",
        "views/reading_views.xml",
        "views/item_views.xml",
        "views/misc_views.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}
