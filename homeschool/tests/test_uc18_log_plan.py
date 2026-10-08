# -*- coding: utf-8 -*-
"""UC-18 — The day's plan lives in Odoo: ``log_plan`` and the printed « Ma liste du jour ».

Acceptance criteria
-------------------
1. ``log_plan(student_id, date, plan)`` writes a whole day in one call: the day's texts
   (``start_time``, ``is_off``, ``off_reason``, ``opening``, ``evening_before``, ``debrief``,
   ``note`` — each written only when its key is present), the planned blocks (kind,
   subject by code or csv key, name, planned minutes, anchor, intention / steps / success /
   fallback, curriculum items by code, material by path, project by code) and the
   deliverables (when, name, detail, bonus), every block and deliverable carrying a stable
   ``plan_key``. Returns ``{"day_id", "block_ids": {key: id}, "deliverable_ids": {key: id},
   "deleted", "log"}``; the blocks' start times are computed as usual.
2. Replay-safe: the same payload twice leaves exactly the same records (same ids, same
   values, nothing new); a replay with a renamed or reordered block (same key) updates it
   in place, the order following ``sequence``.
3. A **closed** block (``status != planned`` or actuals recorded — e.g. after ``log_hours``
   closed it) is never overwritten and never deleted; the ``log`` says it was kept. Same
   for a ticked deliverable (``done``).
4. Planned, actual-less blocks (and unticked deliverables) of the day **absent from the
   payload are deleted**, one ``log`` line each, counted in ``deleted``.
5. A block of the day without ``plan_key`` (the week wizard's, a hand-made one) is matched
   by exact ``(kind, name)`` and gets the key; a replay afterwards matches it by key.
6. Unknown item code, subject, material or project → a ``log`` line, no exception; a
   duplicate key in one payload or a missing key is a ``UserError``.
7. Managers only (``AccessError`` otherwise); what is written for one family changes
   nothing in another.
8. ``is_off: true`` marks the day off and leaves its blocks and deliverables alone.
9. The report « Ma liste du jour » (``homeschool.report_day_list``) renders one card per
   deliverable in ``sequence`` order with its ``when`` label, the bonus card dashed, a tick
   for a done one, and the two footer lines.
"""
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase

D = date(2026, 3, 3)


def plan_payload():
    """A whole invented day, as the prep tool would post it."""
    return {
        "start_time": 9.0,
        "opening": "- what we do today\n- why",
        "evening_before": "- sharpen pencils",
        "debrief": "",
        "note": "a day note",
        "blocks": [
            {"key": "p1", "sequence": 10, "kind": "bloc", "subject": "MATH", "name": "Segment 1 · time measures",
             "duration_planned": 45, "intention": "measure time", "steps": "1. clock\n2. stopwatch",
             "success": "three readings", "fallback": "stop at two",
             "items": ["T-MATH-1", "T-K1"], "materials": ["materiel/fiches/test-fiche.pdf"], "project": "P-PLAN"},
            {"key": "pause1", "sequence": 20, "kind": "pause", "name": "Pause", "duration_planned": 15},
            {"key": "p2", "sequence": 30, "kind": "bloc", "subject": "francais", "name": "Segment 2 · the sentence",
             "duration_planned": 45, "items": ["T-FLE-1"]},
        ],
        "deliverables": [
            {"key": "d1", "sequence": 10, "when": "9 h", "name": "Three time readings on the sheet", "detail": "pencil, dated"},
            {"key": "d2", "sequence": 20, "when": "bonus", "name": "A fourth reading, alone", "detail": "if it comes", "bonus": True},
        ],
    }


