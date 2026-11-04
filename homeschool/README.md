# homeschool

Records of a home school: curriculum items, days built from movable blocks, material,
traces (portfolio), indicators, journal, reviews, projects. The full description is in
`__manifest__.py`; the family's *documents* stay in its own git repository and this
module cites them by reference. Designed for several students per instance.

## Nightly export ("pull from home")

The CSV snapshot of the records (`tracking/*.csv`, `plan/curriculum/*.csv`) is exported
back to the family repository **from the household's machine**, not from the server:
the instance never runs `git`, holds no repository key and never writes to a clone.

- `homeschool.exporter.export_texts(student_id, files=None, newline="\n")` — RPC-callable
  (`@api.model`; execute it like any model method over XML-RPC / JSON-RPC with a user of
  the **Homeschool / Manager** group — an API key of that user works). Returns
  `{relative_path: csv_text}` for every file of `homeschool.exporter.FILES`
  (`tracking/hours.csv`, `tracking/traces.csv`, `tracking/indicateurs.csv`,
  `tracking/indicateurs-definitions.csv`, `tracking/coverage.csv`,
  `plan/curriculum/pda-items.csv`, `plan/curriculum/items-internes.csv`,
  `plan/curriculum/projets.csv`) **followed by the rendered journal week files**
  (`tracking/journal/<ISO>/<ISO>.md`, one per ISO week holding a day of the student —
  dynamic paths, see « The week file is rendered » below), or the `files=` subset (an
  unknown name is a `UserError`; a week path is accepted). Portal and plain internal
  users get `AccessError`.
- Newline handling is the **server's** job on request: the texts use `\n`; pass
  `newline="\r\n"` to get CRLF texts. The client writes each text verbatim
  (`open(path, "w", encoding="utf-8", newline="")`) — one call per line-ending
  convention if the repository mixes them (the on-disk `export_all` sniffs each
  existing file; a pull client does the same and asks accordingly).
- The client's contract: call the method, write the files into its clone, commit
  (`export: <date>`), push. Nothing more is expected of it; it may run as a nightly job
  on any always-on household machine.

`export_all(student, repo_path)` (on-disk, same texts) and the `ir_cron_export_repository`
cron (inactive by default; reads `homeschool.repo_path`) remain for a deployment where the
repository *is* mounted next to the instance.

### Export conventions (the export is the truth)

The exported files are what the records say, not a copy of what was imported; the family
repository is expected to take them as-is.

- `tracking/hours.csv` — one row per block with recorded minutes, days in date order,
  blocks in their sequence. A **day off** always yields its `journee` marker row first
  (`<date>,journee,<reason>,,0,0,<note>`), then whatever blocks were recorded on it (a
  bonus on a day off is two rows). The `block` key and the `matieres` column of an
  imported row are kept verbatim. The `notes` cell is the block's note followed by its
  own journal, folded in: `<note> · ✓ <what worked> · ✗ <what went badly>` (empty parts
  dropped, newlines flattened) — a block with only a note exports as it always did. The
  importer does not split the cell back: a re-import lands the whole string in `note`
  (the file is the nightly snapshot, never re-imported in practice).
- `tracking/traces.csv` — validated traces only, ordered by (date, code); `matieres` and
  `pda_ids` are `;`-joined.
- `tracking/indicateurs.csv` — **derived**: values sorted by (date, code), whatever order
  the file had before.
- `tracking/coverage.csv` — **derived** from the family's `homeschool.item.coverage` rows,
  one row per PDA item in curriculum order; a hand-kept file is overwritten.
- The importer tolerates `,` as well as `;` in multi-valued columns (`matieres`, `pda_ids`,
  `projets`). An unknown subject key in `hours.csv` / `traces.csv` is reported in the
  import log and the row is imported without that subject — those files never create a
  subject; only the curriculum files (`matiere` / `domaine`) create a placeholder subject
  for a new separator-free key.

## Journal API (the household's journal tool writes the records)

