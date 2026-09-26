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

## Tests

`odoo-dev test homeschool` — use cases UC-01..UC-11, synthetic fixtures only (this
repository is public: never household data).
