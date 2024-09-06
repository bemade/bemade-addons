from odoo import models, fields, api, _


class Equipment(models.Model):
    _name = "fsm.equipment"
    _description = "Partner-Owned Equipment"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    code = fields.Char(
        tracking=True,
    )
    name = fields.Char(
        tracking=True,
        required=True,
    )

    tag_ids = fields.Many2many(
        comodel_name="fsm.equipment.tag",
        string="Tags",
    )

    description = fields.Text(tracking=True)

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Physical Address",
        tracking=True,
        ondelete="cascade",
    )

    location_notes = fields.Text(
        string="Physical Location Notes",
        tracking=True,
        help="Any useful information about physical location "
        "(door codes, directions, etc.).",
    )

    task_ids = fields.Many2many(
        comodel_name="project.task",
        relation="fsm_task_equipment_rel",
        column1="equipment_id",
        column2="task_id",
        string="Interventions",
    )

    active = fields.Boolean(
        default=True,
        tracking=True,
    )

    equipment_component_ids = fields.One2many(
        "fsm.equipment.component",
        inverse_name="equipment_id",
        tracking=True,
    )

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        args = args or []
        if name:
            equipments = self.search(
                [
                    "|",
                    "|",
                    ("code", operator, name),
                    ("name", operator, name),
                    ("partner_id.name", operator, name),
                ],
                limit=limit,
            )
        else:
            equipments = self.search(args, limit=limit)
        return [(equipment.id, equipment.display_name) for equipment in equipments]

    def action_view_equipment(self):
        return {
            "name": "Equipment",
            "view_type": "form",
            "view_mode": "form",
            "res_id": self.id,
            "context": self.env.context,
            "res_model": "fsm.equipment",
            "type": "ir.actions.act_window",
        }

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            tag_part = "[%s] " % rec.code if rec.code else ""
            name = rec.name or ""
            rec.display_name = tag_part + name
