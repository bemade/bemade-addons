"""Work order (SVR) numbering and late visits on confirmed orders.

Acceptance criteria:

* An order confirmed with two visits gets two visit tasks numbered
  ``SVR<n>-1`` and ``SVR<n>-2``; the service tasks under each visit carry
  their visit's number.
* An order confirmed with a single visit keeps ``SVR<n>-1``.
* A new visit is placed at the end of the order (its section gets the highest
  sequence), so it never takes over the lines of an existing visit.
* A visit added to a confirmed order gets its visit task as soon as the first
  service line is added under it: the task is numbered after the existing
  visits (``-3`` after ``-1``/``-2``), the new service task is attached under
  it, and the existing visits' tasks and lines are left untouched.
* A service line added later under a visit that already has its task keeps
  its own task (unchanged) but carries that visit's number, not the next one.
* Creating several visits at once puts each label on its own visit's section,
  even when some of them already carry a section.
"""

from odoo.tests import tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class TestVisitNumbering(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.create_default_fsm_visit = True
        cls.product = cls._generate_product(name="Synthetic Service")

    def _so_with_visits(self, labels, lines_per_visit=1):
        so = self._generate_sale_order()
        so.name = "SO90001"
        visits = self.env["bemade_fsm.visit"]
        lines = {}
        for label in labels:
            visit = self._generate_visit(so, label=label)
            visits |= visit
            lines[visit] = self.env["sale.order.line"]
            for _i in range(lines_per_visit):
                lines[visit] |= self._add_line_at_end(so)
        return so, visits, lines

    def _add_line_at_end(self, so):
        """Add a service line at the bottom of the order, the way the web
        client does (sequence given at creation, after every existing line)."""
        return self.env["sale.order.line"].create(
            {
                "order_id": so.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "sequence": max(so.order_line.mapped("sequence"), default=0) + 1,
            }
        )

    def _add_visit_with_line(self, so, label):
        visit = self._generate_visit(so, label=label)
        return visit, self._add_line_at_end(so)

    def test_two_visits_at_confirmation_are_numbered_1_and_2(self):
        so, visits, lines = self._so_with_visits(["Visit A", "Visit B"])
        so.action_confirm()
        visit_a, visit_b = visits
        self.assertEqual(visit_a.task_id.work_order_number, "SVR90001-1")
        self.assertEqual(visit_b.task_id.work_order_number, "SVR90001-2")
        self.assertEqual(lines[visit_a].task_id.parent_id, visit_a.task_id)
        self.assertEqual(lines[visit_b].task_id.parent_id, visit_b.task_id)
        self.assertEqual(lines[visit_a].task_id.work_order_number, "SVR90001-1")
        self.assertEqual(lines[visit_b].task_id.work_order_number, "SVR90001-2")

    def test_single_visit_is_numbered_1(self):
        so, visits, _lines = self._so_with_visits(["Only Visit"])
        so.action_confirm()
        self.assertEqual(visits.task_id.work_order_number, "SVR90001-1")
        self.assertTrue(visits.task_id.name.startswith("SVR90001-1 - "))

    def test_new_visit_section_goes_to_the_end_of_the_order(self):
        so, visits, lines = self._so_with_visits(["Visit A"], lines_per_visit=2)
        # Lines resequenced by the client (handle widget) end up above 10.
        for seq, line in enumerate(so.order_line.sorted("sequence"), start=10):
            line.sequence = seq
        visit_a = visits
        before = visit_a.so_section_id.get_section_line_ids()
        new_visit = self._generate_visit(so, label="Visit B")
        self.assertGreater(
            new_visit.so_section_id.sequence,
            max((so.order_line - new_visit.so_section_id).mapped("sequence")),
        )
        self.assertEqual(visit_a.so_section_id.get_section_line_ids(), before)
        self.assertFalse(new_visit.so_section_id.get_section_line_ids())

    def test_visit_added_after_confirmation_gets_task_on_first_service_line(self):
        so, visits, lines = self._so_with_visits(["Visit A", "Visit B"])
        so.action_confirm()
        visit_a, visit_b = visits
        task_a, task_b = visit_a.task_id, visit_b.task_id
        children_a, children_b = task_a.child_ids, task_b.child_ids
        lines_a = visit_a.so_section_id.get_section_line_ids()

        visit_c = self._generate_visit(so, label="Visit C")
        self.assertFalse(visit_c.task_id)
        line_c = self._add_line_at_end(so)

        self.assertTrue(line_c.task_id, "the new service line must get its task")
        self.assertTrue(visit_c.task_id, "the new visit must get its visit task")
        self.assertEqual(visit_c.task_id.work_order_number, "SVR90001-3")
        self.assertEqual(line_c.task_id.parent_id, visit_c.task_id)
        self.assertEqual(line_c.task_id.work_order_number, "SVR90001-3")
        self.assertTrue(visit_c.task_id.name.startswith("SVR90001-3 - "))
        # Existing visits untouched.
        self.assertEqual(visit_a.task_id, task_a)
        self.assertEqual(visit_b.task_id, task_b)
        self.assertEqual(task_a.child_ids, children_a)
        self.assertEqual(task_b.child_ids, children_b)
        self.assertEqual(task_a.work_order_number, "SVR90001-1")
        self.assertEqual(task_b.work_order_number, "SVR90001-2")
        self.assertEqual(visit_a.so_section_id.get_section_line_ids(), lines_a)

    def test_late_visit_task_created_only_once(self):
        so, visits, _lines = self._so_with_visits(["Visit A"])
        so.action_confirm()
        visit_b, line_1 = self._add_visit_with_line(so, "Visit B")
        visit_task = visit_b.task_id
        self.assertTrue(visit_task)
        self.assertEqual(visit_task.work_order_number, "SVR90001-2")
        visit_tasks = self.env["project.task"].search(
            [("visit_id", "=", visit_b.id)]
        )
        self.assertEqual(visit_tasks, visit_task)
        self.assertEqual(line_1.task_id.parent_id, visit_task)

    def test_late_line_under_existing_visit_takes_that_visit_number(self):
        so, visits, _lines = self._so_with_visits(["Visit A", "Visit B"])
        so.action_confirm()
        visit_a, visit_b = visits
        children_b = visit_b.task_id.child_ids
        # Added at the bottom of the order, i.e. under visit B.
        line = self._add_line_at_end(so)
        self.assertTrue(line.task_id)
        self.assertEqual(line.task_id.work_order_number, "SVR90001-2")
        self.assertEqual(visit_a.task_id.work_order_number, "SVR90001-1")
        self.assertEqual(visit_b.task_id.child_ids, children_b)

    def test_batch_visit_labels_land_on_their_own_visit(self):
        so = self._generate_sale_order()
        existing_section = self.env["sale.order.line"].create(
            {
                "order_id": so.id,
                "display_type": "line_section",
                "name": "Pre-existing section",
            }
        )
        visits = self.env["bemade_fsm.visit"].create(
            [
                {
                    "sale_order_id": so.id,
                    "label": "Pre-existing section",
                    "so_section_id": existing_section.id,
                },
                {"sale_order_id": so.id, "label": "Second label"},
            ]
        )
        self.assertEqual(visits[0].so_section_id, existing_section)
        self.assertEqual(visits[1].so_section_id.name, "Second label")
        self.assertEqual(visits[1].label, "Second label")
