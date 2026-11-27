from odoo import api, fields, models


class FsmPrepTemplateLine(models.Model):
    """A « to bring » line on a task template, copied to the visit when the
    template is applied."""

    _name = "fsm.prep.template.line"
    _description = "To Bring Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "project.task.template",
        string="Task Template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    tool_id = fields.Many2one("fsm.service.tool", string="Tool", ondelete="restrict")
    name = fields.Char(
        string="Description",
        compute="_compute_name",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    quantity = fields.Integer(default=1, required=True)

    _quantity_positive = models.Constraint(
        "CHECK (quantity > 0)",
        "The quantity to bring must be positive.",
    )

    @api.depends("tool_id")
    def _compute_name(self):
        for line in self:
            if line.tool_id:
                line.name = line.tool_id.name

    def _prepare_prep_line_vals(self):
        """Values of the visit « to bring » line copied from this line."""
        self.ensure_one()
        return {
            "sequence": self.sequence,
            "name": self.name,
            "tool_id": self.tool_id.id,
            "quantity": self.quantity,
        }