`homeschool.journal.api` is a service model (no table) whose public `@api.model` methods
are the RPC entry points of the family's daily journal (`/journal` → `tools/journal.py`):
the day's hours, notes, traces and indicator values are written **as records**, and the
nightly export above writes the CSV snapshot back into the repository. Every method takes
the `student_id` and works for any student of any family the caller manages; every one
reuses the importer's per-row logic (`_apply_hours_row`, `_apply_trace_row`,
`_apply_indicator_row`, `_journal_vals`), so a line logged through the API and the same
line imported from a CSV are the same records — the round trip is asserted in UC-15.

**Managers only**: portal users, resource users and plain internal users get `AccessError`;
a manager of another family gets `AccessError` on a student he cannot read.

Call shape (Odoo 19 JSON-2, an API key of a *Homeschool / Manager* user as bearer token;
the body is the JSON object of the keyword arguments):

```
POST https://<host>/json/2/homeschool.journal.api/log_hours
Authorization: Bearer <api key>
Content-Type: application/json

{"student_id": 1, "date": "2026-10-05", "block": "bloc-fle", "activity": "Segment 1 French",
 "matieres": "FLE", "minutes_total": 45, "minutes_adult_present": 45, "notes": ""}
```

(`X-Odoo-Database: <db>` when the server hosts several databases; XML-RPC `execute_kw`
on the same model and method works too.)

- `log_hours(student_id, date, block, activity, matieres, minutes_total, minutes_adult_present, notes="", aliases=None)`
  — one `hours.csv` row: the block key gives kind and subject (`aliases` = `{"teacher":
  ["ressource", null]}` for household keys), `journee` with no minutes marks the day off,
  an existing block with the same name and kind is updated; else the first **planned**
  block of the day with the same kind and subject and no actuals yet (lowest sequence)
  is closed — the activity replaces its title, minutes and `done` are written, the plan
  (intention, steps, planned minutes, sequence) is kept, and `log` says
  `closed planned block <id> «<title>»`; else a new block is created. A second call with
  another text on a day with no planned block left creates a new block. Minutes `null` =
  not recorded (blank), `0` is a value. Returns `{"day_id", "block_id", "log"}`
  (`block_id` `null` for a day-off marker; `log` holds the importer's warnings, e.g. an
  unknown subject key, and the planned-block closing above).
- `log_note(student_id, date, text)` — appends to the day's journal entry with the
  week-file classification (`Ce qui a marché : …` → what worked, `Ce qui a mal été : …` →
  what went badly, anything else a `- ` bullet in notes); `text` may hold several `- `
  bullets (a whole day logged late, one entry). Today's entry grows in place; a **past**
  day's entry is never rewritten — the text lands in `corrections` as a dated line
  (`corrected: true` in the result). Returns `{"journal_id", "day_id", "corrected"}`.
- `log_trace(student_id, date, trace_id, title, matieres, pda_ids, diffusion, notes="", attachment=None, artifact_path=None)`
  — one `traces.csv` row (`trace_id` empty → next free `TR-<date>-<letter>` of the family);
  `attachment` = `{"name": "TR-….pdf", "data_b64": "…"}` is stored once as an attachment
  of the trace; `artifact_path` is the CSV column, when the caller keeps a copy in the
  repository. The trace is the parent's: `submitted_by = parent`, `validated = true`.
  Returns `{"trace_id", "code", "log"}` (`trace_id` = record id).
- `log_indicator(student_id, date, code, value, notes="")` — one `indicateurs.csv` row,
  one value per indicator, student and date (updated in place); an unknown code or a
  missing value is a `UserError` — a skipped indicator has no row, never a zero that was
  not said. Returns `{"value_id", "created"}`.
- `status(student_id, date)` → `{"day_id", "hours_rows", "adult_missing", "journal_entry",
  "done"}` with the household rule: `done` when rows exist (the `journee` marker counts),
  no block lacks adult-present minutes and a journal entry exists.

## The day's plan lives in Odoo (« Le plan du jour vit dans Odoo »)

