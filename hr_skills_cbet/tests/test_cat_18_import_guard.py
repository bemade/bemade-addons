"""UC-CAT-18 — the import never overwrites a competency edited in Odoo.

Content is loaded once from a markdown archive, then authored in Odoo. A later
re-import (an old archive, say) must not silently replace that work.

AC1: every competency an import creates, updates or finds identical is stamped
     with the fingerprint of its content (``import_fingerprint``) and the time
     (``imported_on``); the fingerprint is stable (same content, same digest,
     whatever the reading language) and publishing does not change it.
AC2: an identical re-import is still a no-op (rows not churned) and re-stamps.
AC3: a competency edited in Odoo since its last import (a body in French or in
     English, a criterion, a job-aid line) is skipped by the import: nothing is
     written, its state is unchanged, the log names it and a warning is logged.
AC4: "Overwrite competencies edited in Odoo" lifts the guard: the content is
     replaced, a published competency goes back to draft, the revision history
     keeps the replaced body.
AC5: a competency created in Odoo (no fingerprint) whose code matches an
     imported one is skipped too.
AC6: the dry run reports the skip per code and counts it.
AC7: the prerequisites of a skipped code are not relinked.
AC8: the 19.0.1.14.0 migration stamps existing competencies with their current
     content, so re-importing the archive they came from changes nothing.
"""
import base64
import importlib.util
import io
import zipfile

from odoo.tests.common import tagged
from odoo.tools.misc import file_path

from .common import CbetCommon
from .test_cat_10_import import EVAL, FICHE, FICHE_EN
from .test_cat_12_procedure import PNG, PROCEDURE
from .test_cat_13_job_aid import JOB_AID

LOGGER = "odoo.addons.hr_skills_cbet.models.cbet_import"
EDIT = "<p>Rédigé dans Odoo après l'import</p>"
EDIT_EN = "<p>Written in Odoo after the import</p>"


