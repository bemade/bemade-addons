from odoo import models, fields, api


class IncrementingSequenceMixin(models.AbstractModel):
    _name = "incrementing.sequence.mixin"
    _description = "Incrementing Sequence Mixin"
    _order = "sequence, id asc"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "incrementing.sequence.mixin" in cls._inherit:
            if not hasattr(cls, "_sequence_group"):
                raise ValueError(
                    f"Model {cls._name} inheriting from incrementing.sequence.mixin must define a '_sequence_group' attribute."
                )

    sequence = fields.Integer()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if rec.sequence == 0:
                group_field = getattr(rec, "_sequence_group")
                group_field_data = getattr(rec, group_field)
                if hasattr(group_field_data, "id"):
                    group_field_data = group_field_data.id
                    group = self.env[rec._name].search(
                        [(group_field, "=", group_field_data)]
                    )
                else:
                    group = None
                max_seq = max(group.mapped("sequence")) if group else 0
                rec.sequence = max_seq + 1
        return res

    def _default_sequence(self):
        group_field = getattr(self, "_sequence_group")
        group_field_data = getattr(self, group_field)
        if hasattr(group_field_data, "id"):
            group_field_data = group_field_data.id
            group = self.env[self._name].search([(group_field, "=", group_field_data)])
        else:
            group = None
        max_seq = max(group.mapped("sequence")) if group else 0
        # Don't recalculate if already set
        for rec in self.filtered(lambda r: r.sequence == 0):
            max_seq += 1
            rec.sequence = max_seq

    def _inverse_sequence(self):
        pass
