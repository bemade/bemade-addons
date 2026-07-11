from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError
from odoo.tools import _


class DataRecycleRecord(models.Model):
    """Route ``anonymize``-action records to the target model's Law 25
    anonymization instead of the core archive/unlink dispatch.

    Only ``recycle_action == 'anonymize'`` candidates are handled here; every
    other action is delegated to the pristine core implementation. Nothing runs
    until an admin clicks *Validate* on a review candidate — the manual-mode
    cron merely creates the candidates.
    """

    _inherit = "data_recycle.record"

    def action_validate(self):
        anonymize_records = self.filtered(
            lambda r: r.recycle_model_id.recycle_action == "anonymize"
        )
        # Let core handle archive/unlink exactly as-is.
        other_records = self - anonymize_records
        res = super(DataRecycleRecord, other_records).action_validate()
        if not anonymize_records:
            return res

        original_records = {
            "%s_%s" % (r._name, r.id): r
            for r in anonymize_records._original_records()
        }
        targets_by_model = defaultdict(list)
        for record in anonymize_records:
            original = original_records.get(
                "%s_%s" % (record.res_model_name, record.res_id)
            )
            if original:
                targets_by_model[original._name].append(original.id)

        for model_name, ids in targets_by_model.items():
            model = self.env[model_name]
            if not hasattr(model, "_law25_anonymize"):
                raise UserError(
                    _(
                        "Model %s does not support the Anonymize retention action."
                    )
                    % model_name
                )
            model.sudo().browse(ids)._law25_anonymize()

        # Drop the handled candidates. The target now carries is_anonymized=True
        # so the next scan will not re-surface it.
        anonymize_records.unlink()
        return res
