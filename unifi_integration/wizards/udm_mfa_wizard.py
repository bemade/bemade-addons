# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class UdmMfaWizard(models.TransientModel):
    """Assistant pour entrer le code MFA"""
    _name = 'udm.mfa.wizard'
    _description = 'Assistant Code MFA'

    mfa_code = fields.Char(string='Code MFA', required=True, help="Entrez le code d'authentification reçu par courriel")
    config_id = fields.Many2one('udm.configuration', string='Configuration')

    def action_validate_mfa(self):
        """Valide le code MFA et continue l'importation"""
        self.ensure_one()
        if not self.config_id:
            raise UserError(_("Configuration non trouvée"))

        # Met à jour le code MFA dans la configuration
        self.config_id.write({'mfa_token': self.mfa_code})
        
        # Relance l'importation
        return self.config_id.action_import_configuration()
