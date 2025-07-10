# -*- coding: utf-8 -*-


from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    sale_order_ids = fields.One2many(
        "sale.order",
        "helpdesk_ticket_id",
        string="Sale Orders",
        help="Sale orders associated to this ticket.",
        copy=False,
    )
    sale_order_count = fields.Integer(compute="_compute_sale_order_count")
    team_use_sale_orders = fields.Boolean(related="team_id.use_sale_orders", string="Team Uses Sales Orders", readonly=True)

    @api.depends("sale_order_ids")
    def _compute_sale_order_count(self):
        self.sale_order_count = len(self.sale_order_ids)

    def action_view_sale_order(self):
        self.ensure_one()
        
        action = {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "context": {"create": False},
            "name": _("Sale Orders"),
            "view_mode": "list,form",
        }

        if self.sale_order_count == 1:
            action.update({
                "res_id": self.sale_order_ids[0].id,
                "view_mode": "form",
            })
        else:
            action.update({
                "domain": [("id", "in", self.sale_order_ids.ids)],
            })
        return action

    def action_convert_to_sale_order(self):
        self.ensure_one()
        if not self.team_use_sale_orders:
            raise UserError(_("Creating quotes from tickets is not enabled for this helpdesk team."))

        so_values = self._generate_so_values()
        so = self.env["sale.order"].create([so_values])
        self.message_change_thread(so)
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "helpdesk.ticket"), ("res_id", "=", self.id)]
        )
        attachments.sudo().write({"res_model": "sale.order", "res_id": so.id})
        activities = self.activity_ids
        activities.sudo().write(
            {
                "res_model_id": self.env.ref("sale.model_sale_order").id,
                "res_id": so.id,
                "res_model": "sale.order",
            }
        )
        
        # Archive the ticket
        self.action_archive()
        
        # Retourner une action directe vers le devis créé
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": so.id,
            "view_mode": "form",
            "context": {"create": False},
        }

    def _generate_so_values(self):
        team = self.user_id.sale_team_id if self.user_id else self.env.user.sale_team_id
        if not team:
            raise UserError(
                _(
                    "Creating sale orders is reserved to sales users. Assign the user to sale team first."
                )
            )
        team_id = team.id
        return {
            "partner_id": self.partner_id.id,
            "helpdesk_ticket_id": self.id,
            "company_id": self.company_id.id,
            "team_id": team_id,
        }
