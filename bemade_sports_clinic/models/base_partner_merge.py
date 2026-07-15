from odoo import api, fields, models, _
from odoo.exceptions import UserError
from collections import defaultdict
import datetime
import itertools

class MergePartnerAutomatic(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    @api.model
    def _get_ordered_partner(self, partner_ids):
        # Delegate to super to avoid drift
        return super()._get_ordered_partner(partner_ids)

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        """Refuse merges that would silently destroy patient records.

        sports.patient declares UNIQUE(partner_id). When several of the merged
        contacts each carry a patient, core's _update_foreign_keys_generic tries
        to repoint them all at the destination, hits that constraint, and
        recovers by issuing a raw ``DELETE FROM sports_patient`` (see
        odoo/addons/base/wizard/base_partner_merge.py). That bypasses the ORM
        and ondelete="restrict", and the database then CASCADEs away the
        patients' injuries, treatment notes, documents and team links. The merge
        reports success while the clinical history is gone -- this destroyed two
        players' records in production on 2026-07-15.

        Patients are counted with active_test=False: an archived patient still
        occupies UNIQUE(partner_id) and is just as deletable by that DELETE.

        Note the Merge Players wizard consolidates patients *before* delegating
        the res.partner half to this method, so by then only one patient remains
        and this guard passes on its own -- no bypass flag is needed.
        """
        patients = self.env['sports.patient'].sudo().with_context(
            active_test=False,
        ).search([('partner_id', 'in', partner_ids)])
        if len(patients) > 1:
            names = "\n".join(
                " - %s" % name
                for name in sorted(patients.mapped('partner_id.name'))
            )
            raise UserError(_(
                "These contacts belong to more than one player:\n\n%(names)s\n\n"
                "Merging the contacts would delete all but one of these players, "
                "along with their injuries, treatment notes and documents.\n\n"
                "To combine them, open the Players list, select the players, and "
                "use Actions → Merge Players. That merges the players and "
                "their contacts together, keeping the clinical history.",
                names=names,
            ))
        return super()._merge(
            partner_ids, dst_partner=dst_partner, extra_checks=extra_checks)

    @api.model
    def _update_values(self, src_partners, dst_partner):
        """
        Override to allow writing partner 'name' during merge by using the
        'patient_update' context key expected by bemade_sports_clinic's
        res.partner.write() guard.
        Logic mirrors base implementation, but writes are done with context.
        """
        # Copy of base logic with minimal changes: all writes use context
        model_fields = dst_partner.fields_get().keys()
        summable_fields = self._get_summable_fields()

        def write_serializer(item):
            if isinstance(item, models.BaseModel):
                return item.id
            else:
                return item

        values = dict()
        values_by_company = defaultdict(dict)  # {company: vals}
        for column in model_fields:
            field = dst_partner._fields[column]
            if field.type not in ('many2many', 'one2many') and field.compute is None:
                for item in itertools.chain(src_partners, [dst_partner]):
                    if item[column]:
                        if field.type == 'reference':
                            values[column] = item[column]
                        elif column in summable_fields and values.get(column):
                            values[column] += write_serializer(item[column])
                        else:
                            values[column] = write_serializer(item[column])
            elif field.company_dependent and column in summable_fields:
                partners = (src_partners + dst_partner).sudo()
                for company in self.env['res.company'].sudo().search([]):
                    values_by_company[company][column] = sum(
                        partners.with_company(company).mapped(column)
                    )

        # remove fields that can not be updated (id and parent_id)
        values.pop('id', None)
        parent_id = values.pop('parent_id', None)
        dst_partner.with_context(patient_update=True).write(values)
        for company, vals in values_by_company.items():
            dst_partner.with_company(company).sudo().with_context(patient_update=True).write(vals)
        # try to update the parent_id
        if parent_id and parent_id != dst_partner.id:
            try:
                dst_partner.with_context(patient_update=True).write({'parent_id': parent_id})
            except Exception:
                # keep same logging behavior as base without relying on logger here
                pass

        # After core writes, if destination partner is a patient's contact,
        # recompute the partner's display name from that patient's first/last name
        # to ensure consistency after merge.
        patient = self.env['sports.patient'].sudo().search([('partner_id', '=', dst_partner.id)], limit=1)
        if patient:
            # Use existing helper that writes partner.name with patient_update context
            patient._recompute_name()
