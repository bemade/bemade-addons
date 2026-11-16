"""FSM subtasks take the dates of their scheduled parent visit (durpro task 1062).

Acceptance criteria:
  1. A subtask created under a scheduled FSM task (planned_date_begin and
     date_deadline set) gets both dates; a subtask created with its own dates
     keeps them.
  2. A grandchild created under an unscheduled parent whose own parent is
     scheduled takes the dates of that nearest scheduled ancestor.
  3. Attaching an existing dateless task (and its dateless subtasks) to a
     scheduled parent fills its dates; an attached task that already has dates
     keeps them.
  4. Subtasks instantiated from a task template under a scheduled task inherit.
  5. Regression: changing the parent's dates still propagates to all subtasks.
  6. Migration: open dateless FSM subtasks get the nearest scheduled ancestor's
     dates; done / cancelled ones are left alone; the count is logged.
"""

import importlib.util
import os
from datetime import datetime
from unittest.mock import patch

from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest

BEGIN = datetime(2031, 3, 4, 13, 0)
END = datetime(2031, 3, 4, 21, 0)
OTHER_BEGIN = datetime(2031, 5, 6, 12, 0)
OTHER_END = datetime(2031, 5, 6, 16, 0)


def _load_backfill_migration():
    path = os.path.join(
        get_module_path("bemade_fsm"), "migrations", "19.0.0.6.0", "post-migrate.py"
    )
    spec = importlib.util.spec_from_file_location("bemade_fsm_mig_1906", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("-at_install", "post_install")
class TestSubtaskDates(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("industry_fsm.fsm_project")
        cls.customer = cls._generate_partner(name="Dates Customer")

    def _task(self, name, parent=None, **extra):
        vals = {
            "name": name,
            "project_id": self.project.id,
            "partner_id": self.customer.id,
        }
        if parent:
            vals["parent_id"] = parent.id
        vals.update(extra)
        return self.env["project.task"].create(vals)

    def _scheduled_parent(self):
        return self._task(
            "Visit", planned_date_begin=BEGIN, date_deadline=END
        )

    def assertDates(self, task, begin, end):
        self.assertEqual(task.planned_date_begin, begin, task.name)
        self.assertEqual(task.date_deadline, end, task.name)

    # AC 1
    def test_subtask_created_under_scheduled_parent_inherits(self):
        parent = self._scheduled_parent()
        child = self._task("Child", parent=parent, allocated_hours=2.5)
        self.assertDates(child, BEGIN, END)
        # The planned time of the subtask is not replaced by the visit's span.
        self.assertEqual(child.allocated_hours, 2.5)

    def test_subtask_created_with_own_dates_keeps_them(self):
        parent = self._scheduled_parent()
        child = self._task(
            "Child",
            parent=parent,
            planned_date_begin=OTHER_BEGIN,
            date_deadline=OTHER_END,
        )
        self.assertDates(child, OTHER_BEGIN, OTHER_END)

    def test_subtask_under_unscheduled_parent_stays_dateless(self):
        parent = self._task("Unscheduled visit")
        child = self._task("Child", parent=parent)
        self.assertDates(child, False, False)

    # AC 2
    def test_grandchild_inherits_from_nearest_scheduled_ancestor(self):
        grandparent = self._scheduled_parent()
        parent = self._task("Middle", parent=grandparent)
        # The middle task inherited too; clear it to model an unscheduled level.
        parent.write({"planned_date_begin": False, "date_deadline": False})
        self.assertDates(parent, False, False)
        grandchild = self._task("Grandchild", parent=parent)
        self.assertDates(grandchild, BEGIN, END)

    # AC 3
    def test_attach_dateless_task_fills_dates(self):
        parent = self._scheduled_parent()
        loose = self._task("Loose")
        loose_child = self._task("Loose child", parent=loose)
        self.assertDates(loose, False, False)
        loose.parent_id = parent
        self.assertDates(loose, BEGIN, END)
        self.assertDates(loose_child, BEGIN, END)

    def test_attach_dated_task_keeps_dates(self):
        parent = self._scheduled_parent()
        dated = self._task(
            "Dated", planned_date_begin=OTHER_BEGIN, date_deadline=OTHER_END
        )
        dated.parent_id = parent
        self.assertDates(dated, OTHER_BEGIN, OTHER_END)

    def test_attach_dateless_task_keeps_dated_subtask(self):
        parent = self._scheduled_parent()
        loose = self._task("Loose")
        dated_child = self._task(
            "Dated child",
            parent=loose,
            planned_date_begin=OTHER_BEGIN,
            date_deadline=OTHER_END,
        )
        loose.parent_id = parent
        self.assertDates(loose, BEGIN, END)
        self.assertDates(dated_child, OTHER_BEGIN, OTHER_END)

    # AC 4
    def test_template_subtasks_inherit(self):
        parent = self._scheduled_parent()
        template = self._generate_task_template(
            structure=[2, 1], names=["Tpl", "Tpl child", "Tpl grandchild"]
        )
        row = self._task("From template", parent=parent, template_id=template.id)
        descendants = row | row._get_all_subtasks()
        self.assertEqual(len(descendants), 4)
        for task in descendants:
            self.assertDates(task, BEGIN, END)

    # AC 5
    def test_parent_date_change_still_propagates(self):
        parent = self._scheduled_parent()
        child = self._task("Child", parent=parent)
        grandchild = self._task("Grandchild", parent=child)
        parent.write(
            {"planned_date_begin": OTHER_BEGIN, "date_deadline": OTHER_END}
        )
        self.assertDates(child, OTHER_BEGIN, OTHER_END)
        self.assertDates(grandchild, OTHER_BEGIN, OTHER_END)

    # AC 6
    def test_migration_backfills_open_subtasks_only(self):
        parent = self._scheduled_parent()
        middle = self._task("Middle", parent=parent)
        open_child = self._task("Open", parent=middle)
        done_child = self._task("Done", parent=parent)
        cancelled_child = self._task("Cancelled", parent=parent)
        dated_child = self._task(
            "Dated",
            parent=parent,
            planned_date_begin=OTHER_BEGIN,
            date_deadline=OTHER_END,
        )
        self.env.flush_all()
        # Model the pre-upgrade data: subtasks created before this fix.
        self.env.cr.execute(
            """UPDATE project_task SET planned_date_begin = NULL, date_deadline = NULL
                WHERE id IN %s""",
            [(middle.id, open_child.id, done_child.id, cancelled_child.id)],
        )
        self.env.cr.execute(
            "UPDATE project_task SET state = '1_done' WHERE id = %s", [done_child.id]
        )
        self.env.cr.execute(
            "UPDATE project_task SET state = '1_canceled' WHERE id = %s",
            [cancelled_child.id],
        )
        self.env.invalidate_all()

        migration = _load_backfill_migration()
        # Patch the logger rather than assertLogs: the CI log configuration
        # can filter INFO records before they reach a test handler.
        with patch.object(migration._logger, "info") as log_info:
            migration.migrate(self.env.cr, "19.0.0.5.0")
        self.env.invalidate_all()

        self.assertDates(middle, BEGIN, END)
        self.assertDates(open_child, BEGIN, END)
        self.assertDates(done_child, False, False)
        self.assertDates(cancelled_child, False, False)
        self.assertDates(dated_child, OTHER_BEGIN, OTHER_END)
        log_info.assert_called_once()
        message, count = log_info.call_args.args
        self.assertIn("open FSM subtask", message)
        # The two open dateless subtasks of this test, plus any in the test DB.
        self.assertGreaterEqual(count, 2)
