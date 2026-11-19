from odoo import fields, models


class FsmServiceTool(models.Model):
    """A tool the company owns and brings to field service visits.

    Not a stock product: no moves, only the quantity owned, used to warn when
    visits planned at the same time need more of it than we have.
    """

    _name = "fsm.service.tool"
    _description = "Service Tool"
    _order = "name, id"

    name = fields.Char(required=True, translate=True)
    quantity_owned = fields.Integer(
        string="Quantity Owned",
        default=1,
        required=True,
        help="How many of this tool the company owns. Visits planned on "
        "overlapping dates that need more than this are flagged.",
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _quantity_owned_positive = models.Constraint(
        "CHECK (quantity_owned >= 0)",
        "The quantity owned cannot be negative.",
    )
