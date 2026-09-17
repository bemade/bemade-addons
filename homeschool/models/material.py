# -*- coding: utf-8 -*-
from odoo import fields, models

DIFFUSION = [("internal", "Internal"), ("institutional", "Institutional")]


class Material(models.Model):
    _name = "homeschool.material"
    _description = "Teaching material (fiche, worksheet, poster…)"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True)
    kind = fields.Selection(
        [("fiche", "Fiche"), ("worksheet", "Worksheet"), ("poster", "Poster"), ("reading", "Reading"), ("exercise", "Exercise")],
        required=True, default="fiche",
    )
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF", ondelete="set null")
    attachment_ids = fields.Many2many("ir.attachment", "homeschool_material_attachment_rel", "material_id", "attachment_id", string="Files")
    html_source_path = fields.Char(help="Path of the HTML source in the family repository (e.g. materiel/fiches/x.html).")
    pdf_path = fields.Char(help="Path of the PDF in the family repository, when imported from the inventory.")
    subject_ids = fields.Many2many("homeschool.subject", "homeschool_material_subject_rel", "material_id", "subject_id")
    item_ids = fields.Many2many("homeschool.item", "homeschool_material_item_rel", "material_id", "item_id", string="Curriculum items")
    block_ids = fields.Many2many("homeschool.block", "homeschool_block_material_rel", "material_id", "block_id", string="Used in blocks")
    description = fields.Text()
    diffusion = fields.Selection(DIFFUSION, required=True, default="internal", tracking=True)
    active = fields.Boolean(default=True)