Nothing of a day's plan stays in the family repository: the prep session (or any tool)
writes the whole day into Odoo with **one** call, and the day form prints the paper
« Ma liste du jour » from the deliverables. The week wizard still fills an empty grid from
the weekday templates; `log_plan` fills or completes a grid it created (a template may
carry a `plan_key`, copied to its block; otherwise the block is matched by exact kind
and name and takes the key).

- `log_plan(student_id, date, plan)` — `plan` is one JSON object:

  ```
  {"start_time": 9.0, "is_off": false, "off_reason": "", "opening": "md", "evening_before": "md",
   "debrief": "md", "note": "md",
   "blocks": [{"key": "p1", "sequence": 10, "kind": "bloc", "subject": "MATH", "name": "…",
               "duration_planned": 45, "anchored": false, "start_fixed": 0,
               "intention": "md", "steps": "md", "success": "md", "fallback": "md",
               "items": ["MATH-MES-G.1"], "materials": ["materiel/fiches/x.pdf"], "project": "P-3D"}, …],
   "deliverables": [{"key": "d1", "sequence": 10, "when": "9 h", "name": "…", "detail": "…", "bonus": false}, …]}
  ```

  The day's scalars are written only when their key is present (absent = untouched);
  `is_off: true` marks the day off and leaves its blocks and deliverables alone. `subject`
  is a subject **code** (`MATH`, `PROJETS`) or a CSV key (`francais`); `items` are item
  codes, `materials` repository paths (`pdf_path`, then `html_source_path`), `project` a
  project code — an unknown one goes to `log` and the block is written without it, never
  an exception. `blocks` / `deliverables` absent → that part of the day is untouched;
  `[]` → the planned lines are removed.
- **Replay rules** (the call is idempotent: the same payload twice changes nothing). A
  block is matched by its `plan_key` on that day, else — when it has no key — by exact
  `(kind, name)`, and takes the key. A matched block still `planned` with no actuals is
  **updated in place** (every plan field, `item_ids` / `material_ids` replaced); a
  **closed** block (any other status, or actuals recorded — e.g. after `log_hours` closed
  it) is never overwritten: `log` says `plan <date>/<key>: block <id> already closed, kept`.
  Planned, actual-less blocks of the day **absent from the payload are deleted** (one
  `log` line each, counted in `deleted`); closed ones are never deleted. Deliverables
  follow the same rules with `done` as the closed test (a ticked line is kept as it is).
  A duplicate or missing `key`, a missing `name` or an unknown block `kind` is a
  `UserError` raised before anything is written.
- Returns `{"day_id", "block_ids": {key: id}, "deliverable_ids": {key: id}, "deleted", "log"}`.
- **« Ma liste du jour »**: the day form's **Print the day's list** button (and the Print
  menu) renders `homeschool.report_day_list` on letter paper — one checkbox card per
  deliverable in `sequence` order, the moment (`when`) in the left margin, a bonus line
  with a dashed green border, a tick in the box of a line already `done` (a reprint at
  night shows the state), and the two footer lines (« Quand tout est coché : le reste du
  temps est à toi. » / « Ce qui n'est pas coché va à demain, sans drame — je l'écris ici »).
  The template is written in French on purpose (the household's paper); the model labels
  stay English with their fr_CA terms.

## « Fermer la journée » (close the day)

From the day form's header (**Close the day**) or *Track › Close the day* (today's day of
the company's single student), `homeschool.close.day.wizard` walks the day's
**hour-bearing** blocks — `bloc`, `reading`, `projects`, `ressource`, `bonus`, in
`(sequence, id)` order — one screen at a time: the block's plan (intention, success
criteria, planned minutes) stays visible while the owner types the actual minutes, the
adult-present minutes, the status (done / partial / skipped) and the block's own journal
(what worked, what went badly, note). `opening`, `pause` and `debrief`
(`homeschool.block.NO_HOURS_KINDS`) get no screen: they are set `done` when the day is
finished and never count as pending.

- **Minutes are never pre-filled.** The two inputs are text fields, blank on a planned
  block (an Integer field reads `0` when empty and the client would show « 0 »); a blank
  stays a blank (`actuals_recorded` / `adult_recorded` false), a typed `0` is a value,
  anything but digits is refused. A block already holding minutes shows them.
