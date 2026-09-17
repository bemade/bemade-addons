# -*- coding: utf-8 -*-
"""Export records back to the family repository's CSV files (UC-11). Filled in during TDD."""
from odoo import api, models


class RepositoryExporter(models.AbstractModel):
    _name = "homeschool.exporter"
    _description = "Family repository exporter"
