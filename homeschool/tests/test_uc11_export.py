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
   from kind + subject (inverse of UC-04 §6), ``activity`` from name, ``notes`` from note —
   with the block's ``went_well`` (``✓ …``) and ``went_badly`` (``✗ …``) folded in after
   it, ``·``-separated; a block with only a note exports exactly as before.
   A day off always yields its ``journee`` marker row (reason, ``0,0``, note) *before*
   whatever blocks were recorded on it — a day off with a bonus exports two rows.
4. Markdown is exported as-is (no HTML) so ``report.py check`` (name spelling,
   provenance) keeps working on the snapshot.
5. The export never writes files outside the configured repository path and never
   runs ``git``; committing stays with the household tooling.
6. "Pull from home": ``export_texts(student_id, files=None, newline="\\n")`` is
   RPC-callable and returns ``{relative_path: csv_text}`` with **exactly** the text
   ``export_all`` would write for each file, for the given student id; ``files=``
   restricts to a subset (an unknown name is an error, not a silent omission);
   ``newline`` is applied on the server so the client stays dumb. Managers only: a
   portal or plain internal user gets AccessError. Nothing is written on the server.
7. Several families on one instance: each company has its own repository path
   (``homeschool.repo_path.<company_id>``, falling back to the global ``homeschool.repo_path``);
   the nightly export writes each student's files under his company's path and never
   under another company's; the file layout of the one-student case is unchanged.
   Family-owned rows (traces, hours, indicators, projects) of company B never appear in
   company A's files; the shared curriculum files are identical for both.
8. The journal week files are **rendered from the records**: ``export_journal_weeks(student)``
   returns ``{"tracking/journal/<ISO>/<ISO>.md": text}`` for every ISO week holding a day of
   the student (blocks, an entry, or a day off), in the household's French format (a
   « Semaine N » heading, the weekly review when one exists, ``## Jours``, one ``### date``
   section per day with the recorded blocks as ``- Blocs :`` lines, the entry's bullets with
   the import prefixes, dated corrections). ``export_texts`` merges those dynamic paths
   after ``FILES`` (and accepts them in ``files=``); the rendered file is importable by
   ``import_journal`` and a render → import → render round trip is identical.
