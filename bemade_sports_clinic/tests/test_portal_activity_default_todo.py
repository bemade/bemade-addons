from odoo.tests import HttpCase, tagged
from odoo import Command
from odoo import fields
import re


@tagged("-at_install", "post_install")
class TestPortalActivityDefaultTodo(HttpCase):
    """Verify the activity creation form defaults the activity type to 'To Do'."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Org/team/patient setup
        cls.organization = cls.env['res.partner'].create({
            'name': 'Default Todo Org',
            'is_company': True,
        })
        cls.team = cls.env['sports.team'].create({
            'name': 'Default Todo Team',
            'parent_id': cls.organization.id,
        })
        cls.patient = cls.env['sports.patient'].create({
            'first_name': 'Default',
            'last_name': 'TodoPatient',
            'date_of_birth': '2005-01-01',
            'team_ids': [(4, cls.team.id)],
        })

        # Create a portal treatment professional user and add to team staff
        cls.tp_partner = cls.env['res.partner'].create({
            'name': 'Portal TP',
            'email': 'portal.tp.todo@example.com',
        })
        cls.tp_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.tp_partner.id,
            'login': 'portal.tp.todo@example.com',
            'password': 'tp',
            'name': cls.tp_partner.name,
            'group_ids': [
                Command.link(cls.env.ref('base.group_portal').id),
                Command.link(cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id),
            ]
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.tp_partner.id,
            'role': 'therapist',
        })

        # Resolve the expected default To Do activity type id using the same priority as controller
        todo_type = cls.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo_type:
            todo_type = cls.env['mail.activity.type'].search([('category', '=', 'todo')], limit=1)
        if not todo_type:
            todo_type = cls.env['mail.activity.type'].search([('name', 'ilike', 'todo')], limit=1)
        cls.todo_type_id = todo_type and todo_type.id or False

    def test_activity_create_form_defaults_todo(self):
        self.assertTrue(self.todo_type_id, "A 'To Do' activity type must exist for this test")

        # Login
        self.authenticate('portal.tp.todo@example.com', 'tp')

        # Open create activity form for patient
        resp = self.url_open(f"/my/activity/create?model=sports.patient&res_id={self.patient.id}", timeout=30)
        self.assertEqual(resp.status_code, 200)

        # Assert the To Do option is pre-selected in the HTML
        # QWeb renders selected attribute when t-att-selected resolves truthy, typically selected="selected"
        pattern = rf'<option[^>]+value="{self.todo_type_id}"[^>]+selected'
        self.assertRegex(resp.text, pattern, msg="Expected the 'To Do' activity type to be pre-selected")
