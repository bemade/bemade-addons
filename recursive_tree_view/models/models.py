# models/parent_field_service.py
from odoo import models, api


class ParentFieldService(models.AbstractModel):
    _name = "parent.field.service"
    _description = "Service to retrieve parent field dynamically for any model"

    @api.model
    def get_parent_field(self, model_name):
        """
        Returns the parent field name for the given model.
        If _parent_name is not set, defaults to 'parent_id' if the field exists.
        """
        Model = self.env[model_name]  # Access the model dynamically
        return Model._parent_name or (
            "parent_id" if hasattr(Model, "parent_id") else None
        )