"""
import os
import tempfile
from datetime import date

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import mute_logger

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

    def test_hours_notes_fold_the_block_journal(self):
        day = self.make_day(date(2026, 3, 3))
        self.make_block(day, "All three", 45, 1, subject_id=self.fle.id, minutes_total=45, minutes_adult_present=45, status="done",
                        note="n", went_well="w\nmore", went_badly="b")
        self.make_block(day, "Note only", 45, 2, subject_id=self.math.id, minutes_total=45, minutes_adult_present=45, status="done", note="just a note")
        self.make_block(day, "Badly only", 20, 3, kind="reading", subject_id=self.fle.id, minutes_total=20, minutes_adult_present=0, went_badly="meh")
        self.make_block(day, "Nothing", 20, 4, kind="pause", minutes_total=20, minutes_adult_present=0)
        out = self.env["homeschool.exporter"].export_hours(self.student).splitlines()
        self.assertEqual(out[1:], [
            "2026-03-03,bloc-fle,All three,FLE,45,45,n · ✓ w more · ✗ b",
            "2026-03-03,bloc-math,Note only,MATH,45,45,just a note",
            "2026-03-03,lecture,Badly only,FLE,20,0,✗ meh",
            "2026-03-03,pause,Nothing,,20,0,",
        ])

    def test_off_day_with_block_exports_marker_and_block(self):
        day = self.make_day(date(2026, 3, 4), is_off=True, off_reason="Storm", note="roads closed")
        self.make_block(day, "Snow fort geometry", 30, 1, kind="bonus", subject_id=self.math.id,
                        minutes_total=30, minutes_adult_present=30, status="done")
        self.make_day(date(2026, 3, 5), is_off=True, off_reason="Holiday")
        out = self.env["homeschool.exporter"].export_hours(self.student).splitlines()
        self.assertEqual(out[1:], [
            "2026-03-04,journee,Storm,,0,0,roads closed",
            "2026-03-04,bonus-math,Snow fort geometry,MATH,30,30,",
            "2026-03-05,journee,Holiday,,0,0,",
        ])

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

    # ------------------------------------------------------------------
    # 6. export_texts — pull from home
    # ------------------------------------------------------------------
    def test_export_texts_equals_export_all(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"].with_user(self.manager_user())
        texts = Exporter.export_texts(self.student.id)
        self.assertTrue(set(texts) >= set(Exporter.FILES), "one text per exported file")
        self.assertEqual({k for k in texts if k not in Exporter.FILES}, {"tracking/journal/2026-W02/2026-W02.md", "tracking/journal/2026-W03/2026-W03.md"},
                         "plus one rendered file per ISO week holding a day")
        with tempfile.TemporaryDirectory() as out:
            Exporter.export_all(self.student, out)
            for rel, text in texts.items():
                with open(os.path.join(out, rel), encoding="utf-8", newline="") as fh:
                    self.assertEqual(text, fh.read(), rel)
        self.assertEqual(texts["tracking/hours.csv"], HOURS_CSV)
        self.assertEqual(texts["tracking/traces.csv"], TRACES_CSV)

    def test_export_texts_files_subset(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"].with_user(self.manager_user())
        texts = Exporter.export_texts(self.student.id, files=["tracking/hours.csv", "plan/curriculum/projets.csv"])
        self.assertEqual(sorted(texts), ["plan/curriculum/projets.csv", "tracking/hours.csv"])
        self.assertEqual(texts["plan/curriculum/projets.csv"], PROJETS_CSV)
        with self.assertRaises(UserError):
            Exporter.export_texts(self.student.id, files=["tracking/nope.csv"])
        with self.assertRaises(UserError):
            Exporter.export_texts(self.student.id + 999999)  # no such student

    def test_export_texts_newline(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"].with_user(self.manager_user())
        lf = Exporter.export_texts(self.student.id, files=["tracking/hours.csv"])["tracking/hours.csv"]
        crlf = Exporter.export_texts(self.student.id, files=["tracking/hours.csv"], newline="\r\n")["tracking/hours.csv"]
        self.assertNotIn("\r", lf)
        self.assertEqual(crlf, lf.replace("\n", "\r\n"))
        self.assertNotIn("\r\r", crlf)
        self.assertEqual(crlf.count("\r\n"), lf.count("\n"))

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_export_texts_access(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"]
        manager = self.manager_user()
        texts = Exporter.with_user(manager).export_texts(self.student.id)
        self.assertEqual(texts["tracking/hours.csv"], HOURS_CSV)
        with self.assertRaises(AccessError):
            Exporter.with_user(self.portal_user()).export_texts(self.student.id)
        with self.assertRaises(AccessError):
            Exporter.with_user(self.internal_user()).export_texts(self.student.id)

    # ------------------------------------------------------------------
    # 7. several families
    # ------------------------------------------------------------------
    def _family_b_data(self):
        """A day with hours, a trace, an indicator with a value and a project for the second family."""
        env = self.env(context=dict(self.env.context, allowed_company_ids=self.company_b.ids))
        day = env["homeschool.day"].create({"student_id": self.student_b.id, "date": date(2026, 2, 2)})
        env["homeschool.block"].create({"day_id": day.id, "name": "Other French", "sequence": 1, "subject_id": self.fle.id,
                                        "minutes_total": 30, "minutes_adult_present": 30, "status": "done"})
        env["homeschool.trace"].create({"name": "Other trace", "student_id": self.student_b.id, "date": date(2026, 2, 2),
                                        "diffusion": "institutional", "subject_ids": [(6, 0, self.fle.ids)]})
        indicator = env["homeschool.indicator"].create({"code": "B-ONLY", "name": "Only in B", "period": "weekly"})
        env["homeschool.indicator.value"].create({"indicator_id": indicator.id, "student_id": self.student_b.id, "date": date(2026, 2, 6), "value": 3})
        env["homeschool.project"].create({"code": "P-B", "name": "B project", "kind": "outing"})

    def test_family_rows_stay_in_their_company(self):
        self._import_all()
        self._family_b_data()
        Exporter = self.env["homeschool.exporter"]
        # company A's files are exactly what they were with one family on the instance
        self.assertEqual(Exporter.export_traces(self.student), TRACES_CSV)
        self.assertEqual(Exporter.export_hours(self.student), HOURS_CSV)
        self.assertEqual(Exporter.export_indicator_values(self.student), INDIC_VALUES_CSV)
        self.assertEqual(Exporter.export_projects(self.student), PROJETS_CSV)
        self.assertNotIn("B-ONLY", Exporter.export_indicator_definitions(self.student))
        # company B's files hold B's rows only
        hours_b = Exporter.export_hours(self.student_b).splitlines()
        self.assertEqual(hours_b[1:], ["2026-02-02,bloc-fle,Other French,FLE,30,30,"])
        traces_b = Exporter.export_traces(self.student_b).splitlines()
        self.assertEqual(len(traces_b), 2)
        self.assertIn("Other trace", traces_b[1])
        self.assertEqual(Exporter.export_indicator_values(self.student_b).splitlines()[1:], ["2026-02-06,B-ONLY,3,"])
        defs_b = Exporter.export_indicator_definitions(self.student_b)
        self.assertIn("B-ONLY", defs_b)
        self.assertNotIn("R1-ADULTE", defs_b)
        self.assertEqual(Exporter.export_projects(self.student_b).splitlines()[1:], ["P-B,B project,sortie,,,"])
        # the curriculum is shared: identical files for both
        for method in ("export_pda_items", "export_internal_items"):
            self.assertEqual(getattr(Exporter, method)(self.student), getattr(Exporter, method)(self.student_b), method)
        # coverage: same items in the same order, but status, evidence and manual notes are each family's own
        coverage_a, coverage_b = Exporter.export_coverage(self.student), Exporter.export_coverage(self.student_b)
        self.assertEqual([r.split(",")[0] for r in coverage_a.splitlines()], [r.split(",")[0] for r in coverage_b.splitlines()])
        self.assertIn("TR-2026-01-05-a", coverage_a)
        self.assertNotIn("TR-2026-01-05", coverage_b, "family A's traces never appear in family B's files")
        self.assertIn("US-C1-1820,planned,TR-2026-01-05-b,2026-01-01,Kingston trip", coverage_a, "A's manual status, A's evidence")
        self.assertTrue(all(r.split(",")[1:] == ["not_started", "", "", ""] for r in coverage_b.splitlines()[1:]),
                        "family B has no evidence and no manual status yet")

    def test_cron_exports_each_company_to_its_own_path(self):
        self._import_all()
        self._family_b_data()
        Exporter = self.env["homeschool.exporter"]
        Param = self.env["ir.config_parameter"].sudo()
        with tempfile.TemporaryDirectory() as out_a, tempfile.TemporaryDirectory() as out_b:
            Param.set_param("homeschool.repo_path", out_a)  # global = the first family's repository
            Param.set_param("homeschool.repo_path.%d" % self.company_b.id, out_b)
            Exporter.cron_export()
            with open(os.path.join(out_a, "tracking", "hours.csv"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), HOURS_CSV, "the one-student layout is byte-identical")
            with open(os.path.join(out_b, "tracking", "hours.csv"), encoding="utf-8") as fh:
                self.assertIn("Other French", fh.read())
            with open(os.path.join(out_a, "tracking", "traces.csv"), encoding="utf-8") as fh:
                self.assertNotIn("Other trace", fh.read())
            self.assertTrue(os.path.isfile(os.path.join(out_b, "plan", "curriculum", "pda-items.csv")))
            # a company without its own path falls back to the global one
            Param.set_param("homeschool.repo_path.%d" % self.company_b.id, False)
            self.assertEqual(Exporter._repo_path(company=self.company_b), os.path.realpath(out_a))
            self.assertEqual(Exporter._repo_path(company=self.company), os.path.realpath(out_a))
            # no path at all: the cron does nothing (and raises nothing)
            Param.set_param("homeschool.repo_path", False)
            Exporter.cron_export()

    def test_importer_stamps_the_student_company(self):
        """import_all for a student of company B creates B records, touching nothing of A."""
        self._import_all()
        n_traces_a = self.Trace.search_count([("company_id", "=", self.company.id)])
        log = self.env["homeschool.importer"].import_all(self.repo, self.student_b, aliases={"teacher": ("ressource", None)})
        self.assertTrue(log)
        traces_b = self.Trace.search([("student_id", "=", self.student_b.id)])
        self.assertEqual(len(traces_b), 2)
        self.assertEqual(traces_b.mapped("company_id"), self.company_b)
        self.assertEqual(self.Trace.search_count([("company_id", "=", self.company.id)]), n_traces_a)
        days_b = self.Day.search([("student_id", "=", self.student_b.id)])
        self.assertEqual(set(days_b.mapped("company_id").ids), {self.company_b.id})
        self.assertEqual(set(days_b.block_ids.mapped("company_id").ids), {self.company_b.id})
        self.assertEqual(set(days_b.journal_ids.mapped("company_id").ids), {self.company_b.id})
        for model in ("homeschool.indicator", "homeschool.project", "homeschool.material"):
            recs_b = self.env[model].search([("company_id", "=", self.company_b.id)])
            self.assertTrue(recs_b, model)
            recs_a = self.env[model].search([("company_id", "=", self.company.id)])
            self.assertEqual(set(recs_a.mapped("code" if model != "homeschool.material" else "name")),
                             set(recs_b.mapped("code" if model != "homeschool.material" else "name")), model)
        # the curriculum was not duplicated
        self.assertEqual(self.Item.search_count([("code", "=", "MATH-MES-G.1")]), 1)
        # and B's export equals the fixture too (its own repository, same content)
        Exporter = self.env["homeschool.exporter"]
        self.assertEqual(Exporter.export_traces(self.student_b), TRACES_CSV)
        self.assertEqual(Exporter.export_hours(self.student_b), HOURS_CSV)
        self.assertEqual(Exporter.export_indicator_values(self.student_b), INDIC_VALUES_CSV)
        self.assertEqual(Exporter.export_coverage(self.student_b), Exporter.export_coverage(self.student),
                         "the same repository imported twice: the same coverage.csv for each family")


    # ------------------------------------------------------------------
    # 8. the rendered journal week file
    # ------------------------------------------------------------------
    def _week_fixture(self, student=None):
        """An invented week 2026-W02 for ``student``: Monday with two recorded blocks and a
        full entry, Wednesday off, a weekly review. Returns the Monday's day."""
        student = student or self.student
        env = self.env(context=dict(self.env.context, allowed_company_ids=student.company_id.ids))
        Day = env["homeschool.day"]
        monday = Day.create({"student_id": student.id, "date": date(2026, 1, 5)})
        env["homeschool.block"].create({"day_id": monday.id, "name": "P1 Math — clocks", "sequence": 1, "subject_id": self.math.id,
                                        "duration_planned": 45, "minutes_total": 50, "minutes_adult_present": 45, "status": "done",
                                        "note": "stopwatch", "went_well": "clicked", "went_badly": "long"})
        env["homeschool.block"].create({"day_id": monday.id, "name": "Reading", "sequence": 2, "kind": "reading", "subject_id": self.fle.id,
                                        "duration_planned": 20, "minutes_total": 20, "status": "done"})
        env["homeschool.block"].create({"day_id": monday.id, "name": "Pause", "sequence": 3, "kind": "pause", "duration_planned": 15})
        env["homeschool.block"].create({"day_id": monday.id, "name": "Planned only", "sequence": 4, "subject_id": self.st.id})
        env["homeschool.journal"].create({"day_id": monday.id, "went_well": "the clocks\nthe reading", "went_badly": "the fight",
                                          "notes": "- a note\n- another", "indicator_notes": "R3-CONFLITS 1"})
        Day.create({"student_id": student.id, "date": date(2026, 1, 7), "is_off": True, "off_reason": "Storm"})
        env["homeschool.review"].create({"student_id": student.id, "kind": "weekly", "date": date(2026, 1, 11),
                                         "answer_dose": "yes", "adjustment": "none\nreally"})
        return monday

    def test_journal_week_render(self):
        monday = self._week_fixture()
        texts = self.env["homeschool.exporter"].export_journal_weeks(self.student)
        self.assertEqual(list(texts), ["tracking/journal/2026-W02/2026-W02.md"], "a week with no day of the student has no file")
        lines = texts["tracking/journal/2026-W02/2026-W02.md"].splitlines()
        # 2025-09-01 (the year's start, a Monday) → 2026-01-05 is the 19th calendar week of the year
        self.assertEqual(lines[0], "# Semaine 19 · 2026-W02 (lun. 5 janv. → dim. 11 janv.)")
        self.assertIn("## Revue de la semaine", lines)
        self.assertIn("- **Dose tenue ? :** yes", lines)
        self.assertIn("- **Ajustement pour la semaine prochaine :** none really", lines)
        self.assertNotIn("- **Plafond visible respecté ? :** ", "\n".join(lines), "empty answers are not rendered")
        self.assertIn("## Jours", lines)
        day_start = lines.index("### 2026-01-05")
        self.assertEqual(lines[day_start + 1:day_start + 10], [
            "- Blocs : `bloc-math` P1 Math — clocks · 50/45 · done — stopwatch · ✓ clicked · ✗ long",
            "- Blocs : `lecture` Reading · 20/– · done",
            "- Ce qui a marché : the clocks",
            "- Ce qui a marché : the reading",
            "- Ce qui a mal été : the fight",
            "- a note",
            "- another",
            "- Indicateurs : R3-CONFLITS 1",
            "",
        ])
        self.assertIn("### 2026-01-07 — pas d'école (Storm)", lines)
        self.assertLess(lines.index("## Revue de la semaine"), lines.index("## Jours"), "the review is in the preamble the importer ignores")
        # a dated correction on the entry (a past day) renders verbatim under « Corrections »
        monday.journal_ids.write({"went_well": "late"})
        today = self.env["homeschool.day"]._fields["date"].to_string(fields.Date.context_today(monday))
        text = self.env["homeschool.exporter"].export_journal_weeks(self.student)["tracking/journal/2026-W02/2026-W02.md"]
        self.assertIn("- Corrections :\n  - **%s** (What worked): late\n" % today, text)
        self.assertNotIn("- Ce qui a marché : late", text, "the frozen field itself is unchanged")

    def test_journal_week_roundtrip_identity(self):
        self._week_fixture()
        Exporter = self.env["homeschool.exporter"]
        Importer = self.env["homeschool.importer"]
        rel = "tracking/journal/2026-W02/2026-W02.md"
        first = Exporter.export_journal_weeks(self.student)[rel]
        with tempfile.TemporaryDirectory() as repo:
            os.makedirs(os.path.join(repo, "tracking", "journal", "2026-W02"))
            with open(os.path.join(repo, "tracking", "hours.csv"), "w", encoding="utf-8") as fh:
                fh.write(Exporter.export_hours(self.student))
            with open(os.path.join(repo, rel), "w", encoding="utf-8") as fh:
                fh.write(first)
            # a fresh family: the hours and the week file, then the same render
            Importer.import_hours(repo, self.student_b)
            log = Importer.import_journal(repo, self.student_b)
        self.assertIn("journal: 1 new entries", log, "the day off and the Blocs lines create no entry")
        entry = self.env["homeschool.journal"].search([("student_id", "=", self.student_b.id)])
        self.assertEqual(len(entry), 1)
        self.assertEqual((entry.went_well, entry.went_badly, entry.notes, entry.indicator_notes),
                         ("the clocks\nthe reading", "the fight", "- a note\n- another", "R3-CONFLITS 1"))
        self.env["homeschool.review"].with_company(self.company_b).create({
            "student_id": self.student_b.id, "kind": "weekly", "date": date(2026, 1, 11), "answer_dose": "yes", "adjustment": "none\nreally"})
        second = Exporter.export_journal_weeks(self.student_b)
        self.assertEqual(second[rel], first)
        self.assertEqual(second[rel].splitlines()[0], "# Semaine 19 · 2026-W02 (lun. 5 janv. → dim. 11 janv.)")

    def test_journal_week_number_without_a_year(self):
        """No school year covering the week: N counts from the first day of the student's records."""
        self._week_fixture(self.student_b)
        self.year_b.active = False
        self.env["homeschool.day"].with_company(self.company_b).create({"student_id": self.student_b.id, "date": date(2025, 12, 17), "is_off": True})
        texts = self.env["homeschool.exporter"].export_journal_weeks(self.student_b)
        self.assertEqual(sorted(texts), ["tracking/journal/2025-W51/2025-W51.md", "tracking/journal/2026-W02/2026-W02.md"])
        self.assertTrue(texts["tracking/journal/2025-W51/2025-W51.md"].startswith("# Semaine 1 · 2025-W51 (lun. 15 déc. → dim. 21 déc.)"))
        self.assertTrue(texts["tracking/journal/2026-W02/2026-W02.md"].startswith("# Semaine 4 · 2026-W02"))

    def test_export_texts_week_files(self):
        self._import_all()
        Exporter = self.env["homeschool.exporter"].with_user(self.manager_user())
        rel = "tracking/journal/2026-W02/2026-W02.md"
        texts = Exporter.export_texts(self.student.id, files=[rel])
        self.assertEqual(list(texts), [rel])
        self.assertTrue(texts[rel].startswith("# Semaine 19 · 2026-W02"))
        self.assertIn("- Ce qui a marché : French went fine.", texts[rel])
        self.assertIn("- Blocs : `bloc-fle` Segment 1 French · 45/45 · done", texts[rel])
        crlf = Exporter.export_texts(self.student.id, files=[rel], newline="\r\n")[rel]
        self.assertEqual(crlf, texts[rel].replace("\n", "\r\n"))
        with self.assertRaises(UserError):
            Exporter.export_texts(self.student.id, files=["tracking/journal/2030-W01/2030-W01.md"])
        with tempfile.TemporaryDirectory() as out:
            written = Exporter.export_all(self.student, out)
            self.assertIn(rel, written)
            with open(os.path.join(out, rel), encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), texts[rel])
