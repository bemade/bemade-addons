"""Carried to-dos: « to do on the next visit », noted when a visit is closed.

Acceptance criteria
-------------------
1. The close-out window (``fsm.site.note.wizard``) has « To do on the next
   visit » lines, each with an optional equipment among the closing visit's
   equipment (the visit's and its subtasks'). « Save & close » creates one
   ``fsm.carried.todo`` per non-empty line for the visit's site; « Skip »
   creates none. The site note behaves as before.
2. When the site has an open top-level FSM visit other than the closing one
   planned from today on, the earliest one gets each to-do as a subtask
   « From last visit: <text> » (with the equipment) and the to-do is
   « scheduled ». Open visits planned in the past (never closed) are skipped;
   an unplanned visit counts only if created after the to-do, or once it is
   planned.
3. With no such visit the to-do stays « pending »; the next top-level FSM
   task created (or planned) at the site gets it.
4. Subtask done -> to-do done. Subtask cancelled -> the to-do goes to the
   following visit (pending if none). Subtask deleted -> pending again, then
   attached to the next visit.
5. No duplicates: running the attach again does nothing for a scheduled to-do.
6. The site shows its carried to-dos (count + list); the visit counts the
   carried to-dos still to do on it.
7. Mass / programmatic close never prompts (unchanged from round 1).
"""

from datetime import datetime, timedelta

