from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError


class Equipment(models.Model):
    _name = "fsm.equipment"
    _description = "Partner-Owned Equipment"
    _inherit = ["mail.thread", "mail.activity.mixin", "incrementing.sequence.mixin"]
    _sequence_group = "parent_id"

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
        ondelete="restrict",
        required=False,
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

    parent_id = fields.Many2one(
        "fsm.equipment",
        tracking=True,
    )
    inherited_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Main Equipment Location",
        readonly=True,
        compute="_compute_inherited_partner_id",
        recursive=True,
    )

    child_ids = fields.One2many(
        "fsm.equipment",
        inverse_name="parent_id",
        string="Components",
        tracking=True,
    )

    product_id = fields.Many2one(
        "product.product",
        ondelete="restrict",
        help="The product that represents this equipment, if any.",
    )

    @api.depends("parent_id", "parent_id.partner_id")
    def _compute_inherited_partner_id(self):
        for rec in self:
            if not rec.parent_id:
                rec.inherited_partner_id = False
                continue
            rec.inherited_partner_id = (
                rec.parent_id.partner_id or rec.parent_id.inherited_partner_id
            )

    @api.constrains("product_id", "partner_id")
    def _constrain_only_root_has_partner(self):
        for rec in self:
            if rec.partner_id and rec.parent_id:
                raise ValidationError(
                    _("Only top-level (root) equipments can be linked to a partner.")
                )
            if not rec.parent_id and not rec.partner_id:
                raise ValidationError(
                    _("Top-level (root) equipments must be linked to a partner.")
                )

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):

        args = args or []
        domain = expression.AND(
            [
                args,
                [
                    "|",
                    "|",
                    ("code", operator, name),
                    ("name", operator, name),
                    ("partner_id.name", operator, name),
                ],
            ]
        )

        if name:
            equipments = self.search(
                domain,
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
