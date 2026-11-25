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
    return_delay_days = fields.Integer(
        string="Return Delay (days)",
        default=1,
        required=True,
        help="Days the tool stays unavailable after a visit's planned end "
        "(coming back, cleaning). A visit needing this tool conflicts with "
        "another one that starts before that visit's end plus this delay. "
        "0: the tool is available again as soon as the visit ends.",
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()

    _quantity_owned_positive = models.Constraint(
        "CHECK (quantity_owned >= 0)",
        "The quantity owned cannot be negative.",
    )
    _return_delay_days_positive = models.Constraint(
        "CHECK (return_delay_days >= 0)",
        "The return delay cannot be negative.",
    )
