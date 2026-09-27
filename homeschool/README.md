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
  imported row are kept verbatim.
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

## Tests

`odoo-dev test homeschool` — use cases UC-01..UC-14, synthetic fixtures only (this
repository is public: never household data).
