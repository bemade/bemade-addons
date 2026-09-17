# -*- coding: utf-8 -*-
"""UC-11 — Export back to the family repository: the CSVs stay a diffable snapshot.

Acceptance criteria
-------------------
1. ``homeschool.export`` (a service, callable by cron and by CLI/XML-RPC) writes
   ``tracking/hours.csv``, ``tracking/traces.csv``, ``tracking/indicateurs.csv``,
   ``tracking/indicateurs-definitions.csv``, ``tracking/coverage.csv``,
   ``plan/curriculum/pda-items.csv``, ``items-internes.csv``, ``projets.csv`` with
   **exactly** the current headers, rows ordered by (date, code) so that git diffs
   are minimal.
2. Round-trip: import the repository CSVs → export → byte-identical files (modulo
   trailing newline) on the 2026-09-17 data set; this is the migration gate.
3. ``hours.csv`` rows are derived from blocks with actual minutes: ``block`` column
   from kind + subject (inverse of UC-04 §6), ``activity`` from name, ``notes`` from note.
4. Markdown is exported as-is (no HTML) so ``report.py check`` (Felix spelling,
   provenance) keeps working on the snapshot.
5. The export never writes files outside the configured repository path and never
   runs ``git``; committing stays with the household tooling.
"""
from .common import HomeschoolCase


class TestExport(HomeschoolCase):
    def test_headers_and_ordering(self):
        self.skipTest("pending — TDD")

    def test_roundtrip_byte_identical(self):
        self.skipTest("pending — TDD")

    def test_hours_rows_from_blocks(self):
        self.skipTest("pending — TDD")

    def test_path_confinement(self):
        self.skipTest("pending — TDD")
