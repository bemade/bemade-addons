"""Use case: a service tech reads a task's equipment at a glance.

Acceptance criteria
-------------------
- A task with no linked equipment has an empty ``equipment_summary``.
- A task with one equipment shows « CODE — Name · location notes » on one line.
- Each linked equipment gets its own line, in the task's equipment order.
- When an equipment has no location notes, the « · notes » part is omitted.
- When an equipment has no code, the « CODE — » part is omitted.
- Location notes are flattened to a single line and trimmed to
  ``LOCATION_NOTES_MAX`` characters, ending with « … » when cut.
- The summary follows edits made to the equipment.
"""

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.fsm_equipment.models.task import LOCATION_NOTES_MAX


@tagged("post_install", "-at_install")
class TestTaskEquipmentSummary(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Example Client Inc."})
        cls.project = cls.env["project.project"].create(
            {
                "name": "Field Service Test",
                "is_fsm": True,
                "company_id": cls.env.company.id,
            }
        )
        Equipment = cls.env["fsm.equipment"]
        cls.pump = Equipment.create(
            {
                "name": "Circulation pump",
                "code": "EQ-001",
                "partner_id": cls.partner.id,
                "location_notes": "Basement, room B12",
            }
        )
        cls.boiler = Equipment.create(
            {
                "name": "Boiler",
                "code": "EQ-002",
                "partner_id": cls.partner.id,
            }
        )

    def _task(self, equipments=None):
        return self.env["project.task"].create(
            {
                "name": "Yearly maintenance",
                "project_id": self.project.id,
                "partner_id": self.partner.id,
                "equipment_ids": [Command.set(equipments.ids if equipments else [])],
            }
        )

    def test_no_equipment(self):
        self.assertFalse(self._task().equipment_summary)

    def test_one_equipment_with_location_notes(self):
        task = self._task(self.pump)
        self.assertEqual(
            task.equipment_summary, "EQ-001 — Circulation pump · Basement, room B12"
        )

    def test_one_equipment_without_location_notes(self):
        task = self._task(self.boiler)
        self.assertEqual(task.equipment_summary, "EQ-002 — Boiler")

    def test_two_equipments_one_line_each(self):
        task = self._task(self.pump | self.boiler)
        self.assertEqual(
            task.equipment_summary.split("\n"),
            [
                "EQ-001 — Circulation pump · Basement, room B12",
                "EQ-002 — Boiler",
            ],
        )

    def test_equipment_without_code(self):
        self.boiler.code = False
        task = self._task(self.boiler)
        self.assertEqual(task.equipment_summary, "Boiler")

    def test_long_location_notes_are_flattened_and_trimmed(self):
        self.pump.location_notes = "  Door code 1234.\n\nTake the  stairs " + "x" * 300
        task = self._task(self.pump)
        line = task.equipment_summary
        prefix = "EQ-001 — Circulation pump · "
        self.assertTrue(line.startswith(prefix + "Door code 1234. Take the stairs x"))
        notes = line[len(prefix) :]
        self.assertEqual(len(notes), LOCATION_NOTES_MAX)
        self.assertTrue(notes.endswith("…"))
        self.assertNotIn("\n", line)

    def test_short_notes_are_not_cut(self):
        self.pump.location_notes = "x" * LOCATION_NOTES_MAX
        task = self._task(self.pump)
        self.assertTrue(task.equipment_summary.endswith("x" * LOCATION_NOTES_MAX))

    def test_blank_location_notes_are_omitted(self):
        self.pump.location_notes = "  \n "
        task = self._task(self.pump)
        self.assertEqual(task.equipment_summary, "EQ-001 — Circulation pump")

    def test_summary_follows_equipment_edits(self):
        task = self._task(self.boiler)
        self.boiler.write({"name": "Main boiler", "location_notes": "Roof"})
        self.assertEqual(task.equipment_summary, "EQ-002 — Main boiler · Roof")
