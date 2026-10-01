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
  `plan/curriculum/projets.csv`), or the `files=` subset (an unknown name is a
  `UserError`). Portal and plain internal users get `AccessError`.
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

`odoo-dev test homeschool` — use cases UC-01..UC-16, synthetic fixtures only (this
repository is public: never household data).