from odoo.tests import Form, tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class TestFsmCarriedTodo(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("industry_fsm.fsm_project")
        cls.site = cls._generate_partner(name="Carried Site Co")
        cls.other_site = cls._generate_partner(name="Carried Other Co")
        cls.softener = cls._generate_equipment("Water softener", cls.site)
        cls.pump = cls._generate_equipment("Booster pump", cls.site)
        cls.closing = cls._visit("Closing visit", cls.site, days=0)
        cls.closing.equipment_ids = cls.softener
        cls.closing_sub = cls.env["project.task"].create(
            {
                "name": "Inspect pump",
                "project_id": cls.project.id,
                "parent_id": cls.closing.id,
                "equipment_ids": [(6, 0, cls.pump.ids)],
            }
        )

    @classmethod
    def _visit(cls, name, partner, days=None):
        vals = {"name": name, "project_id": cls.project.id, "partner_id": partner.id}
        if days is not None:
            start = datetime(2030, 1, 1, 8) + timedelta(days=days)
            vals.update(planned_date_begin=start, date_deadline=start + timedelta(hours=4))
        return cls.env["project.task"].create(vals)

    def _close_with_todos(self, lines, note=None, skip=False):
        action = self.closing.with_context(fsm_site_note_prompt=True).action_fsm_validate()
        wizard = self.env["fsm.site.note.wizard"].browse(action["res_id"])
        with Form(wizard) as wiz_form:
            if note is not None:
                wiz_form.note = note
            for text, equipment in lines:
                with wiz_form.todo_line_ids.new() as line:
                    line.name = text
                    if equipment:
                        line.equipment_id = equipment
        wizard = wiz_form.record
        if skip:
            wizard.action_skip()
        else:
            wizard.action_save()
        return self.env["fsm.carried.todo"].search(
            [("source_task_id", "=", self.closing.id)], order="id"
        )

    def _carried_subtasks(self, visit):
        return visit.child_ids.filtered(lambda t: t.fsm_carried_todo_ids)

    # -- 1: close-out window ---------------------------------------------------

    def test_wizard_offers_visit_equipment(self):
        action = self.closing.with_context(fsm_site_note_prompt=True).action_fsm_validate()
        wizard = self.env["fsm.site.note.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.task_equipment_ids, self.softener | self.pump)

    def test_save_creates_pending_todos(self):
        todos = self._close_with_todos(
            [("Replace the softener gasket", self.softener), ("Bring a spare fuse", None), ("  ", None)],
            note="Gate code 1234",
        )
        self.assertEqual(len(todos), 2)
        self.assertEqual(todos.mapped("state"), ["pending", "pending"])
        self.assertEqual(todos[0].equipment_id, self.softener)
        self.assertFalse(todos[1].equipment_id)
        self.assertEqual(todos.partner_id, self.site)
        self.assertEqual(self.site.fsm_site_note, "Gate code 1234")
        self.assertTrue(self.closing.fsm_done)
        self.assertEqual(self.site.fsm_carried_todo_count, 2)

    def test_skip_creates_nothing(self):
        todos = self._close_with_todos([("Ignored", None)], skip=True)
        self.assertFalse(todos)
        self.assertTrue(self.closing.fsm_done)

    def test_source_visit_chatter(self):
        self._close_with_todos([("Replace the softener gasket", self.softener)])
        bodies = self.closing.message_ids.mapped("body")
        self.assertTrue(any("Replace the softener gasket" in str(b) for b in bodies))

    # -- 2: attach to an existing next visit -----------------------------------

    def test_existing_next_visit_gets_subtasks(self):
        later = self._visit("Later visit", self.site, days=20)
        sooner = self._visit("Sooner visit", self.site, days=10)
        unplanned = self._visit("Unplanned visit", self.site)
        self._visit("Other site visit", self.other_site, days=1)
        todos = self._close_with_todos(
            [("Replace the softener gasket", self.softener), ("Bring a spare fuse", None)]
        )
        self.assertEqual(todos.mapped("state"), ["scheduled", "scheduled"])
        subtasks = self._carried_subtasks(sooner)
        self.assertEqual(len(subtasks), 2)
        self.assertFalse(self._carried_subtasks(later))
        self.assertFalse(self._carried_subtasks(unplanned))
        gasket = todos[0].target_task_id
        self.assertEqual(gasket.parent_id, sooner)
        self.assertEqual(gasket.name, "From last visit: Replace the softener gasket")
        self.assertEqual(gasket.equipment_ids, self.softener)
        self.assertEqual(gasket.partner_id, self.site)
        self.assertIn(str(self.closing.id), str(gasket.description))
        self.assertEqual(sooner.fsm_carried_todo_count, 2)
        # The closing visit itself (now done) never gets them.
        self.assertFalse(self._carried_subtasks(self.closing))

    def test_past_open_visit_skipped(self):
        """An old visit never closed is not the next visit."""
        stale = self._visit("Stale visit", self.site, days=-3650)
        todos = self._close_with_todos([("Check the drain", None)])
        self.assertEqual(todos.state, "pending")
        self.assertFalse(self._carried_subtasks(stale))

    def test_unplanned_visit_created_before_waits_for_planning(self):
        unplanned = self._visit("Unplanned visit", self.site)
        todos = self._close_with_todos([("Check the drain", None)])
        self.assertEqual(todos.state, "pending")
        start = datetime(2030, 2, 1, 8)
        unplanned.write(
            {"planned_date_begin": start, "date_deadline": start + timedelta(hours=2)}
        )
        self.assertEqual(todos.state, "scheduled")
        self.assertEqual(todos.target_task_id.parent_id, unplanned)

    def test_unplanned_visit_created_after_gets_it(self):
        todos = self._close_with_todos([("Check the drain", None)])
        # Records of one test transaction share a create_date: age the to-do.
        self.env.cr.execute(
            "UPDATE fsm_carried_todo SET create_date = create_date - interval '1 hour'"
            " WHERE id = %s",
            [todos.id],
        )
        todos.invalidate_recordset(["create_date"])
        unplanned = self._visit("New unplanned visit", self.site)
        self.assertEqual(todos.target_task_id.parent_id, unplanned)

    def test_no_duplicates_on_rerun(self):
        sooner = self._visit("Sooner visit", self.site, days=10)
        todos = self._close_with_todos([("Check the drain", None)])
        todos._attach_to_next_visit()
        self.env["fsm.carried.todo"]._attach_pending_for_sites(self.site)
        self.assertEqual(len(self._carried_subtasks(sooner)), 1)

    # -- 3: no next visit yet ----------------------------------------------------

    def test_pending_until_next_visit_created(self):
        todos = self._close_with_todos([("Check the drain", None)])
        self.assertEqual(todos.state, "pending")
        self.assertFalse(todos.target_task_id)
        self._visit("Other site visit", self.other_site, days=1)
        self.assertEqual(todos.state, "pending")
        new_visit = self._visit("Next visit", self.site, days=30)
        self.assertEqual(todos.state, "scheduled")
        self.assertEqual(todos.target_task_id.parent_id, new_visit)
        # A subtask created at the site does not take it a second time.
        self.assertEqual(len(self._carried_subtasks(new_visit)), 1)

    # -- 4: lifecycle --------------------------------------------------------------

    def test_subtask_done_marks_todo_done(self):
        sooner = self._visit("Sooner visit", self.site, days=10)
        todos = self._close_with_todos([("Check the drain", None)])
        todos.target_task_id.write({"state": "1_done"})
        self.assertEqual(todos.state, "done")
        self.assertEqual(sooner.fsm_carried_todo_count, 0)

    def test_visit_done_marks_todo_done(self):
        sooner = self._visit("Sooner visit", self.site, days=10)
        todos = self._close_with_todos([("Check the drain", None)])
        sooner.action_fsm_validate()
        self.assertEqual(todos.state, "done")

    def test_subtask_cancelled_goes_to_following_visit(self):
        sooner = self._visit("Sooner visit", self.site, days=10)
        later = self._visit("Later visit", self.site, days=20)
        todos = self._close_with_todos([("Check the drain", None)])
        first = todos.target_task_id
        first.write({"state": "1_canceled"})
        self.assertEqual(todos.state, "scheduled")
        self.assertEqual(todos.target_task_id.parent_id, later)
        # The cancelled subtask stays on the first visit, unlinked.
        self.assertEqual(first.parent_id, sooner)
        self.assertEqual(first.state, "1_canceled")
        self.assertFalse(self._carried_subtasks(sooner))
        # Cancelled again with no other visit: pending.
        todos.target_task_id.write({"state": "1_canceled"})
        self.assertEqual(todos.state, "pending")
        self.assertFalse(todos.target_task_id)

    def test_subtask_deleted_goes_to_following_visit(self):
        self._visit("Sooner visit", self.site, days=10)
        todos = self._close_with_todos([("Check the drain", None)])
        todos.target_task_id.unlink()
        # Not carried to the same visit again: pending until another visit.
        self.assertEqual(todos.state, "pending")
        self.assertFalse(todos.target_task_id)
        later = self._visit("Later visit", self.site, days=20)
        self.assertEqual(todos.target_task_id.parent_id, later)

    def test_visit_deleted_reattaches(self):
        sooner = self._visit("Sooner visit", self.site, days=10)
        todos = self._close_with_todos([("Check the drain", None)])
        sooner.unlink()
        self.assertEqual(todos.state, "pending")
        later = self._visit("Later visit", self.site, days=20)
        self.assertEqual(todos.target_task_id.parent_id, later)

    def test_cancel_todo_cancels_open_subtask(self):
        sooner = self._visit("Sooner visit", self.site, days=10)
        todos = self._close_with_todos([("Check the drain", None)])
        sub = todos.target_task_id
        todos.action_cancel()
        self.assertEqual(todos.state, "cancelled")
        self.assertEqual(sub.state, "1_canceled")
        self.assertEqual(len(self._carried_subtasks(sooner)), 1)

    # -- 6: site view -------------------------------------------------------------

    def test_site_action_lists_todos(self):
        self._close_with_todos([("Check the drain", None)])
        action = self.site.action_view_fsm_carried_todos()
        self.assertEqual(action["res_model"], "fsm.carried.todo")
        self.assertEqual(
            self.env["fsm.carried.todo"].search(action["domain"]).partner_id, self.site
        )

    # -- 7: no prompt on mass / programmatic close ----------------------------------

    def test_mass_close_no_prompt(self):
        other = self._visit("Other visit", self.site, days=3)
        res = (self.closing | other).with_context(
            fsm_site_note_prompt=True
        ).action_fsm_validate()
        self.assertNotEqual(
            isinstance(res, dict) and res.get("res_model"), "fsm.site.note.wizard"
        )
        self.assertFalse(self.env["fsm.carried.todo"].search([("partner_id", "=", self.site.id)]))
