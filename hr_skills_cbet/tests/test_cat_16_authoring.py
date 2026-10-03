"""UC-CAT-08 — authoring the training content in Odoo (19.0.1.11.0).

AC1: a CBET Trainer edits the *content* of a DRAFT competency — the document
     bodies, the subtitle and the job aids — and nothing else: criteria,
     questions, protocol, policy and the lifecycle stay Manager-only, and a
     published competency is read-only below Manager (write and the
     translation dialog alike). Managers are unchanged.
AC2: every change to a document body leaves a revision (field + language +
     previous html, last 50 per field and language) that can be restored in
     that language only — the other language's document is left intact.
AC3: "Duplicate as variant" copies a job aid (sections and lines) under a new
     variant name on the same competency.
AC4: ``translation_status`` flags a competency whose French documents are the
     English ones (the import's "untranslated" signal); it is searchable.
AC5: before publishing, the manager sees which documents changed since the
     last published version (counts only).

Synthetic wording only — nothing here comes from a real training vault.
"""
from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import tagged
from odoo.tools.misc import mute_logger

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatAuthoring(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.trainer = cls.env["res.users"].create({
            "name": "CBET Trainer",
            "login": "cbet_trainer",
            "email": "cbet_trainer@example.com",
            "group_ids": [Command.link(cls.env.ref("hr_skills_cbet.group_cbet_trainer").id)],
        })
        cls.fr = "fr_CA"
        cls.env["res.lang"]._activate_lang(cls.fr)

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _draft(self, code="XAU-01", **vals):
        comp = self._make_full_competency(code, publish=False, **vals)
        self._make_job_aid(comp)
        return comp

    # ------------------------------------------------------------------
    # AC1 — trainer rights
    # ------------------------------------------------------------------
    def test_trainer_edits_content_of_a_draft(self):
        comp = self._draft()
        as_trainer = comp.with_user(self.trainer)
        as_trainer.write({"procedure_body": "<p>Trainer's version</p>",
                          "subtitle": "Reworded subtitle"})
        self.assertEqual(comp.procedure_body, "<p>Trainer's version</p>")
        self.assertEqual(comp.subtitle, "Reworded subtitle")
        # Job aids are content too: a line, a new section, and removing a line.
        line = comp.job_aid_ids.section_ids[0].line_ids[0]
        line.with_user(self.trainer).write({"text": "goggles — tinted"})
        self.assertEqual(line.text, "goggles — tinted")
        section = self.env["cbet.job.aid.section"].with_user(self.trainer).create({
            "job_aid_id": comp.job_aid_ids.id, "face": "verso", "kind": "phase",
            "name": "3. Put away",
            "line_ids": [Command.create({"text": "Bench covered"})],
        })
        self.assertEqual(section.line_ids.text, "Bench covered")
        comp.job_aid_ids.section_ids[0].line_ids[1].with_user(self.trainer).unlink()
        # Through the competency form as well (the x2many commands run as the trainer).
        as_trainer.write({"job_aid_ids": [Command.update(comp.job_aid_ids.id, {
            "section_ids": [Command.update(section.id, {"name": "3. Tidy up"})]})]})
        self.assertEqual(section.name, "3. Tidy up")

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_trainer_cannot_touch_structure_policy_or_state(self):
        comp = self._draft()
        as_trainer = comp.with_user(self.trainer)
        for vals in (
            {"pass_threshold": 90.0},
            {"protocol_method": "Oral only"},
            {"validity_months": 6},
            {"name": "Renamed"},
            {"state": "published"},
            {"designated_trainer_ids": [Command.link(self.trainer.id)]},
            {"question_ids": [Command.create({"text": "Why?"})]},
            # content AND structure in one write: refused as a whole
            {"procedure_body": "<p>x</p>", "pass_threshold": 50.0},
        ):
            with self.assertRaises(AccessError, msg=str(vals)):
                as_trainer.write(vals)
        with self.assertRaises(AccessError):
            comp.criterion_ids[0].with_user(self.trainer).write({"text": "Changed"})
        with self.assertRaises(AccessError):
            comp.unit_ids[0].with_user(self.trainer).write({"name": "Changed"})
        self.assertEqual(comp.pass_threshold, 80.0)
        self.assertEqual(comp.state, "draft")
        # Nor create or delete competencies.
        with self.assertRaises(AccessError):
            self.env["cbet.competency"].with_user(self.trainer).create(
                {"code": "XAU-77", "name": "Nope"})
        with self.assertRaises(AccessError):
            as_trainer.unlink()

    @mute_logger("odoo.addons.base.models.ir_model")
    def test_trainer_cannot_edit_a_published_competency(self):
        comp = self._draft()
        self._publish(comp)
        with self.assertRaises(AccessError):
            comp.with_user(self.trainer).write({"procedure_body": "<p>late edit</p>"})
        with self.assertRaises(AccessError):
            comp.with_user(self.trainer).update_field_translations(
                "procedure_body", {self.fr: "<p>édition tardive</p>"})
        aid = comp.job_aid_ids
        with self.assertRaises(AccessError):
            aid.with_user(self.trainer).write({"variant": "late"})
        with self.assertRaises(AccessError):
            aid.section_ids[0].with_user(self.trainer).write({"name": "late"})
        with self.assertRaises(AccessError):
            aid.section_ids[0].line_ids[0].with_user(self.trainer).write({"text": "late"})
        with self.assertRaises(AccessError):
            self.env["cbet.job.aid.line"].with_user(self.trainer).create(
                {"section_id": aid.section_ids[0].id, "text": "late"})
        with self.assertRaises(AccessError):
            aid.section_ids[0].line_ids[0].with_user(self.trainer).unlink()
        with self.assertRaises(AccessError):
            aid.section_ids[0].with_user(self.trainer).update_field_translations(
                "name", {self.fr: "tard"})
        self.assertEqual(comp.procedure_body, self.FULL_FICHE["procedure_body"])
        # Reset to draft is Manager-only too; once reset, the trainer may edit again.
        with self.assertRaises(UserError):
            comp.with_user(self.trainer).action_reset_to_draft()
        comp.with_user(self.manager).action_reset_to_draft()
        comp.with_user(self.trainer).write({"procedure_body": "<p>draft again</p>"})
        self.assertEqual(comp.procedure_body, "<p>draft again</p>")

    def test_trainer_cannot_publish(self):
        comp = self._draft()
        with self.assertRaises(UserError):
            comp.with_user(self.trainer).action_publish()
        with self.assertRaises(UserError):
            comp.with_user(self.trainer).action_open_publish_wizard()
        self.assertEqual(comp.state, "draft")
        self.assertFalse(comp.version_ids)

    def test_manager_is_unchanged(self):
        comp = self._draft()
        as_manager = comp.with_user(self.manager)
        as_manager.write({"pass_threshold": 90.0, "procedure_body": "<p>m</p>",
                          "protocol_method": "Bench"})
        self._publish(comp)
        # A manager may still hot-fix a published competency (as before).
        as_manager.write({"procedure_body": "<p>hotfix</p>", "validity_months": 12})
        self.assertEqual(comp.procedure_body, "<p>hotfix</p>")
        self.assertEqual(comp.validity_months, 12)
        comp.job_aid_ids.section_ids[0].line_ids[0].with_user(self.manager).write(
            {"text": "manager edit"})

    def test_form_exposes_content_only_to_the_trainer(self):
        comp = self._draft()
        with Form(comp.with_user(self.trainer)) as form:
            self.assertTrue(form.can_edit_content)
            self.assertFalse(form.can_edit_structure)
            form.procedure_body = "<p>Through the form</p>"
            with self.assertRaises(AssertionError):
                form.pass_threshold = 10.0
            with self.assertRaises(AssertionError):
                form.protocol_method = "x"
        self.assertEqual(comp.procedure_body, "<p>Through the form</p>")
        self._publish(comp)
        with Form(comp.with_user(self.trainer)) as form:
            self.assertFalse(form.can_edit_content)
            with self.assertRaises(AssertionError):
                form.procedure_body = "<p>no</p>"
        with Form(comp.with_user(self.manager)) as form:
            self.assertTrue(form.can_edit_content)
            self.assertTrue(form.can_edit_structure)
            form.pass_threshold = 85.0
        self.assertEqual(comp.pass_threshold, 85.0)

    def test_preview_buttons_call_the_document_reports(self):
        comp = self._draft()
        as_trainer = comp.with_user(self.trainer)
        for action, xmlid in (
            ("action_preview_fiche", "hr_skills_cbet.action_report_cbet_fiche"),
            ("action_preview_procedure", "hr_skills_cbet.action_report_cbet_procedure"),
            ("action_preview_demo_notes", "hr_skills_cbet.action_report_cbet_demo_notes"),
        ):
            result = getattr(as_trainer, action)()
            self.assertEqual(result["type"], "ir.actions.report")
            self.assertEqual(result["report_name"], self.env.ref(xmlid).report_name)
            self.assertEqual(result["context"]["active_ids"], comp.ids)
        result = comp.job_aid_ids.with_user(self.trainer).action_preview_pdf()
        self.assertEqual(result["report_name"],
                         self.env.ref("hr_skills_cbet.action_report_cbet_job_aid").report_name)

    # ------------------------------------------------------------------
    # AC2 — revisions
    # ------------------------------------------------------------------
    def _revisions(self, comp, field, lang=None):
        domain = [("competency_id", "=", comp.id), ("section_id", "=", False),
                  ("field_name", "=", field)]
        if lang:
            domain.append(("lang", "=", lang))
        return self.env["cbet.content.revision"].search(domain)

    def test_revisions_are_recorded_per_field_and_language(self):
        comp = self._make_competency("XAU-10")
        en = comp.with_context(lang="en_US").with_user(self.manager)
        fr = comp.with_context(lang=self.fr).with_user(self.trainer)
        en.write({"procedure_body": "<p>en v1</p>"})      # from empty: nothing to restore
        en.write({"procedure_body": "<p>en v2</p>"})
        en.write({"procedure_body": "<p>en v2</p>"})      # unchanged: no revision
        en.write({"procedure_body": "<p>en v3</p>", "knowledge_body": "<p>k1</p>"})
        fr.write({"procedure_body": "<p>fr v1</p>"})
        fr.write({"procedure_body": "<p>fr v2</p>"})
        self.assertEqual(len(self._revisions(comp, "procedure_body", "en_US")), 2)
        self.assertEqual(len(self._revisions(comp, "procedure_body", self.fr)), 1)
        self.assertFalse(self._revisions(comp, "knowledge_body"))
        latest = self._revisions(comp, "procedure_body", "en_US")[0]   # newest first
        self.assertEqual(latest.previous_html, "<p>en v2</p>")
        self.assertEqual(latest.user_id, self.manager)
        self.assertEqual(self._revisions(comp, "procedure_body", self.fr).user_id, self.trainer)
        self.assertEqual(self._revisions(comp, "procedure_body", self.fr).previous_html,
                         "<p>fr v1</p>")
        self.assertIn(latest, comp.revision_ids)

    def test_restore_writes_back_that_language_only(self):
        comp = self._make_competency("XAU-11")
        en = comp.with_context(lang="en_US")
        fr = comp.with_context(lang=self.fr)
        en.write({"procedure_body": "<p>en v1</p>"})
        fr.write({"procedure_body": "<p>fr v1</p>"})
        en.write({"procedure_body": "<p>en v2</p>"})
        fr.write({"procedure_body": "<p>fr v2</p>"})
        en.write({"procedure_body": "<p>en v3</p>"})
        rev_en_v1 = self._revisions(comp, "procedure_body", "en_US").filtered(
            lambda r: r.previous_html == "<p>en v1</p>")
        self.assertEqual(len(rev_en_v1), 1)
        rev_en_v1.with_user(self.manager).action_restore()
        comp.invalidate_recordset()
        self.assertEqual(en.procedure_body, "<p>en v1</p>")
        self.assertEqual(fr.procedure_body, "<p>fr v2</p>", "the French is left intact")
        # The restore itself is a revision (undoable): en v3 is now a previous html.
        self.assertEqual(self._revisions(comp, "procedure_body", "en_US")[0].previous_html,
                         "<p>en v3</p>")
        # Restoring the French from the user's English session still targets fr.
        rev_fr_v1 = self._revisions(comp, "procedure_body", self.fr).filtered(
            lambda r: r.previous_html == "<p>fr v1</p>")
        rev_fr_v1.with_context(lang="en_US").action_restore()
        comp.invalidate_recordset()
        self.assertEqual(fr.procedure_body, "<p>fr v1</p>")
        self.assertEqual(en.procedure_body, "<p>en v1</p>")

    def test_translation_dialog_records_a_revision(self):
        comp = self._make_competency("XAU-12")
        comp.with_context(lang="en_US").write({"procedure_body": "<p>en</p>"})
        comp.update_field_translations("procedure_body", {self.fr: "<p>fr v1</p>"})
        comp.update_field_translations("procedure_body", {self.fr: "<p>fr v2</p>",
                                                          "en_US": "<p>en</p>"})
        revs = self._revisions(comp, "procedure_body", self.fr)
        self.assertEqual(revs.mapped("previous_html"), ["<p>fr v1</p>"])
        self.assertFalse(self._revisions(comp, "procedure_body", "en_US"),
                         "an unchanged language gets no revision")
        self.assertEqual(comp.with_context(lang=self.fr).procedure_body, "<p>fr v2</p>")

    def test_revisions_keep_the_last_fifty(self):
        comp = self._make_competency("XAU-13")
        en = comp.with_context(lang="en_US")
        for i in range(56):
            en.write({"procedure_body": "<p>v%d</p>" % i})
        revs = self._revisions(comp, "procedure_body", "en_US")
        self.assertEqual(len(revs), 50)
        self.assertEqual(revs[0].previous_html, "<p>v54</p>")
        self.assertEqual(revs[-1].previous_html, "<p>v5</p>")

    def test_section_note_revisions(self):
        comp = self._draft("XAU-14")
        section = comp.job_aid_ids.section_ids.filtered("note_html")
        section.with_context(lang="en_US").with_user(self.trainer).write(
            {"note_html": "<p>table v2</p>"})
        rev = section.revision_ids
        self.assertEqual(len(rev), 1)
        self.assertEqual(rev.field_name, "note_html")
        self.assertEqual(rev.competency_id, comp, "section revisions roll up to the competency")
        self.assertIn(rev, comp.revision_ids)
        rev.with_user(self.trainer).action_restore()
        section.invalidate_recordset()
        self.assertIn("kPa", section.with_context(lang="en_US").note_html)

    def test_restore_respects_the_trainer_guard(self):
        comp = self._draft("XAU-15")
        comp.with_context(lang="en_US").write({"procedure_body": "<p>v2</p>"})
        rev = self._revisions(comp, "procedure_body", "en_US")
        self._publish(comp)
        with mute_logger("odoo.addons.base.models.ir_model"), self.assertRaises(AccessError):
            rev.with_user(self.trainer).action_restore()
        rev.with_user(self.manager).action_restore()
        self.assertEqual(comp.procedure_body, self.FULL_FICHE["procedure_body"])

    # ------------------------------------------------------------------
    # AC3 — duplicate as variant
    # ------------------------------------------------------------------
    def test_duplicate_as_variant(self):
        comp = self._draft("XAU-20")
        aid = comp.job_aid_ids
        aid.section_ids[0].update_field_translations("name", {self.fr: "ÉPI"})
        wizard = self.env["cbet.job.aid.variant.wizard"].with_user(self.trainer).create(
            {"job_aid_id": aid.id, "variant": "RO"})
        action = wizard.action_duplicate()
        new = self.env["cbet.job.aid"].browse(action["res_id"])
        self.assertEqual(action["res_model"], "cbet.job.aid")
        self.assertNotEqual(new, aid)
        self.assertEqual(new.competency_id, comp)
        self.assertEqual(new.variant, "RO")
        self.assertEqual(len(new.section_ids), len(aid.section_ids))
        self.assertEqual(new.section_ids.mapped("name"), aid.section_ids.mapped("name"))
        self.assertEqual(new.section_ids.mapped("face"), aid.section_ids.mapped("face"))
        self.assertEqual(new.section_ids.mapped("icon_id"), aid.section_ids.mapped("icon_id"))
        self.assertEqual(new.section_ids.line_ids.mapped("text"),
                         aid.section_ids.line_ids.mapped("text"))
        self.assertEqual(new.section_ids.line_ids.mapped("icon_id"),
                         aid.section_ids.line_ids.mapped("icon_id"))
        self.assertEqual(new.section_ids.filtered("note_html").note_html,
                         aid.section_ids.filtered("note_html").note_html)
        self.assertEqual(new.section_ids[0].with_context(lang=self.fr).name, "ÉPI")
        self.assertFalse(aid.variant, "the original is untouched")
        self.assertEqual(len(comp.job_aid_ids), 2)
        # The same variant twice trips the one-card-per-variant rule.
        with mute_logger("odoo.sql_db"), self.assertRaises(ValidationError):
            self.env["cbet.job.aid.variant.wizard"].create(
                {"job_aid_id": aid.id, "variant": "RO"}).action_duplicate()

    def test_default_variant_and_job_aid_face_lists(self):
        comp = self._draft("XAU-21")
        aid = comp.job_aid_ids
        wizard = self.env["cbet.job.aid.variant.wizard"].with_context(
            active_model="cbet.job.aid", active_id=aid.id).create({"variant": "UF"})
        self.assertEqual(wizard.job_aid_id, aid)
        self.assertEqual(aid.recto_section_ids, aid.section_ids.filtered(lambda s: s.face == "recto"))
        self.assertEqual(aid.verso_section_ids, aid.section_ids.filtered(lambda s: s.face == "verso"))
        self.assertEqual(aid.section_ids[0].line_preview, "safety glasses · safety shoes")

    # ------------------------------------------------------------------
    # AC4 — translation status
    # ------------------------------------------------------------------
    def test_translation_status(self):
        empty = self._make_competency("XAU-30")
        self.assertEqual(empty.translation_status, "none")
        comp = self._make_competency("XAU-31")
        comp.with_context(lang="en_US").write({"procedure_body": "<p>Steps</p>"})
        # No French yet: the fr value falls back on the English → missing.
        self.assertEqual(comp.translation_status, "missing")
        comp.with_context(lang=self.fr).write({"procedure_body": "<p>Étapes</p>"})
        self.assertEqual(comp.translation_status, "done")
        # One body back to identical fr/en → missing again (the importer's signal).
        comp.with_context(lang="en_US").write({"knowledge_body": "<p>Theory</p>"})
        comp.with_context(lang=self.fr).write({"knowledge_body": "<p>Theory</p>"})
        self.assertEqual(comp.translation_status, "missing")
        Competency = self.env["cbet.competency"]
        self.assertIn(comp, Competency.search([("translation_status", "=", "missing")]))
        self.assertNotIn(empty, Competency.search([("translation_status", "=", "missing")]))
        self.assertIn(empty, Competency.search([("translation_status", "=", "none")]))
        comp.with_context(lang=self.fr).write({"knowledge_body": "<p>Théorie</p>"})
        self.assertIn(comp, Competency.search([("translation_status", "!=", "missing")]))
        self.assertEqual(comp.translation_status, "done")

    # ------------------------------------------------------------------
    # AC5 — publish confirmation
    # ------------------------------------------------------------------
    def test_publish_confirmation_lists_changed_documents(self):
        comp = self._draft("XAU-40")
        self.assertIsNone(comp._document_changes(), "no previous version yet")
        wizard_action = comp.with_user(self.manager).action_open_publish_wizard()
        wizard = self.env["cbet.publish.wizard"].with_user(self.manager).create(
            {"competency_id": comp.id})
        self.assertEqual(wizard_action["res_model"], "cbet.publish.wizard")
        self.assertTrue(wizard.first_publication)
        self.assertEqual(wizard.next_version, "1.0")
        wizard.action_confirm()
        self.assertEqual(comp.state, "published")
        self.assertEqual(comp.version, "1.0")

        comp.with_user(self.manager).action_reset_to_draft()
        comp.write({"procedure_body": "<p>Changed procedure</p>",
                    "safety_block": "<ul><li>New rule</li></ul>"})
        comp.job_aid_ids.section_ids[0].line_ids[0].text = "goggles — tinted"
        self.env["cbet.job.aid"].create({"competency_id": comp.id, "variant": "RO"})
        comp.criterion_ids[0].text = "Bench isolated AND tagged"
        changes = {c["label"]: c for c in comp._document_changes()}
        self.assertEqual(changes["Procedure"]["changed"], 1)
        self.assertEqual(changes["Competency sheet"]["changed"], 1)
        self.assertEqual(changes["Demonstration notes"]["changed"], 0)
        self.assertEqual(changes["Job aids"]["changed"], 2)       # 1 edited + 1 new
        self.assertEqual(changes["Job aids"]["total"], 2)
        self.assertEqual(changes["Criteria and questions"]["changed"], 1)
        wizard = self.env["cbet.publish.wizard"].with_user(self.manager).create(
            {"competency_id": comp.id})
        self.assertFalse(wizard.first_publication)
        self.assertEqual(wizard.next_version, "1.1")
        self.assertIn("Procedure", wizard.changes_html)
        self.assertIn("Job aids", wizard.changes_html)
        wizard.action_confirm()
        self.assertEqual(comp.version, "1.1")
        self.assertEqual(len(comp.version_ids), 2)
        # Nothing touched since: every count is zero.
        comp.with_user(self.manager).action_reset_to_draft()
        self.assertEqual(sum(c["changed"] for c in comp._document_changes()), 0)
