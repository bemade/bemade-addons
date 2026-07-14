from odoo import fields, models


class DataRecycleModel(models.Model):
    """Add a Law 25 *anonymize* action to Odoo's data-retention engine.

    The engine already ships ``archive`` and ``unlink`` actions. Anonymization
    is a third retention outcome: instead of removing the record we irreversibly
    overwrite the personal data it holds (implemented per-model in
    ``_law25_anonymize``) while keeping the record — and any legally-retained
    links to it (invoices, appointments) — intact.
    """

    _inherit = "data_recycle.model"

    recycle_action = fields.Selection(
        selection_add=[("anonymize", "Anonymize")],
        ondelete={"anonymize": "cascade"},
    )
