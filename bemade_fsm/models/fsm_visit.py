from odoo import models, fields, api


class FSMVisit(models.Model):
    _name = "bemade_fsm.visit"
    _description = "Represents a single visit by assigned service personnel."

    label = fields.Text(
        string="Label",
        required=True,
        related="so_section_id.name",
        readonly=False,
        copy=True,
    )

    approx_date = fields.Date(string="Approximate Date", copy=False)

    so_section_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="Sale Order Section",
        help=(
            "The section on the sale order that represents the labour and parts for"
            " this visit"
        ),
        ondelete="cascade",
    )

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sales Order",
        readonly=True,
        copy=False,
    )

    is_completed = fields.Boolean(
        string="Completed", related="so_section_id.is_fully_delivered"
    )

    is_invoiced = fields.Boolean(
        string="Invoiced", related="so_section_id.is_fully_delivered_and_invoiced"
    )

    summarized_equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        string="Equipment to Service",
        compute="_compute_summarized_equipment_ids",
    )

    task_id = fields.Many2one(
        comodel_name="project.task",
        compute="_compute_task_id",
        string="Service Visit",
        store=True
    )

    task_ids = fields.One2many(comodel_name="project.task", inverse_name="visit_id", copy=False)

    visit_no = fields.Integer(
        compute="_compute_visit_no",
    )

    @api.depends("task_ids")
    def _compute_task_id(self):
        for rec in self:
            rec.task_id = rec.task_ids and rec.task_ids[0]

    @api.depends("so_section_id", "sale_order_id.summary_equipment_ids")
    def _compute_summarized_equipment_ids(self):
        for rec in self:
            lines = rec.so_section_id.get_section_line_ids()
            equipment_ids = []
            for line in lines:
                for equipment in line.equipment_ids:
                    equipment_ids.append(equipment)
            rec.summarized_equipment_ids = equipment_ids

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec, vals in zip(recs, vals_list):
            if rec.so_section_id:
                continue
            # Put the new section after every existing line of the order: with
            # the default sequence (10) it could land inside an earlier visit's
            # section and take over that visit's lines.
            last_sequence = max(
                rec.sale_order_id.order_line.mapped("sequence"), default=0
            )
            rec.so_section_id = rec.env["sale.order.line"].create(
                {
                    "order_id": rec.sale_order_id.id,
                    "display_type": "line_section",
                    "name": vals.get("label", False),
                    "sequence": last_sequence + 1,
                }
            )
        return recs

    @api.depends(
        "so_section_id",
        "sale_order_id",
        "sale_order_id.visit_ids",
        "sale_order_id.visit_ids.task_id",
        "sale_order_id.visit_ids.task_id.planned_date_begin",
    )
    def _compute_visit_no(self):
        for rec in self:
            # Sort visits by task planned_date_begin, with None dates at the end
            ordered_visits = rec.sale_order_id.visit_ids.sorted(
                key=lambda v: (v.task_id.planned_date_begin or False, v.id)
            )
            rec.visit_no = 0
            for index, visit in enumerate(ordered_visits):
                if visit == rec:
                    rec.visit_no = index + 1
                    break