class TestLogPlan(HomeschoolCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.manager_user(cls)
        cls.api = cls.env["homeschool.journal.api"].with_user(cls.manager)
        cls.material = cls.env["homeschool.material"].create({
            "name": "Test fiche", "kind": "fiche", "pdf_path": "materiel/fiches/test-fiche.pdf",
            "html_source_path": "materiel/fiches/test-fiche.html",
        })
        cls.project = cls.env["homeschool.project"].create({"code": "P-PLAN", "name": "Plan project"})

    def _day(self):
        return self.Day.search([("student_id", "=", self.student.id), ("date", "=", D)])

    def _blocks(self):
        return self._day().block_ids.sorted(lambda b: (b.sequence, b.id))

    # (a) ---------------------------------------------------------------
    def test_create_from_scratch(self):
        res = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        day = self._day()
        self.assertEqual(res["day_id"], day.id)
        self.assertEqual(res["log"], [])
        self.assertEqual(res["deleted"], 0)
        self.assertEqual(set(res["block_ids"]), {"p1", "pause1", "p2"})
        self.assertEqual(set(res["deliverable_ids"]), {"d1", "d2"})
        self.assertEqual(day.opening, "- what we do today\n- why")
        self.assertEqual(day.evening_before, "- sharpen pencils")
        self.assertFalse(day.debrief)
        self.assertEqual(day.note, "a day note")
        self.assertEqual(day.start_time, 9.0)
        self.assertFalse(day.is_off)
        blocks = self._blocks()
        self.assertEqual(blocks.mapped("plan_key"), ["p1", "pause1", "p2"])
        self.assertEqual(blocks.mapped("status"), ["planned"] * 3)
        p1 = self.Block.browse(res["block_ids"]["p1"])
        self.assertEqual(p1.subject_id, self.math)
        self.assertEqual(p1.item_ids, self.item_math | self.item_internal)
        self.assertEqual(p1.material_ids, self.material)
        self.assertEqual(p1.project_id, self.project)
        self.assertEqual(p1.intention, "measure time")
        self.assertEqual(p1.steps, "1. clock\n2. stopwatch")
        self.assertEqual(p1.success, "three readings")
        self.assertEqual(p1.fallback, "stop at two")
        self.assertEqual(p1.start_time, 9.0)
        p2 = self.Block.browse(res["block_ids"]["p2"])
        self.assertEqual(p2.subject_id, self.fle)  # csv key "francais"
        self.assertEqual(p2.start_time, 10.0)      # 45 + 15 min after 9:00
        self.assertEqual(p2.item_ids, self.item_fle)
        self.assertFalse(p2.actuals_recorded)
        self.assertEqual(day.planned_minutes, 90)
        d2 = self.Deliverable.browse(res["deliverable_ids"]["d2"])
        self.assertTrue(d2.bonus)
        self.assertEqual(d2.when, "bonus")
        self.assertEqual(d2.plan_key, "d2")
        self.assertFalse(d2.done)
        self.assertEqual(day.deliverable_ids.sorted("sequence").mapped("name"),
                         ["Three time readings on the sheet", "A fourth reading, alone"])

    # (b) ---------------------------------------------------------------
    def test_identical_replay_changes_nothing(self):
        first = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        snapshot = self._snapshot()
        second = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        self.assertEqual(first["block_ids"], second["block_ids"])
        self.assertEqual(first["deliverable_ids"], second["deliverable_ids"])
        self.assertEqual(second["deleted"], 0)
        self.assertEqual(second["log"], [])
        self.assertEqual(self._snapshot(), snapshot)
        self.assertEqual(self.Block.search_count([("day_id", "=", first["day_id"])]), 3)
        self.assertEqual(self.Deliverable.search_count([("day_id", "=", first["day_id"])]), 2)

    def _snapshot(self):
        fields_b = ["id", "plan_key", "sequence", "kind", "subject_id", "name", "duration_planned", "anchored",
                    "start_fixed", "intention", "steps", "success", "fallback", "item_ids", "material_ids",
                    "project_id", "status", "minutes_total", "start_time"]
        fields_d = ["id", "plan_key", "sequence", "when", "name", "detail", "bonus", "done"]
        day = self._day()
        return (
            day.read(["opening", "evening_before", "debrief", "note", "start_time", "is_off"]),
            day.block_ids.read(fields_b),
            day.deliverable_ids.read(fields_d),
        )

    # (c) ---------------------------------------------------------------
    def test_replay_renames_and_reorders_in_place(self):
        first = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        payload = plan_payload()
        payload["blocks"][0]["name"] = "Segment 1 · clocks"
        payload["blocks"][0]["sequence"] = 40  # p1 moves last
        payload["blocks"][0]["items"] = ["T-MATH-1"]  # one item dropped
        payload["deliverables"][0]["name"] = "Three readings, dated"
        second = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(first["block_ids"], second["block_ids"])
        self.assertEqual(second["log"], [])
        blocks = self._blocks()
        self.assertEqual(blocks.mapped("plan_key"), ["pause1", "p2", "p1"])
        p1 = self.Block.browse(first["block_ids"]["p1"])
        self.assertEqual(p1.name, "Segment 1 · clocks")
        self.assertEqual(p1.item_ids, self.item_math)
        self.assertEqual(blocks[0].start_time, 9.0)   # pause first
        self.assertEqual(p1.start_time, 10.0)         # 15 + 45 min after 9:00
        self.assertEqual(self.Deliverable.browse(first["deliverable_ids"]["d1"]).name, "Three readings, dated")

    # (d) ---------------------------------------------------------------
    def test_closed_block_is_kept(self):
        first = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        # the evening's hours close p1 (UC-15 fallback: planned MATH block, title replaced)
        hours = self.api.log_hours(self.student.id, "2026-03-03", "bloc-math", "Clocks, for real", "MATH", 50, 45)
        self.assertEqual(hours["block_id"], first["block_ids"]["p1"])
        payload = plan_payload()
        payload["blocks"][0]["name"] = "Segment 1 · renamed after the fact"
        payload["blocks"][2]["name"] = "Segment 2 · renamed too"
        second = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(first["block_ids"], second["block_ids"])
        p1 = self.Block.browse(first["block_ids"]["p1"])
        self.assertEqual(p1.name, "Clocks, for real")
        self.assertEqual(p1.status, "done")
        self.assertEqual(p1.minutes_total, 50)
        self.assertEqual(p1.plan_key, "p1")
        self.assertEqual(second["log"], ["plan 2026-03-03/p1: block %d already closed, kept" % p1.id])
        self.assertEqual(self.Block.browse(first["block_ids"]["p2"]).name, "Segment 2 · renamed too")
        self.assertEqual(self.Block.search_count([("day_id", "=", first["day_id"])]), 3)

    # (e) ---------------------------------------------------------------
    def test_absent_planned_block_is_deleted_closed_is_kept(self):
        first = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        payload = plan_payload()
        payload["blocks"] = [b for b in payload["blocks"] if b["key"] != "p2"]
        second = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(second["deleted"], 1)
        self.assertFalse(self.Block.browse(first["block_ids"]["p2"]).exists())
        self.assertEqual(second["log"], ["plan 2026-03-03/p2: deleted planned block %d «Segment 2 · the sentence»" % first["block_ids"]["p2"]])
        self.assertEqual(set(second["block_ids"]), {"p1", "pause1"})
        # closed: same removal, the block stays
        self.Block.browse(first["block_ids"]["p1"]).write({"status": "partial", "minutes_total": 20, "minutes_adult_present": 20})
        payload["blocks"] = [b for b in payload["blocks"] if b["key"] != "p1"]
        third = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(third["deleted"], 0)
        self.assertTrue(self.Block.browse(first["block_ids"]["p1"]).exists())
        self.assertEqual(third["log"], [])
        self.assertEqual(set(third["block_ids"]), {"pause1"})
        self.assertEqual(self.Block.search_count([("day_id", "=", first["day_id"])]), 2)

    # (f) ---------------------------------------------------------------
    def test_ticked_deliverable_is_kept_unticked_is_deleted(self):
        first = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        d1 = self.Deliverable.browse(first["deliverable_ids"]["d1"])
        d1.done = True
        payload = plan_payload()
        payload["deliverables"] = [{"key": "d3", "sequence": 30, "when": "14 h", "name": "A new one"}]
        second = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertTrue(d1.exists())
        self.assertTrue(d1.done)
        self.assertFalse(self.Deliverable.browse(first["deliverable_ids"]["d2"]).exists())
        self.assertEqual(second["deleted"], 1)
        self.assertEqual(set(second["deliverable_ids"]), {"d3"})
        self.assertIn("plan 2026-03-03/d2: deleted deliverable %d «A fourth reading, alone»" % first["deliverable_ids"]["d2"], second["log"])
        # a ticked deliverable present in the payload with another text is kept as it is
        payload["deliverables"].append({"key": "d1", "sequence": 10, "when": "9 h", "name": "Renamed after the tick"})
        third = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(d1.name, "Three time readings on the sheet")
        self.assertEqual(third["deliverable_ids"]["d1"], d1.id)
        self.assertIn("plan 2026-03-03/d1: deliverable %d already done, kept" % d1.id, third["log"])

    # (g) ---------------------------------------------------------------
    def test_unknown_refs_are_logged_not_raised(self):
        payload = plan_payload()
        payload["blocks"][0]["items"] = ["T-MATH-1", "NOPE-9"]
        payload["blocks"][0]["materials"] = ["materiel/fiches/nope.pdf"]
        payload["blocks"][0]["project"] = "P-NOPE"
        payload["blocks"][2]["subject"] = "klingon"
        res = self.api.log_plan(self.student.id, "2026-03-03", payload)
        p1 = self.Block.browse(res["block_ids"]["p1"])
        self.assertEqual(p1.item_ids, self.item_math)
        self.assertFalse(p1.material_ids)
        self.assertFalse(p1.project_id)
        p2 = self.Block.browse(res["block_ids"]["p2"])
        self.assertFalse(p2.subject_id)
        self.assertEqual(sorted(res["log"]), sorted([
            "plan 2026-03-03/p1: unknown item 'NOPE-9'",
            "plan 2026-03-03/p1: unknown material 'materiel/fiches/nope.pdf'",
            "plan 2026-03-03/p1: unknown project 'P-NOPE'",
            "plan 2026-03-03/p2: unknown subject 'klingon'",
        ]))
        # subject codes as well as csv keys
        payload = plan_payload()
        payload["blocks"][2]["subject"] = "FLE"
        res = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(self.Block.browse(res["block_ids"]["p2"]).subject_id, self.fle)

    def test_duplicate_or_missing_key_is_an_error(self):
        payload = plan_payload()
        payload["blocks"][1]["key"] = "p1"
        with self.assertRaises(UserError):
            self.api.log_plan(self.student.id, "2026-03-03", payload)
        payload = plan_payload()
        payload["deliverables"][1]["key"] = "d1"
        with self.assertRaises(UserError):
            self.api.log_plan(self.student.id, "2026-03-03", payload)
        payload = plan_payload()
        del payload["blocks"][0]["key"]
        with self.assertRaises(UserError):
            self.api.log_plan(self.student.id, "2026-03-03", payload)
        payload = plan_payload()
        payload["blocks"][0]["kind"] = "lunch"
        with self.assertRaises(UserError):
            self.api.log_plan(self.student.id, "2026-03-03", payload)
        with self.assertRaises(UserError):
            self.api.log_plan(self.student.id, "2026-03-03", ["not", "a", "dict"])
        self.assertFalse(self._day())  # nothing half-written

    # (h) ---------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_non_manager_is_refused(self):
        for user in (self.portal_user(), self.internal_user(), self.resource_user(self.student)):
            with self.assertRaises(AccessError):
                self.env["homeschool.journal.api"].with_user(user).log_plan(self.student.id, "2026-03-03", plan_payload())
        other = self.manager_user(self.company_b, login="hs_manager_b")
        with self.assertRaises(AccessError):
            self.env["homeschool.journal.api"].with_user(other).log_plan(self.student.id, "2026-03-03", plan_payload())
        self.assertFalse(self._day())

    # (i) ---------------------------------------------------------------
    def test_second_family_untouched(self):
        self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        other = self.manager_user(self.company_b, login="hs_manager_b")
        api_b = self.env["homeschool.journal.api"].with_user(other)
        payload = plan_payload()
        payload["blocks"][0]["materials"] = []   # the material belongs to family A
        payload["blocks"][0]["project"] = None
        res_b = api_b.log_plan(self.student_b.id, "2026-03-03", payload)
        day_b = self.Day.browse(res_b["day_id"])
        self.assertEqual(day_b.company_id, self.company_b)
        self.assertEqual(day_b.block_ids.mapped("company_id"), day_b.company_id)
        self.assertEqual(len(day_b.block_ids), 3)
        day_a = self._day()
        self.assertEqual(len(day_a.block_ids), 3)
        self.assertEqual(len(day_a.deliverable_ids), 2)
        self.assertNotEqual(set(day_a.block_ids.ids), set(day_b.block_ids.ids))
        # family A's material is not visible to family B's plan
        payload["blocks"][0]["materials"] = ["materiel/fiches/test-fiche.pdf"]
        res_b = api_b.log_plan(self.student_b.id, "2026-03-03", payload)
        self.assertIn("plan 2026-03-03/p1: unknown material 'materiel/fiches/test-fiche.pdf'", res_b["log"])

    # fallback & day off ------------------------------------------------
    def test_keyless_block_matched_by_kind_and_name(self):
        day = self.make_day(D)
        hand = self.make_block(day, "Segment 1 · time measures", 30, 5, kind="bloc", subject_id=self.math.id)
        other = self.make_block(day, "Something else", 30, 6, kind="bloc")
        res = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        self.assertEqual(res["block_ids"]["p1"], hand.id)
        self.assertEqual(hand.plan_key, "p1")
        self.assertEqual(hand.duration_planned, 45)
        self.assertEqual(hand.sequence, 10)
        self.assertFalse(other.exists())   # planned, keyless, absent → deleted
        self.assertEqual(res["deleted"], 1)
        self.assertEqual(len(day.block_ids), 3)
        # a closed keyless block matched by name is kept as it is, but stamped with the key
        p2 = self.Block.browse(res["block_ids"]["p2"])
        p2.write({"plan_key": False, "status": "done", "minutes_total": 40, "minutes_adult_present": 40})
        payload = plan_payload()
        payload["blocks"][2]["duration_planned"] = 60
        res = self.api.log_plan(self.student.id, "2026-03-03", payload)
        self.assertEqual(res["block_ids"]["p2"], p2.id)
        self.assertEqual(p2.plan_key, "p2")
        self.assertEqual(p2.duration_planned, 45)
        self.assertIn("plan 2026-03-03/p2: block %d already closed, kept" % p2.id, res["log"])

    def test_day_off_leaves_blocks_alone(self):
        first = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        res = self.api.log_plan(self.student.id, "2026-03-03", {"is_off": True, "off_reason": "storm", "blocks": [], "deliverables": []})
        day = self._day()
        self.assertTrue(day.is_off)
        self.assertEqual(day.off_reason, "storm")
        self.assertEqual(day.opening, "- what we do today\n- why")   # absent key: untouched
        self.assertEqual(len(day.block_ids), 3)
        self.assertEqual(len(day.deliverable_ids), 2)
        self.assertEqual(res["deleted"], 0)
        self.assertEqual(res["block_ids"], {})
        # absent "blocks" key: blocks untouched; an empty list deletes the planned ones
        res = self.api.log_plan(self.student.id, "2026-03-03", {"is_off": False})
        self.assertEqual(len(self._day().block_ids), 3)
        res = self.api.log_plan(self.student.id, "2026-03-03", {"blocks": []})
        self.assertEqual(len(self._day().block_ids), 0)
        self.assertEqual(res["deleted"], 3)
        self.assertEqual(len(self._day().deliverable_ids), 2)
        self.assertEqual(first["day_id"], res["day_id"])

    def test_template_plan_key_is_copied(self):
        self.env["homeschool.block.template"].create({
            "student_id": self.student.id,   # the student's own grid wins over the shipped default one
            "weekday": "1", "sequence": 10, "kind": "bloc", "subject_id": self.math.id, "name": "Grid math",
            "duration_planned": 45, "plan_key": "p1",
        })
        created, _skipped = self.Day.generate_week(self.student, D)   # 2026-03-03 is a Tuesday
        tuesday = created.filtered(lambda d: d.date == D)
        self.assertEqual(tuesday.block_ids.mapped("plan_key"), ["p1"])
        res = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        self.assertEqual(res["block_ids"]["p1"], tuesday.block_ids.filtered(lambda b: b.plan_key == "p1").id)
        self.assertEqual(len(tuesday.block_ids), 3)

    # views -------------------------------------------------------------
    def test_forms_carry_plan_key(self):
        res = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        with Form(self.Block.browse(res["block_ids"]["p1"])) as f:
            self.assertEqual(f.plan_key, "p1")
            f.plan_key = "p1b"
        with Form(self._day()) as f:
            self.assertEqual(f.block_ids.edit(0).plan_key, "p1b")

    # report ------------------------------------------------------------
    def test_report_day_list_renders(self):
        res = self.api.log_plan(self.student.id, "2026-03-03", plan_payload())
        day = self.Day.browse(res["day_id"])
        self.Deliverable.browse(res["deliverable_ids"]["d1"]).done = True
        Report = self.env["ir.actions.report"].with_user(self.manager)
        action = self.env.ref("homeschool.action_report_day_list")
        self.assertEqual(action.model, "homeschool.day")
        self.assertEqual(action.report_type, "qweb-pdf")
        self.assertEqual(action.paperformat_id.format, "Letter")
        html = Report._render_qweb_html("homeschool.report_day_list", day.ids)[0].decode()
        self.assertIn("Ma liste du jour", html)
        self.assertIn("je coche quand c'est fait, pas avant", html)
        self.assertIn("Three time readings on the sheet", html)
        self.assertIn("A fourth reading, alone", html)
        self.assertIn("pencil, dated", html)
        self.assertLess(html.index("Three time readings"), html.index("A fourth reading"))
        self.assertIn(">9 h<", html)
        self.assertIn(">bonus<", html)
        self.assertEqual(html.count('class="hs-item'), 2)
        self.assertEqual(html.count('class="hs-item hs-bonus"'), 1)          # the dashed card
        self.assertEqual(html.count('class="hs-box hs-box-done"'), 1)        # the tick of the done one
        self.assertEqual(html.count('class="hs-box"'), 1)                    # the empty box of the other
        self.assertIn("le reste du temps est à toi", html)
        self.assertIn("Ce qui n'est pas coché va à demain, sans drame", html)
        self.assertIn(day.display_name, html)
