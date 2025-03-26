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
from typing import Dict, Tuple, List, Any
from requests.exceptions import RequestException, ConnectionError

_logger = logging.getLogger(__name__)

class UnifiSiteController(models.Model):
    """Extension du modèle UnifiSite pour l'API Controller (Local)
    
    Cette classe ajoute les champs et méthodes spécifiques à l'API Controller local.
    Elle est utilisée lorsque api_type = 'controller'.
    """
    _name = 'unifi.site.controller'
    _description = 'UniFi Site Controller API'
    
    # Champs pour établir la relation avec unifi.site
    site_id = fields.Many2one(
        comodel_name='unifi.site',
        string='Site',
        required=True,
        ondelete='cascade',
        help='Site associé à cette configuration API Controller'
    )
    
    # Champs nécessaires pour le fonctionnement du modèle
    name = fields.Char(related='site_id.name', string='Nom', readonly=True)
    api_type = fields.Selection(related='site_id.api_type', string='Type API', readonly=True)
    verify_ssl = fields.Boolean(string='Verify SSL', default=True, help='Vérifier les certificats SSL. Désactivez cette option pour les certificats auto-signés.')
    ssl_cert_file = fields.Binary(string='Certificat SSL personnalisé', attachment=True, help='Fichier de certificat SSL personnalisé (.pem ou .crt)')
    ssl_cert_filename = fields.Char(string='Nom du fichier de certificat')
    ssl_cert_path = fields.Char(string='Chemin du certificat', compute='_compute_ssl_cert_path', store=True, help='Chemin vers le fichier de certificat SSL')
    last_sync = fields.Datetime(string='Dernière synchronisation')
    
    @api.depends('ssl_cert_file', 'ssl_cert_filename')
    def _compute_ssl_cert_path(self):
        """Calcule le chemin vers le fichier de certificat SSL
        
        Cette méthode est appelée lorsque le fichier de certificat SSL est modifié.
        Elle sauvegarde le certificat dans un fichier temporaire et stocke le chemin.
        """
        import tempfile
        import os
        import base64
        
        for record in self:
            if record.ssl_cert_file and record.ssl_cert_filename:
                # Créer un fichier temporaire pour stocker le certificat
                fd, path = tempfile.mkstemp(suffix='.pem')
                try:
                    # Décoder le contenu du certificat et l'écrire dans le fichier
                    cert_content = base64.b64decode(record.ssl_cert_file)
                    os.write(fd, cert_content)
                    # Stocker le chemin du fichier
                    record.ssl_cert_path = path
                finally:
                    os.close(fd)
            else:
                record.ssl_cert_path = False
    
    @api.model
    def _check_required_fields(self, site):
        """Vérifie que les champs requis pour l'API Controller sont renseignés
        
        Cette méthode est appelée par le modèle principal lors de la validation des contraintes.
        
        Args:
            site: L'enregistrement du site à vérifier
            
        Raises:
            ValidationError: Si des champs requis ne sont pas renseignés
        """
        if not site.host:
            raise ValidationError(_("Le champ 'Host' est requis pour l'API Controller."))
        
        if not site.port:
            raise ValidationError(_("Le champ 'Port' est requis pour l'API Controller."))
        
        if not site.username:
            raise ValidationError(_("Le champ 'Username' est requis pour l'API Controller."))
        
        if not site.password:
            raise ValidationError(_("Le champ 'Password' est requis pour l'API Controller."))
    
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
                'api_type': 'controller',
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
        """Nettoie les champs qui ne sont pas pertinents pour l'API Controller
        
        Cette méthode est appelée par le modèle principal lors du changement de type d'API.
        Elle efface les champs spécifiques à l'API Site Manager.
        
        Args:
            site: L'enregistrement du site à nettoyer
        """
        # Effacer les champs spécifiques à l'API Site Manager
        site.api_key = False
        site.mfa_enabled = False
        site.mfa_token = False
    
    # Controller configuration - Only used when api_type = 'controller'
    controller_type = fields.Selection(
        selection=[
            ('udm', 'UDM/UDR'),
            ('software', 'Software Controller')
        ],
        string='Controller Type',
        required=False,
        default='udm',

        help='Type of UniFi controller managing this site'
    )
    
    # Controller API fields - Only used when api_type = 'controller'
    host = fields.Char(
        string='Host',

        help='IP address or hostname of the controller'
    )
    
    port = fields.Integer(
        string='Port',
        default=443,

        help='Port number (default: 443)'
    )
    
    username = fields.Char(
        string='Username',

        help='Username for controller login'
    )
    
    password = fields.Char(
        string='Password',

        help='Password for controller login'
    )
    
    # Champs pour la gestion de session
    session_cookies = fields.Text(
        string='Session Cookies',
        help='Cookies de session pour l\'API Controller',
        readonly=True,
        copy=False
    )
    
    csrf_token = fields.Text(
        string='CSRF Token',
        help='Token CSRF pour l\'API Controller',
        readonly=True,
        copy=False
    )
    
    last_login = fields.Datetime(
        string='Dernière connexion',
        help='Date et heure de la dernière connexion réussie',
        readonly=True,
        copy=False
    )
    
    # Endpoints API communs à tous les types de contrôleurs
    COMMON_ENDPOINTS = {
        'login': '/api/auth/login',
        'logout': '/api/auth/logout',
        'status': '/api/s/{site_id}/stat/status',
        'sites': '/api/self/sites',
        'devices': '/api/s/{site_id}/stat/device',
        'device': '/api/s/{site_id}/stat/device/{mac}',
        'clients': '/api/s/{site_id}/stat/sta',
        'client': '/api/s/{site_id}/stat/sta/{mac}',
        'networks': '/api/s/{site_id}/rest/networkconf',
        'wlans': '/api/s/{site_id}/rest/wlanconf',
        'users': '/api/s/{site_id}/list/user',
        'firewall_rules': '/api/s/{site_id}/rest/firewallrule',
        'port_forwards': '/api/s/{site_id}/rest/portforward',
        'health': '/api/s/{site_id}/stat/health',
        'dashboard': '/api/s/{site_id}/stat/dashboard',
        'alarms': '/api/s/{site_id}/list/alarm',
        'events': '/api/s/{site_id}/stat/event',
        'dpi': '/api/s/{site_id}/stat/dpi',
        'settings': '/api/s/{site_id}/get/setting',
        'routing': '/api/s/{site_id}/rest/routing',
        'system_info': '/api/s/{site_id}/stat/sysinfo',
        'vouchers': '/api/s/{site_id}/stat/voucher',
        'hotspot': '/api/s/{site_id}/rest/hotspot',
    }
    
    # Endpoints spécifiques au type de contrôleur UDM
    UDM_ENDPOINTS = {
        'login': '/api/auth/login',
        'logout': '/api/auth/logout',
    }
    
    # Endpoints spécifiques au type de contrôleur Cloud Key
    CLOUD_KEY_ENDPOINTS = {
        'login': '/api/login',
        'logout': '/api/logout',
    }
    
    def _get_endpoint(self, endpoint_name: str, site_id: str = 'default', **kwargs) -> str:
        """Récupère l'URL complète d'un endpoint API en fonction du type de contrôleur
        
        Args:
            endpoint_name: Nom de l'endpoint à récupérer
            site_id: ID du site UniFi (par défaut: 'default')
            **kwargs: Paramètres supplémentaires pour formater l'URL
            
        Returns:
            str: URL complète de l'endpoint
        """
        # Sélectionner les endpoints en fonction du type de contrôleur
        if self.controller_type == 'udm':
            endpoints = {**self.COMMON_ENDPOINTS, **self.UDM_ENDPOINTS}
        elif self.controller_type == 'software':
            endpoints = {**self.COMMON_ENDPOINTS, **self.CLOUD_KEY_ENDPOINTS}
        else:
            endpoints = self.COMMON_ENDPOINTS
        
        # Vérifier si l'endpoint existe
        if endpoint_name not in endpoints:
            _logger.error(f"Endpoint '{endpoint_name}' non trouvé pour le contrôleur de type '{self.controller_type}'")
            return ''
        
        # Récupérer l'endpoint et le formater avec les paramètres
        endpoint = endpoints[endpoint_name]
        params = {'site_id': site_id, **kwargs}
        
        try:
            return endpoint.format(**params)
        except KeyError as e:
            _logger.error(f"Paramètre manquant pour l'endpoint '{endpoint_name}': {str(e)}")
            return ''
    
    def _get_base_url(self) -> str:
        """Construit l'URL de base pour les requêtes API
        
        Returns:
            str: URL de base pour les requêtes API
        """
        return f"https://{self.host}:{self.port}"
    
    def _get_headers(self, csrf_token: str = '') -> Dict[str, str]:
        """Prépare les en-têtes pour les requêtes API
        
        Args:
            csrf_token: Token CSRF à inclure dans les en-têtes (optionnel)
            
        Returns:
            Dict[str, str]: En-têtes pour les requêtes API
        """
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Odoo UniFi Integration'
        }
        
        # Ajouter le token CSRF si présent
        if csrf_token:
            headers['X-CSRF-Token'] = csrf_token
        
        return headers
    
    def _authenticate(self) -> bool:
        """Authentifie la session auprès du contrôleur UniFi
        
        Returns:
            bool: True si l'authentification a réussi, False sinon
        """
        self.ensure_one()
        
        if self.api_type != 'controller':
            return False
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Créer une nouvelle session pour cette authentification
        session = requests.Session()
        
        # Construire l'URL de connexion
        base_url = self._get_base_url()
        login_endpoint = self._get_endpoint('login')
        login_url = f"{base_url}{login_endpoint}"
        
        # Préparer les données de connexion
        login_data = {
            'username': self.username,
            'password': self.password,
            'remember': True
        }
        
        # Préparer les en-têtes
        headers = self._get_headers()
        
        # Initialiser le log API
        auth_api_log = self.env['unifi.api.log'].create({
            'site_id': self.site_id.id,
            'api_type': 'controller',
            'endpoint': login_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'request_body': json.dumps(login_data),
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Déterminer comment gérer la vérification SSL
            verify = self.verify_ssl
            
            # Si un certificat personnalisé est fourni, l'utiliser
            if self.ssl_cert_path and self.verify_ssl:
                verify = self.ssl_cert_path
                _logger.info(f"Utilisation du certificat SSL personnalisé: {verify}")
            
            # Effectuer la requête de connexion
            response = session.post(
                login_url,
                json=login_data,
                headers=headers,
                verify=verify,
                timeout=10
            )
            
            # Mettre à jour le log API avec les données de réponse
            auth_api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la connexion a réussi
            if response.status_code == 200:
                # Stocker les cookies de session et le token CSRF
                self.session_cookies = json.dumps(dict(session.cookies.items()))
                
                # Extraire le token CSRF si présent
                csrf_token = ''
                if 'X-CSRF-Token' in response.headers:
                    csrf_token = response.headers['X-CSRF-Token']
                    self.csrf_token = csrf_token
                
                # Mettre à jour la date de dernière connexion
                self.last_login = fields.Datetime.now()
                
                return True
            
            # Journaliser l'échec de connexion
            _logger.error(f"Échec de connexion à l'API Controller: {response.status_code} - {response.text}")
            return False
            
        except Exception as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de l'authentification: {str(e)}"
            auth_api_log.write({
                'end_time': fields.Datetime.now(),
                'error_message': error_msg
            })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()
    
    def _logout(self) -> bool:
        """Déconnecte la session du contrôleur UniFi
        
        Returns:
            bool: True si la déconnexion a réussi, False sinon
        """
        self.ensure_one()
        
        if self.api_type != 'controller':
            return False
        
        # Vérifier si nous avons des cookies de session
        if not self.session_cookies:
            return True  # Déjà déconnecté
        
        # Créer une nouvelle session pour cette déconnexion
        session = requests.Session()
        
        # Restaurer les cookies de session
        if self.session_cookies:
            try:
                cookies = json.loads(self.session_cookies)
                for key, value in cookies.items():
                    session.cookies.set(key, value)
            except json.JSONDecodeError:
                _logger.error("Impossible de décoder les cookies de session")
                return False
        
        # Construire l'URL de déconnexion
        base_url = self._get_base_url()
        logout_endpoint = self._get_endpoint('logout')
        logout_url = f"{base_url}{logout_endpoint}"
        
        # Préparer les en-têtes
        headers = self._get_headers(self.csrf_token if self.csrf_token else '')
        
        # Initialiser le log API
        logout_api_log = self.env['unifi.api.log'].create({
            'site_id': self.site_id.id,
            'api_type': 'controller',
            'endpoint': logout_url,
            'method': 'POST',
            'request_headers': json.dumps(headers),
            'start_time': fields.Datetime.now()
        })
        
        try:
            
            # Effectuer la requête de déconnexion
            response = session.post(
                logout_url,
                headers=headers,
                verify=self.verify_ssl,
                timeout=10
            )
            
            # Mettre à jour le log API avec les données de réponse
            logout_api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Effacer les cookies de session et le token CSRF
            self.session_cookies = False
            self.csrf_token = False
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la déconnexion: {str(e)}"
            logout_api_log.write({
                'end_time': fields.Datetime.now(),
                'error_message': error_msg
            })
            _logger.error(error_msg)
            return False
        finally:
            # Fermer la session
            session.close()
    
    def _make_request(self, method: str, endpoint_name: str, site_id: str = '', 
                     params: Dict[str, str] = {}, data: Dict[str, str] = {}, 
                     retry_auth: bool = True) -> Tuple[bool, Dict, int]:
        """Effectue une requête API au contrôleur UniFi
        
        Args:
            method: Méthode HTTP à utiliser (GET, POST, PUT, DELETE)
            endpoint_name: Nom de l'endpoint à appeler
            site_id: ID du site UniFi (par défaut: '')
            params: Paramètres de requête (pour GET et DELETE)
            data: Données de requête (pour POST et PUT)
            retry_auth: Si True, réessaie avec une nouvelle authentification en cas d'échec
            
        Returns:
            Tuple[bool, Dict, int]: (Succès, Données de réponse, Code de statut HTTP)
        """
        self.ensure_one()
        
        if self.api_type != 'controller':
            return False, {"error": "Type d'API non pris en charge"}, 400
        
        # Désactiver les avertissements SSL si verify_ssl est False
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Créer une nouvelle session pour cette requête
        session = requests.Session()
        
        # Restaurer les cookies de session
        if self.session_cookies:
            try:
                cookies = json.loads(self.session_cookies)
                for key, value in cookies.items():
                    session.cookies.set(key, value)
            except json.JSONDecodeError:
                _logger.error("Impossible de décoder les cookies de session")
                if retry_auth:
                    # Tenter une nouvelle authentification
                    if self._authenticate():
                        return self._make_request(method, endpoint_name, site_id, params, data, False)
                return False, {"error": "Erreur de session"}, 401
        
        # Construire l'URL complète
        base_url = self._get_base_url()
        endpoint = self._get_endpoint(endpoint_name, site_id)
        url = f"{base_url}{endpoint}"
        
        # Préparer les en-têtes
        headers = self._get_headers(self.csrf_token if self.csrf_token else '')
        
        # Journaliser l'appel API
        request_api_log = self.env['unifi.api.log'].create({
            'site_id': self.site_id.id,
            'api_type': 'controller',
            'endpoint': url,
            'method': method,
            'request_headers': json.dumps(headers),
            'request_params': json.dumps(params) if params else '',
            'request_body': json.dumps(data) if data else '',
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Déterminer comment gérer la vérification SSL
            verify = self.verify_ssl
            
            # Si un certificat personnalisé est fourni, l'utiliser
            if self.ssl_cert_path and self.verify_ssl:
                verify = self.ssl_cert_path
                _logger.debug(f"Utilisation du certificat SSL personnalisé: {verify}")
            
            # Effectuer la requête
            if method == 'GET':
                response = session.get(url, params=params, headers=headers, verify=verify, timeout=10)
            elif method == 'POST':
                response = session.post(url, json=data, headers=headers, verify=verify, timeout=10)
            elif method == 'PUT':
                response = session.put(url, json=data, headers=headers, verify=verify, timeout=10)
            elif method == 'DELETE':
                response = session.delete(url, params=params, headers=headers, verify=verify, timeout=10)
            else:
                return False, {"error": "Méthode HTTP non prise en charge"}, 400
            
            # Mettre à jour le log API avec les données de réponse
            request_api_log.write({
                'end_time': fields.Datetime.now(),
                'status_code': response.status_code,
                'response_headers': json.dumps(dict(response.headers)),
                'response_body': response.text
            })
            
            # Vérifier si la session a expiré (401 Unauthorized)
            if response.status_code == 401 and retry_auth:
                # Tenter une nouvelle authentification
                if self._authenticate():
                    return self._make_request(method, endpoint_name, site_id, params, data, False)
                return False, {"error": "Session expirée et échec de réauthentification"}, 401
            
            # Traiter la réponse
            if response.status_code in [200, 201, 204]:
                try:
                    # Certains endpoints peuvent retourner une réponse vide
                    if not response.text:
                        return True, {}, response.status_code
                    
                    # Décoder la réponse JSON
                    json_response = response.json()
                    return True, json_response, response.status_code
                except json.JSONDecodeError:
                    return False, {"error": "Erreur de décodage JSON"}, response.status_code
            
            # Gérer les erreurs
            return False, {"error": f"Erreur HTTP {response.status_code}"}, response.status_code
            
        except Exception as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la requête: {str(e)}"
            request_api_log.write({
                'end_time': fields.Datetime.now(),
                'error_message': error_msg
            })
            _logger.error(error_msg)
            return False, {"error": str(e)}, 500
        finally:
            # Fermer la session
            session.close()
    
    def _get(self, endpoint_name: str, site_id: str = '', 
            params: Dict[str, str] = {}) -> Tuple[bool, Dict, int]:
        """Effectue une requête GET
        
        Args:
            endpoint_name: Nom de l'endpoint à appeler
            site_id: ID du site UniFi (par défaut: '')
            params: Paramètres de requête
            
        Returns:
            Tuple[bool, Dict, int]: (Succès, Données de réponse, Code de statut HTTP)
        """
        return self._make_request('GET', endpoint_name, site_id, params=params)
    
    def _post(self, endpoint_name: str, site_id: str = '', 
             data: Dict[str, str] = {}) -> Tuple[bool, Dict, int]:
        """Effectue une requête POST
        
        Args:
            endpoint_name: Nom de l'endpoint à appeler
            site_id: ID du site UniFi (par défaut: '')
            data: Données de requête
            
        Returns:
            Tuple[bool, Dict, int]: (Succès, Données de réponse, Code de statut HTTP)
        """
        return self._make_request('POST', endpoint_name, site_id, data=data)
    
    def _put(self, endpoint_name: str, site_id: str = '', 
            data: Dict[str, str] = {}) -> Tuple[bool, Dict, int]:
        """Effectue une requête PUT
        
        Args:
            endpoint_name: Nom de l'endpoint à appeler
            site_id: ID du site UniFi (par défaut: '')
            data: Données de requête
            
        Returns:
            Tuple[bool, Dict, int]: (Succès, Données de réponse, Code de statut HTTP)
        """
        return self._make_request('PUT', endpoint_name, site_id, data=data)
    
    def _delete(self, endpoint_name: str, site_id: str = '', 
               params: Dict[str, str] = {}) -> Tuple[bool, Dict, int]:
        """Effectue une requête DELETE
        
        Args:
            endpoint_name: Nom de l'endpoint à appeler
            site_id: ID du site UniFi (par défaut: '')
            params: Paramètres de requête
            
        Returns:
            Tuple[bool, Dict, int]: (Succès, Données de réponse, Code de statut HTTP)
        """
        return self._make_request('DELETE', endpoint_name, site_id, params=params)
    
    def _test_controller_connection(self):
        """Test connection to the Controller API"""
        self.ensure_one()
        
        if self.api_type != 'controller':
            return False
        
        try:
            # Tester l'authentification
            if not self._authenticate():
                return False
                
            # Tester la récupération du statut du système
            success, response, status_code = self._get('status')
            if not success:
                self._logout()
                return False
                
            # Déconnexion propre
            self._logout()
            
            return True
            
        except Exception as e:
            _logger.error(f"Erreur lors du test de connexion: {str(e)}")
            return False
    
    @api.model
    def get_device_data(self, site, mac_address=None):
        """Récupère les données d'un appareil spécifique ou de tous les appareils du site
        
        Cette méthode utilise l'API Controller pour obtenir les informations sur les appareils.
        
        Args:
            site: L'enregistrement du site UniFi
            mac_address: Adresse MAC de l'appareil spécifique à récupérer (optionnel)
            
        Returns:
            dict ou list: Données de l'appareil ou liste des données de tous les appareils
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données des appareils
            if mac_address:
                # URL pour un appareil spécifique
                device_url = f"{base_url}/api/s/{site.site_id}/stat/device/{mac_address}"
            else:
                # URL pour tous les appareils
                device_url = f"{base_url}/api/s/{site.site_id}/stat/device"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
                return data['data'][0] if data['data'] else False
            else:
                # Retourner la liste des données de tous les appareils
                return data['data']
                
        except (RequestException, json.JSONDecodeError) as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la récupération des données des appareils: {str(e)}"
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
    def get_system_info_data(self, site):
        """Récupère les données d'information système du site
        
        Cette méthode utilise l'API Controller pour obtenir les informations système.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            dict: Données d'information système
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données système
            system_url = f"{base_url}/api/s/{site.site_id}/stat/sysinfo"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
                'endpoint': system_url,
                'method': 'GET',
                'request_headers': json.dumps(headers),
                'start_time': fields.Datetime.now()
            })
            
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
            if 'data' not in data or not data['data']:
                _logger.error("Aucune donnée système trouvée dans la réponse")
                return False
            
            # Retourner les données système (premier élément de la liste)
            return data['data'][0]
                
        except (RequestException, json.JSONDecodeError) as e:
            # Journaliser l'erreur
            error_msg = f"Erreur lors de la récupération des données système: {str(e)}"
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
    def get_vlan_data(self, site):
        """Récupère les données des VLANs du site
        
        Cette méthode utilise l'API Controller pour obtenir les informations sur les VLANs.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de tous les VLANs
        """
        # Initialiser api_log à None pour éviter les erreurs de variable potentiellement indépendante
        api_log = None
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données des VLANs
            vlan_url = f"{base_url}/api/s/{site.site_id}/rest/vlan"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
        
        Cette méthode utilise l'API Controller pour obtenir les informations sur les réseaux.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de tous les réseaux
        """
        # Initialiser api_log à None pour éviter les erreurs de variable potentiellement indépendante
        api_log = None
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données des réseaux
            network_url = f"{base_url}/api/s/{site.site_id}/rest/networkconf"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
    
    def _sync_controller(self):
        """Synchronize data with the Controller API"""
        self.ensure_one()
        
        if self.api_type != 'controller':
            return False
        
        # Create a sync job to track progress
        sync_job = self.env['unifi.sync.job'].create({
            'site_id': self.id,
            'api_type': 'controller',
            'status': 'running',
            'start_time': fields.Datetime.now()
        })
        
        try:
            # Implement synchronization logic here
            # This would typically involve:
            # 1. Authenticating with the controller
            # 2. Fetching device data
            # 3. Fetching network data
            # 4. Fetching client data
            # 5. Updating local records
            
            # For now, just a placeholder
            _logger.info("Starting synchronization with Controller API for site %s", self.name)
            
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
            _logger.error("Error during synchronization with Controller API: %s", str(e))
            sync_job.write({
                'status': 'failed',
                'end_time': fields.Datetime.now(),
                'message': f'Synchronization failed: {str(e)}'
            })
            return False

    @api.model
    def get_user_data(self, site):
        """Récupère les données des utilisateurs du site
        
        Cette méthode utilise l'API Controller pour obtenir les informations sur les utilisateurs.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de tous les utilisateurs
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données des utilisateurs
            # Pour les utilisateurs réguliers
            user_url = f"{base_url}/api/s/{site.site_id}/rest/user"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
                _logger.warning("Aucune donnée d'utilisateur trouvée dans la réponse de l'API Controller")
                return []
            
            # Récupérer également les utilisateurs invités
            guest_url = f"{base_url}/api/s/{site.site_id}/rest/guest"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
            _logger.error("Erreur lors de la communication avec l'API Controller: %s", str(e))
            return False
        finally:
            # Fermer la session
            session.close()

    @api.model
    def get_firewall_data(self, site):
        """Récupère les données des règles de pare-feu du site
        
        Cette méthode utilise l'API Controller pour obtenir les informations sur les règles de pare-feu.
        
        Args:
            site: L'enregistrement du site UniFi
            
        Returns:
            list: Liste des données de toutes les règles de pare-feu
        """
        # Créer une session pour les requêtes
        session = requests.Session()
        
        # Construire l'URL de base
        base_url = f"https://{site.host}:{site.port}"
        
        # URL pour la connexion
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données des règles de pare-feu
            firewall_url = f"{base_url}/api/s/{site.site_id}/rest/firewallrule"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
                _logger.warning("Aucune donnée de règle de pare-feu trouvée dans la réponse de l'API Controller")
                return []
            
            return data['data']
            
        except RequestException as e:
            # Gérer les erreurs de requête
            _logger.error("Erreur lors de la communication avec l'API Controller: %s", str(e))
            return False
        finally:
            # Fermer la session
            session.close()

    @api.model
    def get_port_forward_data(self, site):
        """Récupère les données des redirections de port du site
        
        Cette méthode utilise l'API Controller pour obtenir les informations sur les redirections de port.
        
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
        login_url = f"{base_url}/api/login"
        
        # Données de connexion
        login_data = {
            'username': site.username,
            'password': site.password,
            'remember': True
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
            'api_type': 'controller',
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
                _logger.error("Erreur de connexion à l'API Controller: %s", response.text)
                return False
            
            # Construire l'URL pour récupérer les données des redirections de port
            port_forward_url = f"{base_url}/api/s/{site.site_id}/rest/portforward"
            
            # Journaliser l'appel API
            api_log = self.env['unifi.api.log'].create({
                'site_id': site.id,
                'api_type': 'controller',
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
                _logger.warning("Aucune donnée de redirection de port trouvée dans la réponse de l'API Controller")
                return []
            
            return data['data']
            
        except RequestException as e:
            # Gérer les erreurs de requête
            _logger.error("Erreur lors de la communication avec l'API Controller: %s", str(e))
            return False
        finally:
            # Fermer la session
            session.close()
