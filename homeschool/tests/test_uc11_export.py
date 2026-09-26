# -*- coding: utf-8 -*-
"""UC-11 — Export back to the family repository: the CSVs stay a diffable snapshot.

Acceptance criteria
-------------------
1. ``homeschool.exporter`` (a service, callable by cron and by CLI/XML-RPC) writes
   ``tracking/hours.csv``, ``tracking/traces.csv``, ``tracking/indicateurs.csv``,
   ``tracking/indicateurs-definitions.csv``, ``tracking/coverage.csv``,
   ``plan/curriculum/pda-items.csv``, ``items-internes.csv``, ``projets.csv`` with
   **exactly** the current headers, rows ordered by (date, code) so that git diffs
   are minimal.
2. Round-trip: import the repository CSVs → export → byte-identical files (modulo
   trailing newline) on the family data set (run locally, skipped when the repository
   path is absent); this is the migration gate. On the synthetic fixture the round trip
   is asserted here.
3. ``hours.csv`` rows are derived from blocks with actual minutes: ``block`` column
   from kind + subject (inverse of UC-04 §6), ``activity`` from name, ``notes`` from note.
4. Markdown is exported as-is (no HTML) so ``report.py check`` (name spelling,
   provenance) keeps working on the snapshot.
5. The export never writes files outside the configured repository path and never
   runs ``git``; committing stays with the household tooling.
"""
import os
import tempfile

from odoo.exceptions import UserError

from .common import HomeschoolCase, HOURS_CSV, TRACES_CSV, INDIC_VALUES_CSV, PDA_ITEMS_CSV, ITEMS_INTERNES_CSV, PROJETS_CSV


class TestExport(HomeschoolCase):
    def _import_all(self):
        return self.env["homeschool.importer"].import_all(self.repo, self.student, aliases={"teacher": ("ressource", None)})

    def test_headers_and_ordering(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"]
        expected = {
            "export_hours": "date,block,activity,matieres,minutes_total,minutes_adult_present,notes",
            "export_traces": "trace_id,date,title,matieres,pda_ids,artifact_path,diffusion,notes",
            "export_indicator_values": "date,id,valeur,notes",
            "export_indicator_definitions": "id,porte,libelle,unite,cadence,sens,seuil,source,notes",
            "export_coverage": "pda_id,status,evidence_refs,date_updated,notes",
            "export_pda_items": PDA_ITEMS_CSV.splitlines()[0],
            "export_internal_items": ITEMS_INTERNES_CSV.splitlines()[0],
            "export_projects": PROJETS_CSV.splitlines()[0],
        }
        for method, header in expected.items():
            out = getattr(Exporter, method)(self.student)
            self.assertEqual(out.splitlines()[0], header, method)
        traces = Exporter.export_traces(self.student).splitlines()[1:]
        self.assertEqual([r.split(",")[0] for r in traces], sorted(r.split(",")[0] for r in traces))

    def test_roundtrip_byte_identical(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"]
        self.assertEqual(Exporter.export_traces(self.student), TRACES_CSV)
        self.assertEqual(Exporter.export_indicator_values(self.student), INDIC_VALUES_CSV)
        self.assertEqual(Exporter.export_projects(self.student), PROJETS_CSV)
        def without_fixture_items(text):
            # the setUpClass items (codes T-*) are not part of the repository snapshot
            return "".join(line + "\n" for line in text.splitlines() if not line.startswith("T-"))
        self.assertEqual(without_fixture_items(Exporter.export_internal_items(self.student)), ITEMS_INTERNES_CSV)
        self.assertEqual(without_fixture_items(Exporter.export_pda_items(self.student)), PDA_ITEMS_CSV)
        # hours: the original 'block' keys and the day-off note round-trip verbatim
        self.assertEqual(Exporter.export_hours(self.student), HOURS_CSV)

    def test_hours_rows_from_blocks(self):
        from datetime import date
        day = self.make_day(date(2026, 3, 2))
        self.make_block(day, "Segment 1 French", 45, 1, subject_id=self.fle.id, minutes_total=45, minutes_adult_present=45, status="done", note="fine\nreally")
        self.make_block(day, "Planned only", 45, 2, subject_id=self.math.id)
        self.make_block(day, "Reading", 20, 3, kind="reading", subject_id=self.fle.id, minutes_total=20)
        out = self.env["homeschool.exporter"].export_hours(self.student).splitlines()
        self.assertEqual(out[1], "2026-03-02,bloc-fle,Segment 1 French,FLE,45,45,fine really")
        self.assertEqual(out[2], "2026-03-02,lecture,Reading,FLE,20,,", "adult minutes blank = not recorded")
        self.assertEqual(len(out), 3, "planned-only blocks are not hours")

    def test_path_confinement(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"]
        with tempfile.TemporaryDirectory() as out:
            written = Exporter.export_all(self.student, out)
            self.assertIn("tracking/hours.csv", written)
            self.assertTrue(os.path.isfile(os.path.join(out, "tracking", "hours.csv")))
            self.assertTrue(os.path.isfile(os.path.join(out, "plan", "curriculum", "pda-items.csv")))
            Exporter.FILES["../escape.csv"] = "export_hours"
            try:
                with self.assertRaises(UserError):
                    Exporter.export_all(self.student, out, files=["../escape.csv"])
            finally:
                del Exporter.FILES["../escape.csv"]
            self.assertFalse(os.path.exists(os.path.join(os.path.dirname(out), "escape.csv")))
        with self.assertRaises(UserError):
            Exporter.export_all(self.student, None)  # no path configured
