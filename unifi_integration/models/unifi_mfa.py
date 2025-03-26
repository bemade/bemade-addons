# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import logging
import requests
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class UnifiMfa(models.TransientModel):
    """Modèle transitoire pour l'authentification à deux facteurs UniFi
    
    Ce modèle gère le processus d'authentification à deux facteurs pour les sites
    qui ont activé cette fonctionnalité. Il est utilisé dans le flux d'authentification
    pour collecter et valider les codes MFA.
    """
    _name = 'unifi.mfa'
    _description = 'UniFi MFA Authentication'
    
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='Le site pour lequel l\'authentification à deux facteurs est requise'
    )
    
    mfa_code = fields.Char(
        string='Code MFA',
        required=True,
        help='Code d\'authentification à deux facteurs fourni par l\'application d\'authentification'
    )
    
    mfa_token = fields.Char(
        string='Token MFA',
        help='Token temporaire reçu lors de la première étape d\'authentification'
    )
    
    auth_type = fields.Selection(
        selection=[
            ('site_manager', 'Site Manager API'),
            ('controller', 'Controller API')
        ],
        string='Type d\'authentification',
        required=True,
        default='site_manager',
        help='Type d\'API pour lequel l\'authentification à deux facteurs est requise'
    )
    
    expiry = fields.Datetime(
        string='Date d\'expiration',
        help='Date et heure d\'expiration de ce code MFA'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge de la méthode create pour définir la date d'expiration
        
        Args:
            vals_list (list): Liste de dictionnaires contenant les valeurs pour la création des enregistrements
            
        Returns:
            unifi.mfa: Les enregistrements créés
        """
        for vals in vals_list:
            # Définir une expiration par défaut (10 minutes)
            if not vals.get('expiry'):
                vals['expiry'] = fields.Datetime.now() + timedelta(minutes=10)
        
        return super(UnifiMfa, self).create(vals_list)
    
    def validate_mfa(self):
        """Valide le code MFA et poursuit le processus d'authentification
        
        Cette méthode vérifie le code MFA fourni par l'utilisateur et, s'il est valide,
        poursuit le processus d'authentification en créant une session.
        
        Returns:
            dict: Action à effectuer après la validation (redirection, message, etc.)
        """
        self.ensure_one()
        
        # Vérifier que le code n'est pas expiré
        if self.expiry and self.expiry < fields.Datetime.now():
            raise ValidationError(_("Le code MFA a expiré. Veuillez recommencer le processus d'authentification."))
        
        try:
            if self.auth_type == 'site_manager':
                return self._validate_site_manager_mfa()
            elif self.auth_type == 'controller':
                return self._validate_controller_mfa()
            else:
                raise ValidationError(_("Type d'authentification non pris en charge."))
        except Exception as e:
            _logger.error("Erreur lors de la validation du code MFA: %s", str(e))
            raise UserError(_("Erreur lors de la validation du code MFA: %s") % str(e))
    
    def _validate_site_manager_mfa(self):
        """Valide le code MFA pour l'API Site Manager
        
        Returns:
            dict: Action à effectuer après la validation
        """
        self.ensure_one()
        site = self.site_id
        
        if not site.api_key:
            raise ValidationError(_("Clé API manquante pour le site."))
        
        if not self.mfa_token:
            raise ValidationError(_("Token MFA temporaire manquant."))
        
        try:
            # Simulation de l'appel API pour valider le code MFA
            # Dans une implémentation réelle, cela ferait un appel à l'API UniFi
            
            # URL de base pour l'API Site Manager
            base_url = "https://sitemanager.ui.com/api"
            
            # Préparer les données pour la requête
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {site.api_key}"
            }
            
            data = {
                "mfa_token": self.mfa_token,
                "mfa_code": self.mfa_code
            }
            
            # Simuler la réponse - dans une implémentation réelle, cela serait:
            # response = requests.post(f"{base_url}/auth/mfa/validate", headers=headers, json=data)
            # response.raise_for_status()
            # result = response.json()
            
            # Simuler un résultat positif
            result = {
                "success": True,
                "token": "simulated_auth_token_after_mfa",
                "csrf_token": "simulated_csrf_token",
                "expiry": (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            # Créer une session d'authentification
            expiry_date = datetime.fromisoformat(result["expiry"])
            session = self.env['unifi.auth.session'].create_session(
                site_id=site.id,
                auth_type='site_manager',
                token=result["token"],
                csrf_token=result["csrf_token"],
                expiry=expiry_date
            )
            
            # Retourner une action pour rediriger vers la fiche du site
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'unifi.site',
                'res_id': site.id,
                'view_mode': 'form',
                'target': 'current',
                'context': {'show_success_notification': True}
            }
            
        except Exception as e:
            _logger.error("Erreur lors de la validation MFA pour Site Manager: %s", str(e))
            raise UserError(_("Erreur lors de la validation du code MFA: %s") % str(e))
    
    def _validate_controller_mfa(self):
        """Valide le code MFA pour l'API Controller
        
        Returns:
            dict: Action à effectuer après la validation
        """
        self.ensure_one()
        site = self.site_id
        
        # L'API Controller actuelle ne supporte pas l'authentification à deux facteurs
        # Cette méthode est incluse pour une future implémentation
        raise UserError(_("L'authentification à deux facteurs n'est pas encore supportée pour l'API Controller."))
        
    @api.model
    def request_mfa_challenge(self, site_id, auth_type, username=None, password=None, api_key=None):
        """Demande un challenge MFA à l'API
        
        Cette méthode initie le processus d'authentification à deux facteurs en demandant
        un challenge à l'API. Elle retourne un token temporaire qui sera utilisé avec
        le code MFA pour compléter l'authentification.
        
        Args:
            site_id (int): ID du site
            auth_type (str): Type d'authentification ('site_manager' ou 'controller')
            username (str, optional): Nom d'utilisateur pour l'API Controller
            password (str, optional): Mot de passe pour l'API Controller
            api_key (str, optional): Clé API pour l'API Site Manager
            
        Returns:
            dict: Informations sur le challenge MFA, incluant le token temporaire
        """
        site = self.env['unifi.site'].browse(site_id)
        
        if auth_type == 'site_manager':
            if not api_key and not site.api_key:
                raise ValidationError(_("Clé API manquante pour le site."))
            
            api_key = api_key or site.api_key
            
            try:
                # Simulation de l'appel API pour demander un challenge MFA
                # Dans une implémentation réelle, cela ferait un appel à l'API UniFi
                
                # URL de base pour l'API Site Manager
                base_url = "https://sitemanager.ui.com/api"
                
                # Préparer les données pour la requête
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                # Simuler la réponse - dans une implémentation réelle, cela serait:
                # response = requests.post(f"{base_url}/auth/mfa/challenge", headers=headers)
                # response.raise_for_status()
                # result = response.json()
                
                # Simuler un résultat positif
                result = {
                    "success": True,
                    "mfa_token": "simulated_temporary_mfa_token",
                    "expiry": (datetime.now() + timedelta(minutes=10)).isoformat()
                }
                
                # Créer un enregistrement MFA transitoire
                mfa_record = self.create({
                    'site_id': site_id,
                    'auth_type': auth_type,
                    'mfa_token': result["mfa_token"],
                    'expiry': datetime.fromisoformat(result["expiry"])
                })
                
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'unifi.mfa',
                    'res_id': mfa_record.id,
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_site_id': site_id, 'default_auth_type': auth_type}
                }
                
            except Exception as e:
                _logger.error("Erreur lors de la demande de challenge MFA: %s", str(e))
                raise UserError(_("Erreur lors de la demande de challenge MFA: %s") % str(e))
        
        elif auth_type == 'controller':
            # L'API Controller actuelle ne supporte pas l'authentification à deux facteurs
            raise UserError(_("L'authentification à deux facteurs n'est pas encore supportée pour l'API Controller."))
        
        else:
            raise ValidationError(_("Type d'authentification non pris en charge."))
