from odoo import models, fields, api, _


class MailFollowers(models.Model):
    _inherit = "mail.followers"

    # This is a user quality of life modification, to avoid duplicated message subtype subscription for internal
    # and external notifications (since both subtypes are default=True).

    def write(self, vals):
        # Call super first to handle the actual write operation
        result = super().write(vals)
        
        # Only process subtype deduplication if subtype_ids was actually changed
        if 'subtype_ids' in vals:
            subtypes_map = self.__subtypes_map()
            for record in self:
                try:
                    # Ensure we have a valid record and model
                    if record.exists() and record.res_model in subtypes_map:
                        internal_subtype, external_subtype = subtypes_map.get(record.res_model)
                        if (external_subtype and internal_subtype and 
                            external_subtype in record.subtype_ids and 
                            internal_subtype in record.subtype_ids):
                            record.subtype_ids = record.subtype_ids - external_subtype
                except Exception:
                    # If there's any issue with individual record processing, continue with others
                    # This prevents partner merge operations from failing due to subtype processing
                    continue
        
        return result

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        subtypes_map = self.__subtypes_map()
        to_fix = {
            model:
                recs.filtered(
                    lambda rec: rec.res_model == model
                                and subtypes[0] in rec.subtype_ids
                                and subtypes[1] in rec.subtype_ids
                ) for model, subtypes in subtypes_map.items()
        }
        for model, records in to_fix.items():
            for rec in records:
                rec.subtype_ids = rec.subtype_ids - subtypes_map[model][1]
        return recs

    def __subtypes_map(self):
        xml_id_fmt_string = "bemade_sports_clinic.subtype_{0}_{1}_update"
        return {
            'sports.patient': (
                self.env.ref(xml_id_fmt_string.format('patient', 'internal')),
                self.env.ref(xml_id_fmt_string.format('patient', 'external')),
            ),
            'sports.patient.injury': (
                self.env.ref(xml_id_fmt_string.format('patient_injury', 'internal')),
                self.env.ref(xml_id_fmt_string.format('patient_injury', 'external')),
            ),
        }
