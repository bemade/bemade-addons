from odoo import models, fields, api


class ApplicationSpecificationKey(models.Model):
    _name = "partner.application.specification.key"
    _description = "Application Specification Key"

    name = fields.Char(required=True, index="trigram")
    _sql_constraints = [
        ("name_uniq", "unique (name)", "Specification key name must be unique."),
    ]
