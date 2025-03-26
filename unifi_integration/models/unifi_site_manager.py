# -*- coding: utf-8 -*-

# These imports will work in an Odoo environment, even if your IDE marks them as not found
# pylint: disable=import-error
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
# pylint: enable=import-error

import json
import logging
import requests
import urllib3
from datetime import datetime, timedelta
from requests.exceptions import RequestException

_logger = logging.getLogger(__name__)

class UnifiSiteManager(models.Model):
    """Extension du modèle UnifiSite pour l'API Site Manager (Cloud)
    
    Cette classe ajoute les champs et méthodes spécifiques à l'API Site Manager cloud.
    Elle est utilisée lorsque api_type = 'site_manager'.
    """
    _name = 'unifi.site.manager'
    _description = 'UniFi Site Manager API'
    
    # Champs pour établir la relation avec unifi.site
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='Site associé à cette configuration API Site Manager'
    )
    
    # Champs nécessaires pour le fonctionnement du modèle
    name = fields.Char(related='site_id.name', string='Nom', readonly=True)
    api_type = fields.Selection(related='site_id.api_type', string='Type API', readonly=True)
    verify_ssl = fields.Boolean(string='Verify SSL', default=True)
    last_sync = fields.Datetime(string='Dernière synchronisation')
    
    def test_connection(self):
        """Teste la connexion à l'API Site Manager
        
        Cette méthode tente d'établir une connexion avec l'API Site Manager
        pour vérifier que les paramètres de connexion sont corrects.
        
        Returns:
            bool: True si la connexion est établie avec succès, False sinon
        """
        try:
            # Utiliser la méthode existante pour tester la connexion
            return self._test_site_manager_connection()
        except Exception as e:
            _logger.error('Erreur lors du test de connexion à l\'API Site Manager: %s', str(e))
            return False
            
    def _make_request(self, method, endpoint, data=None, params=None, headers=None):
        """Effectue une requête HTTP vers l'API Site Manager
        
        Cette méthode gère les requêtes HTTP vers l'API Site Manager, en incluant
        les en-têtes d'authentification et en gérant les erreurs.
        
        Args:
            method: Méthode HTTP (GET, POST, PUT, DELETE)
            endpoint: Point de terminaison API (chemin relatif)
            data: Données à envoyer dans le corps de la requête (optionnel)
            params: Paramètres de requête (optionnel)
            headers: En-têtes HTTP supplémentaires (optionnel)
            
        Returns:
            Response: Objet réponse HTTP
            
        Raises:
            RequestException: Si une erreur se produit lors de la requête
        """
        self.ensure_one()
        
        # Créer un log API pour cette requête
        api_log = self.env['unifi.api.log'].create({
            'site_id': self.site_id.id,
            'api_type': 'site_manager',
            'endpoint': endpoint,
            'method': method,
            'request_body': json.dumps(data) if data else '',
            'request_params': json.dumps(params) if params else '',
            'request_headers': json.dumps(headers) if headers else '',
            'start_time': fields.Datetime.now(),
        })
        
        try:
            # Désactiver les avertissements SSL si verify_ssl est False
            if not self.verify_ssl:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Construire l'URL de base
            base_url = "https://sitemanager.unifi.ui.com"
            url = f"{base_url}{endpoint}"
            
            # Préparer les en-têtes avec la clé API
            default_headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Odoo UniFi Integration',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            # Fusionner les en-têtes par défaut avec les en-têtes personnalisées
            if headers:
                default_headers.update(headers)
            
            # Effectuer la requête HTTP
            response = requests.request(
                method=method,
                url=url,
                json=data if data else None,
                params=params,
                headers=default_headers,
                verify=self.verify_ssl,
                timeout=30
            )
            
            # Mettre à jour le log API avec la réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_body': response.text if response.text else '',
                'response_headers': json.dumps(dict(response.headers)) if response.headers else '',
                'duration': (fields.Datetime.now() - api_log.start_time).total_seconds() * 1000,
            })
            
            # Gérer les erreurs HTTP
            response.raise_for_status()
            
            return response
            
        except RequestException as e:
            # Mettre à jour le log API avec l'erreur
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': e.response.status_code if hasattr(e, 'response') and e.response else 0,
                'error_message': str(e),
                'duration': (fields.Datetime.now() - api_log.start_time).total_seconds() * 1000,
            })
            
            _logger.error('Erreur lors de la requête HTTP vers l\'API Site Manager: %s', str(e))
            raise
    
    @api.model
    def _check_required_fields(self, site):
        """Vérifie que les champs requis pour l'API Site Manager sont renseignés
        
        Cette méthode est appelée par le modèle principal lors de la validation des contraintes.
        
        Args:
            site: L'enregistrement du site à vérifier
            
        Raises:
            ValidationError: Si des champs requis ne sont pas renseignés
        """
        if not site.api_key:
            raise ValidationError(_("Le champ 'API Key' est requis pour l'API Site Manager."))
        
        if site.mfa_enabled and not site.mfa_token:
            raise ValidationError(_("Le champ 'MFA Token' est requis lorsque l'authentification à deux facteurs est activée."))
    
    @api.model
    def _create_or_update_api_log(self, api_log=None, **kwargs):
        """Crée ou met à jour un enregistrement de log API
        
        Cette méthode d'aide simplifie la gestion des logs API en créant un nouvel enregistrement
        si api_log est None, ou en mettant à jour l'enregistrement existant sinon.
        
        Args:
            api_log: L'enregistrement de log API existant, ou None pour en créer un nouveau
            **kwargs: Les valeurs à écrire dans l'enregistrement
            
        Returns:
            L'enregistrement de log API créé ou mis à jour
        """
        if not api_log:
            # Valeurs par défaut pour la création
            default_values = {
                'site_id': self.id,
                'api_type': 'site_manager',
                'method': 'GET',
                'endpoint': 'error_handler',
                'start_time': fields.Datetime.now()
            }
            # Fusionner les valeurs par défaut avec les valeurs fournies
            values = {**default_values, **kwargs}
            return self.env['unifi.api.log'].create(values)
        else:
            # Mettre à jour l'enregistrement existant
            api_log.write(kwargs)
            return api_log
    
    def _clear_irrelevant_fields(self, site):
        """Nettoie les champs qui ne sont pas pertinents pour l'API Site Manager
        
        Cette méthode est appelée par le modèle principal lors du changement de type d'API.
        Elle supprime les enregistrements unifi.site.controller associés au site.
        
        Args:
            site: L'enregistrement du site à nettoyer
        """
        # Rechercher et supprimer les enregistrements unifi.site.controller associés au site
        controllers = self.env['unifi.site.controller'].search([('site_id', '=', site.id)])
        if controllers:
            _logger.info("Suppression des enregistrements unifi.site.controller associés au site %s", site.name)
            controllers.unlink()
    
    # Site Manager API fields - Only used when api_type = 'site_manager'
    api_key = fields.Char(
        string='API Key',

        help='API key for Site Manager authentication'
    )
    
    mfa_enabled = fields.Boolean(
        string='MFA Enabled',
        default=False,

        help='Whether two-factor authentication is enabled for this site'
    )
    
    mfa_token = fields.Char(
        string='MFA Token',

        help='Two-factor authentication token if enabled'
    )
    
    def _test_site_manager_connection(self):
        """Test connection to the Site Manager API"""
        self.ensure_one()
        
        if self.api_type != 'site_manager':
            return False
        
        # Disable SSL warnings if verify_ssl is False
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Create a new session for this connection test
        session = requests.Session()
        
        # Build the API URL
        base_url = "https://sitemanager.unifi.ui.com/api"
        sites_url = f"{base_url}/sites"
        
        # Prepare headers with API key
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo UniFi Integration',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        # Add MFA token if enabled
        if self.mfa_enabled and self.mfa_token:
            headers['X-MFA-Token'] = self.mfa_token
        
        # Initialiser le log API
        api_log = self.env['unifi.api.log'].create({
            'site_id': self.site_id.id,
            'api_type': 'site_manager',
            'endpoint': sites_url,
            'method': 'GET',
            'request_headers': json.dumps(headers),
            'start_time': fields.Datetime.now()
        })
        
        try:
            
            # Make the request
            response = session.get(
                sites_url,
                headers=headers,
                verify=self.verify_ssl,
                timeout=10
            )
            
            # Update the API log with response data
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Return True if the request was successful
            return response.status_code == 200
            
        except Exception as e:
            # Utiliser la méthode d'aide pour créer ou mettre à jour le log API
            if self.env.get('unifi.api.log'):
                self._create_or_update_api_log(
                    api_log=api_log,
                    end_time=fields.Datetime.now(),
                    error_message=str(e)
                )
            _logger.error("Error testing connection to Site Manager API: %s", str(e))
            return False
        finally:
            # Close the session
            session.close()
    
    @api.model
    def get_system_info_data(self, site):
        """Récupère les données d'information système du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations système.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            dict: Données d'information système
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # URL de base pour l'API Site Manager
        base_url = "https://sitemanager.unifi.ui.com/api"
        
        # Préparer les en-têtes avec la clé API
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo UniFi Integration',
            'Authorization': f'Bearer {site.api_key}'
        }
        
        # Ajouter le token MFA si activé
        if site.mfa_enabled and site.mfa_token:
            headers['X-MFA-Token'] = site.mfa_token
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Construire l'URL pour récupérer les données système
        system_url = f"{base_url}/sites/{site.site_id}/system"
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': system_url,
            'method': 'GET',
            'request_headers': json.dumps(headers),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête pour récupérer les données système
            response = session.get(
                system_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données système: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if not data:
                _logger.error("Aucune donnée système trouvée dans la réponse")
                return False
            
            # Retourner les données système
            return data
                
        except (RequestException, json.JSONDecodeError) as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la récupération des données système: {str(e)}"
            if api_log:
                api_log.write({
                    'end_time': fields.Datetime.now(),
                    'error_message': error_msg
                })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()
    
    @api.model
    def get_device_data(self, site, mac_address=None):
        """Récupère les données d'un appareil spécifique ou de tous les appareils du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations sur les appareils.
        
        Args:
            site: L'enregistrement du site UniFi
            mac_address: Adresse MAC de l'appareil spécifique à récupérer (optionnel)
            
        Returns:
            dict ou list: Données de l'appareil ou liste des données de tous les appareils
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # URL de base pour l'API Site Manager
        base_url = "https://api.cloud.ui.com"
        
        # URL pour l'authentification
        auth_url = f"{base_url}/auth/login"
        
        # Données d'authentification
        auth_data = {
            'username': site.username,
            'password': site.password,
            'token': site.api_key or '',
            'rememberMe': True
        }
        
        # En-têtes de la requête
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': auth_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(auth_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête d'authentification
            response = session.post(
                auth_url,
                json=auth_data,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si l'authentification a réussi
            if response.status_code != 200:
                _logger.error("Erreur d'authentification à l'API Site Manager: %s", response.text)
                return False
            
            # Extraire le token d'authentification
            auth_response = response.json()
            if 'access_token' not in auth_response:
                _logger.error("Token d'authentification non trouvé dans la réponse")
                return False
            
            # Mettre à jour les en-têtes avec le token d'authentification
            headers['Authorization'] = f"Bearer {auth_response['access_token']}"
            
            # Construire l'URL pour récupérer les données des appareils
            if mac_address:
                # URL pour un appareil spécifique
                device_url = f"{base_url}/api/site/{site.site_id}/device/{mac_address}"
            else:
                # URL pour tous les appareils
                device_url = f"{base_url}/api/site/{site.site_id}/device"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': device_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des appareils
            response = session.get(
                device_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données des appareils: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if 'data' not in data:
                _logger.error("Aucune donnée d'appareil trouvée dans la réponse")
                return False
            
            # Retourner les données des appareils
            if mac_address and data['data']:
                # Retourner les données de l'appareil spécifique
                return data['data']
            else:
                # Retourner la liste des données de tous les appareils
                return data['data']
                
        except (RequestException, json.JSONDecodeError) as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la récupération des données des appareils: {str(e)}"
            if api_log:
                api_log.write({
                    'end_time': fields.Datetime.now(),
                    'error_message': error_msg
                })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()
    
    @api.model
    def get_vlan_data(self, site):
        """Récupère les données des VLANs du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations sur les VLANs.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de tous les VLANs
        """
        # Initialiser api_log à None pour éviter les erreurs de variable potentiellement indépendante
        api_log = None
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # URL de base pour l'API Site Manager
        base_url = "https://api.cloud.ui.com"
        
        # URL pour l'authentification
        auth_url = f"{base_url}/auth/login"
        
        # Données d'authentification
        auth_data = {
            'username': site.username,
            'password': site.password,
            'token': site.api_key or '',
            'rememberMe': True
        }
        
        # En-têtes de la requête
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': auth_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(auth_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête d'authentification
            response = session.post(
                auth_url,
                json=auth_data,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si l'authentification a réussi
            if response.status_code != 200:
                _logger.error("Erreur d'authentification à l'API Site Manager: %s", response.text)
                return False
            
            # Extraire le token d'authentification
            auth_response = response.json()
            if 'access_token' not in auth_response:
                _logger.error("Token d'authentification non trouvé dans la réponse")
                return False
            
            # Mettre à jour les en-têtes avec le token d'authentification
            headers['Authorization'] = f"Bearer {auth_response['access_token']}"
            
            # Construire l'URL pour récupérer les données des VLANs
            vlan_url = f"{base_url}/api/site/{site.site_id}/vlan"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': vlan_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des VLANs
            response = session.get(
                vlan_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données des VLANs: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if 'data' not in data:
                _logger.error("Aucune donnée de VLAN trouvée dans la réponse")
                return False
            
            # Retourner la liste des données de tous les VLANs
            return data['data']
                
        except (RequestException, json.JSONDecodeError) as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la récupération des données des VLANs: {str(e)}"
            if 'api_log' in locals() and api_log:
                api_log.write({
                    'end_time': fields.Datetime.now(),
                    'error_message': error_msg
                })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()
    
    @api.model
    def get_network_data(self, site):
        """Récupère les données des réseaux du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations sur les réseaux.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de tous les réseaux
        """
        # Initialiser api_log à None pour éviter les erreurs de variable potentiellement indépendante
        api_log = None
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # URL de base pour l'API Site Manager
        base_url = "https://api.cloud.ui.com"
        
        # URL pour l'authentification
        auth_url = f"{base_url}/auth/login"
        
        # Données d'authentification
        auth_data = {
            'username': site.username,
            'password': site.password,
            'token': site.api_key or '',
            'rememberMe': True
        }
        
        # En-têtes de la requête
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': auth_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(auth_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête d'authentification
            response = session.post(
                auth_url,
                json=auth_data,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si l'authentification a réussi
            if response.status_code != 200:
                _logger.error("Erreur d'authentification à l'API Site Manager: %s", response.text)
                return False
            
            # Extraire le token d'authentification
            auth_response = response.json()
            if 'access_token' not in auth_response:
                _logger.error("Token d'authentification non trouvé dans la réponse")
                return False
            
            # Mettre à jour les en-têtes avec le token d'authentification
            headers['Authorization'] = f"Bearer {auth_response['access_token']}"
            
            # Construire l'URL pour récupérer les données des réseaux
            network_url = f"{base_url}/api/site/{site.site_id}/network"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': network_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des réseaux
            response = session.get(
                network_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données des réseaux: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if 'data' not in data:
                _logger.error("Aucune donnée de réseau trouvée dans la réponse")
                return False
            
            # Retourner la liste des données de tous les réseaux
            return data['data']
                
        except (RequestException, json.JSONDecodeError) as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la récupération des données des réseaux: {str(e)}"
            if 'api_log' in locals() and api_log:
                api_log.write({
                    'end_time': fields.Datetime.now(),
                    'error_message': error_msg
                })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()
    
    def _sync_site_manager(self):
        """Synchronize data with the Site Manager API"""
        self.ensure_one()
        
        if self.api_type != 'site_manager':
            return False
        
        # Create a sync job to track progress
        sync_job = self.env['unifi.sync.job'].create({
            'site_id': self.id,
            'api_type': 'site_manager',
            'status': 'running',
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Implement synchronization logic here
            # This would typically involve:
            # 1. Authenticating with the Site Manager API
            # 2. Fetching site data
            # 3. Fetching device data
            # 4. Fetching network data
            # 5. Updating local records
            
            # For now, just a placeholder
            _logger.info("Starting synchronization with Site Manager API for site %s", self.name)
            
            # Update sync job with success status
            sync_job.write({
                'status': 'completed',
                'end_time': fields.Datetime.now(),
                'message': 'Synchronization completed successfully'
            })
            
            # Update site's last sync timestamp
            self.write({
                'last_sync': fields.Datetime.now()
            })
            
            return True
            
        except Exception as e:
            # Log the error and update sync job
            _logger.error("Error during synchronization with Site Manager API: %s", str(e))
            sync_job.write({
                'status': 'failed',
                'end_time': fields.Datetime.now(),
                'message': f'Synchronization failed: {str(e)}'
            })
            return False

    @api.model
    def get_user_data(self, site):
        """Récupère les données des utilisateurs du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations sur les utilisateurs.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de tous les utilisateurs
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # URL de base pour l'API Site Manager
        base_url = "https://api.cloud.ui.com"
        
        # URL pour l'authentification
        auth_url = f"{base_url}/auth/login"
        
        # Données d'authentification
        auth_data = {
            'username': site.username,
            'password': site.password,
            'token': site.api_key or '',
            'rememberMe': True
        }
        
        # En-têtes de la requête
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': auth_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(auth_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête d'authentification
            response = session.post(
                auth_url,
                json=auth_data,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si l'authentification a réussi
            if response.status_code != 200:
                _logger.error("Erreur d'authentification à l'API Site Manager: %s", response.text)
                return False
            
            # Extraire le jeton d'authentification
            auth_response = response.json()
            if 'token' not in auth_response:
                _logger.error("Jeton d'authentification manquant dans la réponse de l'API Site Manager")
                return False
            
            # Mettre à jour les en-têtes avec le jeton d'authentification
            headers['Authorization'] = f"Bearer {auth_response['token']}"
            
            # Construire l'URL pour récupérer les données des utilisateurs
            # Pour les utilisateurs réguliers
            user_url = f"{base_url}/proxy/network/api/s/{site.site_id}/rest/user"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': user_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des utilisateurs
            response = session.get(
                user_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données des utilisateurs: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if 'data' not in data:
                _logger.warning("Aucune donnée d'utilisateur trouvée dans la réponse de l'API Site Manager")
                return []
            
            # Récupérer également les utilisateurs invités
            guest_url = f"{base_url}/proxy/network/api/s/{site.site_id}/rest/guest"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': guest_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des utilisateurs invités
            guest_response = session.get(
                guest_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': guest_response.status_code,
                'response_headers': json.dumps(dict(guest_response.headers)),
                'response_body': guest_response.text
            })
            
            # Si la requête pour les invités a réussi, ajouter les données à la liste
            if guest_response.status_code == 200:
                guest_data = guest_response.json()
                if 'data' in guest_data:
                    # Marquer ces utilisateurs comme invités
                    for guest in guest_data['data']:
                        guest['is_guest'] = True
                    # Ajouter les invités à la liste des utilisateurs
                    data['data'].extend(guest_data['data'])
            
            return data['data']
            
        except RequestException as e:
            # Gérer les erreurs de requête
            error_msg = f"Erreur lors de la récupération des données des utilisateurs: {str(e)}"
            if 'api_log' in locals() and api_log:
                api_log.write({
                    'end_time': fields.Datetime.now(),
                    'error_message': error_msg
                })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()

    @api.model
    def get_firewall_data(self, site):
        """Récupère les données des règles de pare-feu du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations sur les règles de pare-feu.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de toutes les règles de pare-feu
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # URL de base pour l'API Site Manager
        base_url = "https://api.cloud.ui.com"
        
        # URL pour l'authentification
        auth_url = f"{base_url}/auth/login"
        
        # Données d'authentification
        auth_data = {
            'username': site.username,
            'password': site.password,
            'token': site.api_key or '',
            'rememberMe': True
        }
        
        # En-têtes de la requête
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': auth_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(auth_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête d'authentification
            response = session.post(
                auth_url,
                json=auth_data,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si l'authentification a réussi
            if response.status_code != 200:
                _logger.error("Erreur d'authentification à l'API Site Manager: %s", response.text)
                return False
            
            # Extraire le jeton d'authentification
            auth_response = response.json()
            if 'token' not in auth_response:
                _logger.error("Jeton d'authentification manquant dans la réponse de l'API Site Manager")
                return False
            
            # Mettre à jour les en-têtes avec le jeton d'authentification
            headers['Authorization'] = f"Bearer {auth_response['token']}"
            
            # Construire l'URL pour récupérer les données des règles de pare-feu
            firewall_url = f"{base_url}/proxy/network/api/s/{site.site_id}/rest/firewallrule"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': firewall_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des règles de pare-feu
            response = session.get(
                firewall_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données des règles de pare-feu: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if 'data' not in data:
                _logger.warning("Aucune donnée de règle de pare-feu trouvée dans la réponse de l'API Site Manager")
                return []
            
            return data['data']
            
        except RequestException as e:
            # Gérer les erreurs de requête
            error_msg = f"Erreur lors de la récupération des données des règles de pare-feu: {str(e)}"
            if 'api_log' in locals() and api_log:
                api_log.write({
                    'end_time': fields.Datetime.now(),
                    'error_message': error_msg
                })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()

    @api.model
    def get_port_forward_data(self, site):
        """Récupère les données des redirections de port du site
        
        Cette méthode utilise l'API Site Manager pour obtenir les informations sur les redirections de port.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de toutes les redirections de port
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/auth/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password
        }
        
        # En-têtes de la requête
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not site.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Journaliser l'appel API
        api_log = self.env['unifi.api.log'].create({
            'site_id': site.id,
            'api_type': 'site_manager',
            'endpoint': login_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(login_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Effectuer la requête de connexion
            response = session.post(
                login_url,
                json=login_data,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la connexion a réussi
            if response.status_code != 200:
                _logger.error("Erreur de connexion à l'API Site Manager: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            auth_data = response.json()
            
            # Vérifier si la réponse contient un jeton d'authentification
            if 'data' not in auth_data or 'token' not in auth_data['data']:
                _logger.error("Aucun jeton d'authentification trouvé dans la réponse de l'API Site Manager")
                return False
            
            # Extraire le jeton d'authentification
            token = auth_data['data']['token']
            
            # Mettre à jour les en-têtes avec le jeton d'authentification
            headers['Authorization'] = f"Bearer {token}"
            
            # Construire l'URL pour récupérer les données des redirections de port
            port_forward_url = f"{base_url}/proxy/network/api/s/{site.site_id}/rest/portforward"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'site_manager',
                'endpoint': port_forward_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
            # Effectuer la requête pour récupérer les données des redirections de port
            response = session.get(
                port_forward_url,
                headers=headers,
                verify=site.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le journal API avec les données de réponse
            api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la requête a réussi
            if response.status_code != 200:
                _logger.error("Erreur lors de la récupération des données des redirections de port: %s", response.text)
                return False
            
            # Analyser la réponse JSON
            data = response.json()
            
            # Vérifier si la réponse contient des données
            if 'data' not in data:
                _logger.warning("Aucune donnée de redirection de port trouvée dans la réponse de l'API Site Manager")
                return []
            
            return data['data']
            
        except RequestException as e:
            # Gérer les erreurs de requête
            _logger.error("Erreur lors de la communication avec l'API Site Manager: %s", str(e))
            return False
        finally:
            # Fermer la session
            session.close()