- **Next** writes the block at once and moves on; **Skip this block** writes `skipped` and
  nothing else; **Previous** writes nothing. Closing the dialog loses only the current
  screen. The three texts are written only when they changed — on a past day they land
  under the block's `corrections` (the freeze), and an unchanged pre-loaded text never
  produces a correction line.
- The last screen is the day's `homeschool.journal` entry (pre-loaded when it exists):
  **Finish** creates it (at least one line is required — an empty entry is a false
  journal) or writes what changed (a past day's under `corrections`), sets `done` on the
  no-hours blocks still planned, and closes.
- A blank adult field keeps the day **Incomplete**: the last screen names those blocks
  (« Blocs sans minutes adulte : … ») and still lets the owner finish. `journal_state`
  now agrees with the journal API's `status`: `done` once every hour-bearing, non-skipped
  block has both its minutes and its adult-present minutes and the entry exists.

## The week file is rendered (`tracking/journal/<ISO>/<ISO>.md`)

`export_journal_weeks(student)` renders the household's week file from the records for
every ISO week holding at least one day with blocks, a journal entry or a day off; the
nightly export (`export_texts`, `export_all`) returns those files after the CSVs, so the
hand-written week file is **replaced** by the rendered one from the first export after
this ships (git keeps the old text). The format, kept importable by `import_journal`:

```
# Semaine N · 2026-W02 (lun. 5 janv. → dim. 11 janv.)

## Revue de la semaine                              ← only when a weekly homeschool.review exists
- **Dose tenue ? :** …  (Plafond visible respecté ?, Semaine notée telle quelle ?,
  Ajustement pour la semaine prochaine, Notes — empty answers omitted)

## Jours

### 2026-01-05
- Blocs : `bloc-math` P1 Math — clocks · 50/45 · done — note · ✓ what worked · ✗ what went badly
- Blocs : `lecture` Reading · 20/– · done              ← one line per recorded block, sequence order:
                                                        hours key, name, total/adult minutes (– = blank), status, hours.csv notes cell
- Ce qui a marché : …                                 ← one bullet per line of the entry's field
- Ce qui a mal été : …
- a free note                                         ← the entry's `notes`, bullets as they are
- Indicateurs : …                                     ← `indicator_notes`
- Corrections :                                       ← the entry's dated corrections, verbatim, indented
  - **2026-01-08** (What worked): …

### 2026-01-07 — pas d'école (Storm)                  ← a day off
```

« Semaine N » counts calendar weeks from the Monday of the week holding the start of the
student's latest `homeschool.year` begun by that week's Sunday; without one, from the week
of the first day of his records. Dates are French (`fr_CA`) whatever the user's language;
the file is French by design and carries no translatable term.

On the way back, `import_journal` reads `Ce qui a marché` / `Ce qui a mal été` /
`Indicateurs :` into the entry's fields, keeps any other bullet in `notes`, ignores the
`Blocs :` lines (`hours.csv` is the blocks' record) and `Corrections :` (append-only on the
live record, never re-imported), accepts the day-off suffix on the heading, and creates no
entry for a section without journal bullets (a day off, blocks only). Render → import into a
fresh family (with `hours.csv`) → render is identical (UC-11); a free-text `notes` line
without a leading `- ` is normalized to a bullet by the first export.

## The block's own journal

Besides its `note`, a block carries `went_well` / `went_badly` (Markdown, rendered on the
« Rendered » page) on its « Block journal » page — the parent's blunt view of that block,
next to the day-level `homeschool.journal`. The three texts share the journal's **past-day
freeze**: from the next day on, a change to any of them is appended under `corrections` as
`- **<today>** (<label>): <text>` and the field itself is never rewritten (`append_note`
behaves the same; `journal_force_edit` in the context bypasses the freeze for imports and
repairs — the hours row written by `log_hours` / `import_hours` is such a case). Minutes and
`status` stay freely editable: closing yesterday late is normal. The export folds the two
texts into the `notes` cell of `hours.csv` (above).

## Several families, one curriculum

Each family is a company; the curriculum items are shared. What a family has done about an
item is its own `homeschool.item.coverage` row (item, company): status computed from that
family's traces and blocks, manual status, note, date, evidence refs. `tracking/coverage.csv`
is therefore per family (`export_coverage(student)` reads the student's family's rows), and the
item's coverage fields, filters and pivot always show the current company.

## Portal data: deliverables, reading log, submitted traces

Three record types exist so that the portal (module `homeschool_portal`) has data to show;
none of them is exported to the family CSV files (the printed « liste du jour » and the paper
carnet remain the household's; `tracking/*.csv` are unchanged).

- **Deliverables** (`homeschool.deliverable`) hang from a day: `when`, `name`, `detail`,
  `bonus`, `done` / `done_at` / `done_by`. The parent fills the day's list (tab
  *Deliverables* on the day form, or *Plan › Deliverables*); the student's portal user may
  flip `done` on his own student's lines and nothing else — any other field in a portal
  write is an `AccessError`. Resource users read.
- **Reading log** (`homeschool.reading.book`, `homeschool.reading.entry`): a book per
  student, one entry per book per day (`word1`, `word2`, `question`, `answer`, and
  `weekly_page` for the Friday page), `written_by` the user who wrote it. The student
  creates and edits his own entries; the parent manages the books (*Track › Reading log*);
  resource users read.
- **Submitted traces**: `trace.submitted_by` is `parent`, `student` or `resource`. A trace
  created by a portal user is forced to `diffusion = internal`, `validated = False`, and
  `submitted_by` is derived from his relation to the student (his own login → `student`,
  attached resource user → `resource`; anyone else is refused). The submitter sees his own
  pending traces; the parent finds them with the *To validate* filter and validates them
  with the button (`action_validate(diffusion=None)`, managers only), which stamps
  `validated_by` / `validated_at`. A non-validated trace can never be institutional.
  Parent-created traces, including the importer's, are validated from the start.

## Security for portal users

A portal user is the student's own login (`student.user_id`) or an outside teacher
attached to him (`student.resource_user_ids`). Through the access lines and record rules
of this module he may:

- **read** his own student record and the students he follows, the shared subjects, and
  the days, blocks, deliverables, reading books and entries of those students, plus the
  **institutional** traces and material of their families;
- **write** his own student's deliverables (`done` only) and reading entries (the student
  only), and **his own submitted traces while they wait for validation** — title, date,
  own words, files. `validated`, `validated_by`, `validated_at`, `diffusion`, the
  parent's `note`, `student_id`, `submitted_by`, `company_id` and `code` are the parent's:
  an `AccessError` from the model guard, whatever the value (the note cannot be set at
  creation either). A validated trace, another user's submission and an institutional
  trace are never writable; nothing is ever unlinked; the curriculum items stay out of
  reach (no read access on `homeschool.item`).
- **attach files** to his own pending trace and **read** the files of the traces and
  material he can read: the module gives portal users a read + create line on
  `ir.attachment` (never write or unlink); Odoo's record-level check then makes a file
  follow the access of the record it is linked to (`res_model` / `res_id`). Every file
  linked to a trace or a material is stamped with that record on link (create and write —
  the backend uploads a file before its record exists), and the 19.0.5.0.0 migration
  stamps the ones already there.
- **comment** a trace he can read in its chatter (`_mail_post_access = "read"`).

The journal, the indicators and the reviews have no portal access at all.

## Language

Source strings are English; `i18n/fr_CA.po` carries the Québec French of the household
(bloc, période, trace, matière, livrable, carnet de lecture, ressource, journée sans
école…). A day's `display_name` shows the weekday in the user's language (« lun. 2 mars »)
while its stored `name` keeps the English weekday for the exports. Terms identical in both
languages (Date, Code, Bloc, Pause…) come back with an empty `msgstr` from `i18n export`:
Odoo drops a translation equal to its source at export time.

## Tests

`odoo-dev test homeschool` — use cases UC-01..UC-19, synthetic fixtures only (this
repository is public: never household data).