@tagged("post_install", "-at_install")
class TestCatImportGuard(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    # ---------------------------------------------------------------- helpers
    def _archive(self, eval_md=EVAL, procedure=PROCEDURE, extra=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("c/a/FICHE_XIM-01.md", FICHE)
            z.writestr("c/a/FICHE_XIM-01_EN.md", FICHE_EN)
            z.writestr("c/a/EVALUATION_XIM-01.md", eval_md)
            z.writestr("c/a/PROCEDURE_XIM-01.md", procedure)
            z.writestr("c/a/images/banc.png", PNG)
            z.writestr("c/a/JOB_AID_XIM-01.md", JOB_AID)
            for name, text in (extra or {}).items():
                z.writestr(name, text)
        return base64.b64encode(buf.getvalue())

    def _run(self, archive, dry=False, overwrite=False):
        wiz = self.env["cbet.import.wizard"].create({
            "import_mode": "archive", "archive_file": archive,
            "archive_filename": "content.zip", "overwrite_edited": overwrite})
        if dry:
            wiz.action_dry_run()
        else:
            wiz.action_import()
        return wiz

    def _comp(self, code="XIM-01"):
        return self.env["cbet.competency"].search([("code", "=", code)])

    def _changed(self):
        return EVAL.replace("Bypass confirmé", "Bypass revu")

    # -------------------------------------------------------------------- AC1
    def test_import_stamps_the_fingerprint(self):
        self._run(self._archive())
        comp = self._comp()
        self.assertTrue(comp.import_fingerprint)
        self.assertTrue(comp.imported_on)
        self.assertEqual(comp.import_fingerprint, comp._content_fingerprint())
        self.assertFalse(comp._edited_since_import())

    def test_fingerprint_is_stable_and_language_independent(self):
        self._run(self._archive())
        comp = self._comp()
        digest = comp._content_fingerprint()
        self.env.invalidate_all()
        self.assertEqual(comp._content_fingerprint(), digest)
        self.assertEqual(comp.with_context(lang="fr_FR")._content_fingerprint(), digest)

    def test_publishing_does_not_count_as_an_edit(self):
        self._run(self._archive())
        comp = self._comp()
        comp.with_user(self.manager).action_publish()
        self.assertFalse(comp._edited_since_import())

    # -------------------------------------------------------------------- AC2
    def test_identical_reimport_is_a_noop_and_restamps(self):
        self._run(self._archive())
        comp = self._comp()
        comp.with_user(self.manager).action_publish()
        crit_ids, digest = comp.criterion_ids.ids, comp.import_fingerprint
        comp.imported_on = "2020-01-01 00:00:00"
        wiz = self._run(self._archive())
        self.assertEqual(wiz.imported_count, 1)
        self.assertNotIn("edited in Odoo", wiz.result_log)
        self.assertEqual(comp.state, "published")
        self.assertEqual(comp.criterion_ids.ids, crit_ids)
        self.assertEqual(comp.import_fingerprint, digest)
        self.assertGreater(str(comp.imported_on), "2020-01-01 00:00:00")

    def test_new_codes_still_import_next_to_a_skipped_one(self):
        self._run(self._archive())
        self._comp().with_context(lang="fr_FR").procedure_body = EDIT
        with self.assertLogs(LOGGER, "WARNING"):
            wiz = self._run(self._archive(eval_md=self._changed(), extra={
                "c/b/FICHE_XIT-01.md": FICHE.replace("XIM", "XIT"),
                "c/b/EVALUATION_XIT-01.md": EVAL,
            }))
        self.assertEqual(wiz.imported_count, 1)
        self.assertTrue(self._comp("XIT-01").import_fingerprint)

    # -------------------------------------------------------------------- AC3
    def test_body_edited_in_french_is_skipped(self):
        self._run(self._archive())
        comp = self._comp()
        comp.with_user(self.manager).action_publish()
        comp.with_context(lang="fr_FR").procedure_body = EDIT
        texts = comp.criterion_ids.mapped("text")
        with self.assertLogs(LOGGER, "WARNING") as logs:
            wiz = self._run(self._archive(eval_md=self._changed()))
        self.assertIn("XIM-01: edited in Odoo since its last import", logs.output[0])
        self.assertEqual(wiz.imported_count, 0)
        self.assertIn("XIM-01: edited in Odoo since its last import — skipped",
                      wiz.result_log)
        self.assertIn("Overwrite competencies edited in Odoo", wiz.result_log)
        self.env.invalidate_all()
        self.assertEqual(comp.with_context(lang="fr_FR").procedure_body, EDIT)
        self.assertEqual(comp.state, "published")
        self.assertEqual(comp.criterion_ids.mapped("text"), texts)
        self.assertTrue(comp._edited_since_import())       # still flagged

    def test_body_edited_in_english_is_skipped_even_with_unchanged_french(self):
        # The French is identical, so the import would only refresh the
        # English — which is exactly what was edited.
        self._run(self._archive())
        comp = self._comp()
        comp.with_context(lang="en_US").procedure_body = EDIT_EN
        french = comp.with_context(lang="fr_FR").procedure_body
        with self.assertLogs(LOGGER, "WARNING"):
            wiz = self._run(self._archive())
        self.assertIn("XIM-01: edited in Odoo", wiz.result_log)
        self.env.invalidate_all()
        self.assertEqual(comp.with_context(lang="en_US").procedure_body, EDIT_EN)
        self.assertEqual(comp.with_context(lang="fr_FR").procedure_body, french)

    def test_edit_outside_what_the_import_writes_is_absorbed(self):
        # An edit the import never touches is not in its way: an identical
        # re-import keeps it and takes the current content as the new baseline.
        self._run(self._archive())
        comp = self._comp()
        comp.pass_threshold = 90.0
        wiz = self._run(self._archive())
        self.assertNotIn("edited in Odoo", wiz.result_log)
        self.assertEqual(comp.pass_threshold, 90.0)
        self.assertFalse(comp._edited_since_import())

    def test_edited_criterion_is_detected(self):
        self._run(self._archive())
        comp = self._comp()
        comp.criterion_ids[:1].with_context(lang="fr_FR").text = "Critère réécrit"
        self.assertTrue(comp._edited_since_import())

    def test_edited_job_aid_line_is_detected(self):
        self._run(self._archive())
        comp = self._comp()
        line = comp.job_aid_ids.section_ids.line_ids[:1]
        self.assertTrue(line)
        line.with_context(lang="en_US").text = "Reworded in Odoo"
        self.assertTrue(comp._edited_since_import())

    # -------------------------------------------------------------------- AC4
    def test_overwrite_edited_replaces_the_content(self):
        self._run(self._archive())
        comp = self._comp()
        comp.with_user(self.manager).action_publish()
        comp.with_context(lang="fr_FR").procedure_body = EDIT
        wiz = self._run(self._archive(eval_md=self._changed()), overwrite=True)
        self.assertEqual(wiz.imported_count, 1)
        self.assertNotIn("edited in Odoo", wiz.result_log)
        self.env.invalidate_all()
        self.assertNotEqual(comp.with_context(lang="fr_FR").procedure_body, EDIT)
        self.assertIn("Bypass revu", comp.with_context(lang="fr_FR").criterion_ids.mapped("text"))
        self.assertEqual(comp.state, "draft")
        revision = self.env["cbet.content.revision"].search([
            ("competency_id", "=", comp.id), ("field_name", "=", "procedure_body"),
            ("lang", "=", "fr_FR")], limit=1)
        self.assertIn("Rédigé dans Odoo", revision.previous_html)
        self.assertFalse(comp._edited_since_import())     # re-stamped

    # -------------------------------------------------------------------- AC5
    def test_competency_created_in_odoo_is_skipped(self):
        comp = self._make_competency("XIM-01", name="Créée à la main")
        self.assertFalse(comp.import_fingerprint)
        with self.assertLogs(LOGGER, "WARNING"):
            wiz = self._run(self._archive())
        self.assertIn("XIM-01: edited in Odoo", wiz.result_log)
        self.assertEqual(comp.name, "Créée à la main")
        self.assertFalse(comp.criterion_ids)

    # -------------------------------------------------------------------- AC6
    def test_dry_run_reports_the_skip(self):
        self._run(self._archive())
        self._comp().with_context(lang="fr_FR").procedure_body = EDIT
        wiz = self._run(self._archive(eval_md=self._changed()), dry=True)
        self.assertIn("skip (edited in Odoo): 1", wiz.result_log)
        self.assertIn("would be left alone (1): XIM-01", wiz.result_log)
        row = wiz.result_log.splitlines()[-1]               # the per-code table
        self.assertTrue(row.endswith("skip (edited in Odoo)"), wiz.result_log)
        # with the box ticked, the same run would update it
        wiz = self._run(self._archive(eval_md=self._changed()), dry=True, overwrite=True)
        self.assertIn("skip (edited in Odoo): 0", wiz.result_log)

    def test_dry_run_reports_an_english_edit_and_changes_nothing(self):
        # French unchanged: only the English refresh is at stake, and the dry
        # run tries it (then rolls it back) to give the import's own decision.
        self._run(self._archive())
        comp = self._comp()
        comp.with_context(lang="en_US").procedure_body = EDIT_EN
        wiz = self._run(self._archive(), dry=True)
        self.assertIn("would be left alone (1): XIM-01", wiz.result_log)
        self.env.invalidate_all()
        self.assertEqual(comp.with_context(lang="en_US").procedure_body, EDIT_EN)
        self.assertTrue(comp._edited_since_import())

    # -------------------------------------------------------------------- AC7
    def test_prerequisites_of_a_skipped_code_are_not_relinked(self):
        # FICHE (XIM-01) requires XIM-02, absent from the first import.
        self._run(self._archive())
        comp = self._comp()
        self.assertFalse(comp.prerequisite_ids)
        comp.with_context(lang="fr_FR").procedure_body = EDIT
        with self.assertLogs(LOGGER, "WARNING"):
            self._run(self._archive(eval_md=self._changed(), extra={
                "c/b/FICHE_XIM-02.md": FICHE.replace("XIM-01", "XIM-02").replace(
                    "`XIM-02` | Autre", "`XIM-09` | Autre"),
                "c/b/EVALUATION_XIM-02.md": EVAL,
            }))
        self.assertTrue(self._comp("XIM-02"))
        self.assertFalse(comp.prerequisite_ids)

    def test_linking_prerequisites_keeps_the_stamp_in_step(self):
        self._run(self._archive(extra={
            "c/b/FICHE_XIM-02.md": FICHE.replace("XIM-01", "XIM-02").replace(
                "`XIM-02` | Autre", "`XIM-09` | Autre"),
            "c/b/EVALUATION_XIM-02.md": EVAL,
        }))
        comp = self._comp()
        self.assertTrue(comp.prerequisite_ids)
        self.assertFalse(comp._edited_since_import())

    # -------------------------------------------------------------------- AC8
    def test_migration_stamps_existing_competencies(self):
        self._run(self._archive())
        comp = self._comp()
        comp.write({"import_fingerprint": False, "imported_on": False})
        self.assertTrue(comp._edited_since_import())
        path = file_path("hr_skills_cbet/migrations/19.0.1.14.0/post-migrate.py")
        spec = importlib.util.spec_from_file_location("cbet_post_migrate_1_14", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.1.13.0")
        self.env.invalidate_all()
        self.assertTrue(comp.imported_on)
        self.assertFalse(comp._edited_since_import())
        wiz = self._run(self._archive())
        self.assertNotIn("edited in Odoo", wiz.result_log)
