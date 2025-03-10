# -*- coding: utf-8 -*-

# pylint: disable=import-error
from odoo import http, _  # IDE peut signaler une erreur, mais fonctionne dans l'environnement Odoo
from odoo.http import request  # IDE peut signaler une erreur, mais fonctionne dans l'environnement Odoo
# pylint: enable=import-error
import logging
import json  # Nécessaire pour parser les réponses API et utilisé dans les méthodes de traitement
import requests
from requests.exceptions import RequestException, ConnectionError
from urllib3.exceptions import InsecureRequestWarning
from datetime import datetime

# Supprimer les avertissements pour les connexions non sécurisées
try:
    # Pour les versions plus récentes de requests
    import urllib3
    urllib3.disable_warnings(category=InsecureRequestWarning)
except ImportError:
    # Pour les versions plus anciennes de requests
    try:
        # Désactiver l'avertissement de sécurité de pylint pour cette ligne spécifique
        # pylint: disable=no-member
        requests.packages.urllib3.disable_warnings()
        # pylint: enable=no-member
    except AttributeError:
        # Si ni l'un ni l'autre ne fonctionne, nous ignorons silencieusement
        pass

_logger = logging.getLogger(__name__)

class UdmProController(http.Controller):
    """Contrôleur pour les fonctionnalités liées à UDM Pro dans Odoo"""
    
    @http.route('/udm_pro/advanced_options', type='http', auth='user', website=True)
    def advanced_options_form(self):
        """Affiche le formulaire des options avancées pour l'API UDM Pro"""
        return request.render('udm_pro_docs.advanced_options_form', {
            'default_site': 'default',
            'fixed_only': True,
            'lowercase_hostnames': True,
        })
    
    @http.route('/udm_pro/restart_device', type='http', auth='user', website=True)
    def restart_device_form(self):
        """Affiche le formulaire pour redémarrer un appareil UDM Pro"""
        if not request.env.user.has_group('udm_pro_docs.group_udm_pro_manager'):
            return request.render('udm_pro_docs.access_denied', {
                'error_message': _("You don't have permission to restart devices.")
            })
            
        # Récupérer les configurations UDM Pro enregistrées pour le formulaire
        configs = request.env['udm.configuration'].sudo().search([])
        return request.render('udm_pro_docs.restart_device_form', {
            'configs': configs
        })
        
    @http.route('/udm_pro/restart_device', type='http', auth='user', website=True, methods=['POST'])
    def restart_device(self, **post):
        """Traite la demande de redémarrage d'un appareil UDM Pro"""
        if not request.env.user.has_group('udm_pro_docs.group_udm_pro_manager'):
            return request.render('udm_pro_docs.access_denied', {
                'error_message': _("You don't have permission to restart devices.")
            })
        
        config_id = int(post.get('config_id'))
        mac_address = post.get('mac_address')
        
        if not mac_address:
            return request.render('udm_pro_docs.restart_device_form', {
                'error_message': _("Please provide the MAC address of the device to restart."),
                'configs': request.env['udm.configuration'].sudo().search([])
            })
        
        try:
            # Récupérer la configuration
            config = request.env['udm.configuration'].sudo().browse(config_id)
            if not config.exists():
                raise ValueError(_("Configuration not found"))
                
            # Initialiser le client UDM Pro
            client = UdmProClient(
                host=config.host,
                username=config.username,
                password=config.password,
                port=config.port or 443
            )
            
            # Authentifier le client
            if not client.login():
                return request.render('udm_pro_docs.restart_device_form', {
                    'error_message': _("Authentication failed. Please check the configuration credentials."),
                    'configs': request.env['udm.configuration'].sudo().search([])
                })
            
            # Redémarrer l'appareil
            success = client.restart_device(mac_address)
            if not success:
                return request.render('udm_pro_docs.restart_device_form', {
                    'error_message': _("Failed to restart the device. Please check logs for details."),
                    'configs': request.env['udm.configuration'].sudo().search([])
                })
                
            return request.render('udm_pro_docs.restart_success', {
                'mac_address': mac_address
            })
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error during UDM Pro device restart: %s", str(e))
            return request.render('udm_pro_docs.restart_device_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([])
            })
        except Exception as e:  # pylint: disable=broad-except
            _logger.exception("Unexpected error during UDM Pro device restart")
            return request.render('udm_pro_docs.restart_device_form', {
                'error_message': _("An unexpected error occurred: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([])
            })
    
    @http.route('/udm_pro/generate_hosts', type='http', auth='user', website=True)
    def generate_hosts_form(self):
        """Affiche le formulaire pour générer un fichier hosts depuis UDM Pro"""
        # Récupérer les configurations UDM Pro enregistrées pour le formulaire
        configs = request.env['udm.configuration'].sudo().search([])
        return request.render('udm_pro_docs.generate_hosts_form', {
            'configs': configs,
            'fixed_only': True,
            'lowercase_hostnames': True
        })
        
    @http.route('/udm_pro/generate_hosts', type='http', auth='user', website=True, methods=['POST'])
    def generate_hosts(self, **post):
        """Génère un fichier hosts à partir des clients réseau UDM Pro"""
        config_id = int(post.get('config_id'))
        fixed_only = post.get('fixed_only') == 'on'
        lowercase_hostnames = post.get('lowercase_hostnames') == 'on'
        
        try:
            # Récupérer la configuration
            config = request.env['udm.configuration'].sudo().browse(config_id)
            if not config.exists():
                raise ValueError(_("Configuration not found"))
                
            # Initialiser le client UDM Pro avec les options avancées
            client = UdmProClient(
                host=config.host,
                username=config.username,
                password=config.password,
                port=config.port or 443,
                fixed_only=fixed_only,
                lowercase_hostnames=lowercase_hostnames
            )
            
            # Authentifier le client
            if not client.login():
                return request.render('udm_pro_docs.generate_hosts_form', {
                    'error_message': _("Authentication failed. Please check the configuration credentials."),
                    'configs': request.env['udm.configuration'].sudo().search([]),
                    'fixed_only': fixed_only,
                    'lowercase_hostnames': lowercase_hostnames
                })
            
            # Générer le fichier hosts
            hosts_content = client.generate_hosts_file()
            
            # Retourner le contenu sous forme de fichier à télécharger
            response = request.make_response(hosts_content)
            response.headers['Content-Type'] = 'text/plain'
            response.headers['Content-Disposition'] = 'attachment; filename=udm_hosts.txt'
            return response
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error during UDM Pro hosts file generation: %s", str(e))
            return request.render('udm_pro_docs.generate_hosts_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except Exception as e:  # pylint: disable=broad-except
            _logger.exception("Unexpected error during UDM Pro hosts file generation")
            return request.render('udm_pro_docs.generate_hosts_form', {
                'error_message': _("An unexpected error occurred: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
    
    @http.route('/udm_pro/network_clients', type='http', auth='user', website=True)
    def network_clients_form(self):
        """Affiche le formulaire pour consulter les clients réseau UDM Pro"""
        # Récupérer les configurations UDM Pro enregistrées pour le formulaire
        configs = request.env['udm.configuration'].sudo().search([])
        return request.render('udm_pro_docs.network_clients_form', {
            'configs': configs,
            'fixed_only': False,
            'lowercase_hostnames': True
        })
        
    @http.route('/udm_pro/network_clients', type='http', auth='user', website=True, methods=['POST'])
    def get_network_clients(self, **post):
        """Récupère et affiche la liste des clients réseau UDM Pro"""
        config_id = int(post.get('config_id'))
        fixed_only = post.get('fixed_only') == 'on'
        lowercase_hostnames = post.get('lowercase_hostnames') == 'on'
        
        try:
            # Récupérer la configuration
            config = request.env['udm.configuration'].sudo().browse(config_id)
            if not config.exists():
                raise ValueError(_("Configuration not found"))
                
            # Initialiser le client UDM Pro avec les options avancées
            client = UdmProClient(
                host=config.host,
                username=config.username,
                password=config.password,
                port=config.port or 443,
                fixed_only=fixed_only,
                lowercase_hostnames=lowercase_hostnames
            )
            
            # Authentifier le client
            if not client.login():
                return request.render('udm_pro_docs.network_clients_form', {
                    'error_message': _("Authentication failed. Please check the configuration credentials."),
                    'configs': request.env['udm.configuration'].sudo().search([]),
                    'fixed_only': fixed_only,
                    'lowercase_hostnames': lowercase_hostnames
                })
            
            # Récupérer les clients réseau
            network_clients = client.get_network_clients()
            
            return request.render('udm_pro_docs.network_clients_result', {
                'clients': network_clients,
                'config': config
            })
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error retrieving UDM Pro network clients: %s", str(e))
            return request.render('udm_pro_docs.network_clients_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except ValueError as e:
            _logger.error("Value error retrieving UDM Pro network clients: %s", str(e))
            return request.render('udm_pro_docs.network_clients_form', {
                'error_message': _("Configuration error: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except (AttributeError, KeyError) as e:
            _logger.error("Data format error retrieving UDM Pro network clients: %s", str(e))
            return request.render('udm_pro_docs.network_clients_form', {
                'error_message': _("Data error: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
        except Exception as e:  # pylint: disable=broad-except
            # Conserver cette exception générique comme dernier recours, avec un avertissement explicite pour pylint
            _logger.exception("Unexpected error retrieving UDM Pro network clients")
            return request.render('udm_pro_docs.network_clients_form', {
                'error_message': _("An unexpected error occurred: %s") % str(e),
                'configs': request.env['udm.configuration'].sudo().search([]),
                'fixed_only': fixed_only,
                'lowercase_hostnames': lowercase_hostnames
            })
    
    @http.route('/udm_pro/import_config', type='http', auth='user', website=True)
    def import_config_form(self):
        """Affiche le formulaire d'importation de configuration UDM Pro"""
        return request.render('udm_pro_docs.import_config_form', {})
    
    @http.route('/udm_pro/import_config', type='http', auth='user', website=True, methods=['POST'])
    def import_config(self, **post):
        """Importe une configuration UDM Pro depuis l'appareil"""
        if not request.env.user.has_group('udm_pro_docs.group_udm_pro_manager'):
            return request.render('udm_pro_docs.access_denied', {
                'error_message': _("You don't have permission to import configurations.")
            })
        
        host = post.get('host')
        username = post.get('username')
        password = post.get('password')
        port = int(post.get('port') or 443)
        
        if not all([host, username, password]):
            return request.render('udm_pro_docs.import_config_form', {
                'error_message': _("Please provide all required fields."),
                'host': host,
                'username': username,
                'port': port
            })
        
        try:
            # Utiliser le client API pour récupérer la configuration
            client = UdmProClient(host, username, password, port)
            if not client.login():
                return request.render('udm_pro_docs.import_config_form', {
                    'error_message': _("Authentication failed. Please check your credentials."),
                    'host': host,
                    'username': username,
                    'port': port
                })
            
            config_data = client.get_full_configuration()
            
            # Importer la configuration dans Odoo
            config_id = request.env['udm.configuration'].sudo().import_configuration(config_data)
            
            return request.redirect('/web#id=%s&model=udm.configuration&view_type=form' % config_id)
            
        except (ConnectionError, RequestException) as e:
            _logger.error("Error during UDM Pro configuration import: %s", str(e))
            return request.render('udm_pro_docs.import_config_form', {
                'error_message': _("Error connecting to UDM Pro: %s") % str(e),
                'host': host,
                'username': username,
                'port': port
            })
        except (ValueError, TypeError, AttributeError) as e:
            _logger.error("Data processing error during UDM Pro configuration import: %s", str(e))
            return request.render('udm_pro_docs.import_config_form', {
                'error_message': _("Error processing data: %s") % str(e),
                'host': host,
                'username': username,
                'port': port
            })
        except Exception as e:  # pylint: disable=broad-except
            _logger.exception("Unexpected error during UDM Pro configuration import")
            return request.render('udm_pro_docs.import_config_form', {
                'error_message': _("An unexpected error occurred. Please check server logs."),
                'host': host,
                'username': username,
                'port': port
            })


class UdmProClient:
    """Client pour interagir avec l'API UDM Pro."""
    
    # Points d'accès de l'API
    API_LOGIN_ENDPOINT = '/api/auth/login'
    API_SYSTEM_INFO_ENDPOINT = '/api/system'
    API_NETWORK_ENDPOINT = '/api/networks'
    API_DEVICES_ENDPOINT = '/api/devices'
    API_USERS_ENDPOINT = '/api/users'
    API_SETTINGS_ENDPOINT = '/api/settings'
    API_FIREWALL_ENDPOINT = '/api/firewall'
    
    # Nouveaux endpoints inspirés du client Go
    API_ACTIVE_CLIENTS_ENDPOINT = '/proxy/network/api/s/{site}/stat/sta'
    API_CONFIGURED_CLIENTS_ENDPOINT = '/proxy/network/api/s/{site}/list/user'
    API_DEVICE_RESTART_ENDPOINT = '/proxy/network/api/s/{site}/cmd/devmgr'
    
    def __init__(self, host, username, password, port=443, verify_ssl=False, site='default', fixed_only=True, lowercase_hostnames=True, debug=False):
        """
        Initialise le client API UDM Pro.
        
        Args:
            host (str): Adresse IP ou nom d'hôte de l'UDM Pro
            username (str): Nom d'utilisateur pour l'API
            password (str): Mot de passe pour l'API
            port (int): Port pour la connexion (par défaut 443)
            verify_ssl (bool): Vérifier le certificat SSL (par défaut False)
            site (str): Identifiant du site pour l'API UniFi (par défaut 'default')
            fixed_only (bool): Ne considérer que les clients avec adresse IP fixe (par défaut True)
            lowercase_hostnames (bool): Convertir les noms d'hôtes en minuscules (par défaut True)
            debug (bool): Activer le mode débogage pour les requêtes HTTP (par défaut False)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.verify_ssl = verify_ssl
        self.site = site
        self.fixed_only = fixed_only
        self.lowercase_hostnames = lowercase_hostnames
        self.debug = debug
        self.base_url = f"https://{host}:{port}"
        self.token = None
        self.csrf_token = None
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
    def _get_auth_headers(self):
        """Retourne les en-têtes d'authentification."""
        if not self.token:
            raise ValueError("Non authentifié. Appelez login() d'abord.")
            
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Ajouter le token CSRF si disponible
        if self.csrf_token:
            headers["X-Csrf-Token"] = self.csrf_token
            
        return headers
    
    def login(self):
        """
        Authentifie le client auprès de l'API UDM Pro.
        
        Returns:
            bool: True si l'authentification a réussi, False sinon
        """
        try:
            login_url = f"{self.base_url}{self.API_LOGIN_ENDPOINT}"
            payload = {
                "username": self.username,
                "password": self.password
            }
            
            _logger.debug("Tentative de connexion à %s", login_url)
            response = self.session.post(login_url, json=payload)
            response.raise_for_status()
            
            # Capture du token CSRF s'il existe
            csrf_token = response.headers.get('X-Csrf-Token')
            if csrf_token:
                self.csrf_token = csrf_token
                _logger.debug("Token CSRF capturé: %s", csrf_token)
            
            data = response.json()
            if not data.get('token'):
                _logger.error("Aucun token n'a été retourné par l'API")
                return False
                
            self.token = data['token']
            _logger.debug("Authentification réussie")
            return True
            
        except RequestException as e:
            _logger.error("Erreur d'authentification: %s", str(e))
            return False
    
    def _make_api_request(self, method, endpoint, params=None, data=None, retry=True):
        """
        Effectue une requête API.
        
        Args:
            method (str): Méthode HTTP (GET, POST, etc.)
            endpoint (str): Point d'accès API
            params (dict): Paramètres de requête
            data (dict): Données à envoyer dans le corps de la requête
            retry (bool): Réessayer en cas d'erreur d'authentification
            
        Returns:
            dict: Réponse JSON de l'API
        """
        if not self.token and retry:
            _logger.debug("Non authentifié, tentative d'authentification")
            if not self.login():
                raise ConnectionError("Impossible de s'authentifier à l'API UDM Pro")
        
        url = f"{self.base_url}{endpoint}"
        try:
            _logger.debug("Requête %s vers %s", method, url)
            headers = self._get_auth_headers()
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data
            )
            
            # Capture du token CSRF s'il existe dans la réponse
            csrf_token = response.headers.get('X-Csrf-Token')
            if csrf_token and csrf_token != self.csrf_token:
                self.csrf_token = csrf_token
                _logger.debug("Token CSRF mis à jour: %s", csrf_token)
            
            response.raise_for_status()
            return response.json()
            
        except RequestException as e:
            if response.status_code == 401 or response.status_code == 403:
                if retry:
                    _logger.debug("Token expiré, nouvelle tentative d'authentification")
                    self.token = None
                    return self._make_api_request(method, endpoint, params, data, retry=False)
            _logger.error("Erreur API (%s %s): %s", method, url, str(e))
            raise
    
    def get_system_info(self):
        """
        Récupère les informations système de l'UDM Pro.
        
        Returns:
            dict: Informations système
        """
        return self._make_api_request('GET', self.API_SYSTEM_INFO_ENDPOINT)
    
    def get_networks(self):
        """
        Récupère la configuration des réseaux.
        
        Returns:
            dict: Configuration des réseaux
        """
        return self._make_api_request('GET', self.API_NETWORK_ENDPOINT)
    
    def get_devices(self):
        """
        Récupère la liste des périphériques.
        
        Returns:
            dict: Liste des périphériques
        """
        return self._make_api_request('GET', self.API_DEVICES_ENDPOINT)
    
    def get_users(self):
        """
        Récupère la liste des utilisateurs.
        
        Returns:
            dict: Liste des utilisateurs
        """
        return self._make_api_request('GET', self.API_USERS_ENDPOINT)
    
    def get_settings(self):
        """
        Récupère les paramètres généraux.
        
        Returns:
            dict: Paramètres généraux
        """
        return self._make_api_request('GET', self.API_SETTINGS_ENDPOINT)
    
    def get_firewall_rules(self):
        """
        Récupère les règles de pare-feu.
        
        Returns:
            dict: Règles de pare-feu
        """
        return self._make_api_request('GET', self.API_FIREWALL_ENDPOINT)
    
    def get_active_clients(self):
        """
        Récupère la liste des clients actuellement connectés.
        
        Returns:
            list: Liste des clients actifs
        """
        endpoint = self.API_ACTIVE_CLIENTS_ENDPOINT.format(site=self.site)
        response = self._make_api_request('GET', endpoint)
        
        if not response or 'data' not in response:
            return []
            
        return response.get('data', [])
        
    def get_configured_clients(self):
        """
        Récupère la liste des clients configurés statiquement.
        
        Returns:
            list: Liste des clients configurés
        """
        endpoint = self.API_CONFIGURED_CLIENTS_ENDPOINT.format(site=self.site)
        response = self._make_api_request('GET', endpoint)
        
        if not response or 'data' not in response:
            return []
            
        return response.get('data', [])
        
    def restart_device(self, mac_address):
        """
        Redémarre un appareil géré par l'UDM Pro (ex: point d'accès WiFi).
        Nécessite des permissions de niveau 'admin du site'.
        
        Args:
            mac_address (str): Adresse MAC de l'appareil à redémarrer
            
        Returns:
            bool: True si l'opération a réussi, False sinon
        """
        endpoint = self.API_DEVICE_RESTART_ENDPOINT.format(site=self.site)
        payload = {
            'mac': mac_address,
            'reboot_type': 'soft',
            'cmd': 'restart'
        }
        
        try:
            response = self._make_api_request('POST', endpoint, data=payload)
            if response and response.get('meta', {}).get('rc') == 'ok':
                return True
            return False
        except Exception as e:  # pylint: disable=broad-except
            _logger.error("Erreur lors du redémarrage de l'appareil %s: %s", mac_address, str(e))
            return False
            
    def get_network_clients(self):
        """
        Récupère tous les clients réseau (actifs et/ou configurés selon les paramètres).
        
        Returns:
            list: Liste des clients réseau
        """
        clients = []
        
        # Toujours inclure les clients configurés statiquement
        configured_clients = self.get_configured_clients()
        clients.extend(configured_clients)
        
        # Inclure les clients actifs si fixed_only est False
        if not self.fixed_only:
            active_clients = self.get_active_clients()
            clients.extend(active_clients)
            
        # Traitement des noms d'hôtes si nécessaire
        if self.lowercase_hostnames:
            for client in clients:
                if client.get('hostname'):
                    client['hostname'] = client['hostname'].lower()
                if client.get('name'):
                    client['name'] = client['name'].lower()
                    
        return clients
    
    def generate_hosts_file(self):
        """
        Génère un fichier hosts à partir des clients réseau.
        
        Returns:
            str: Contenu du fichier hosts
        """
        clients = self.get_network_clients()
        hosts_content = "# UDM Pro Generated Hosts File\n"
        hosts_content += "# Generated on {}\n\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        for client in clients:
            name = client.get('name') or client.get('hostname')
            ip = client.get('fixed_ip') or client.get('ip')
            mac = client.get('mac', '')
            
            if name and ip:
                hosts_content += "{:16s} {:30s} # {}\n".format(ip, name, mac)
                
        return hosts_content
    
    def get_full_configuration(self):
        """
        Récupère la configuration complète de l'UDM Pro.
        
        Returns:
            dict: Configuration complète de l'UDM Pro
        """
        # S'authentifier d'abord
        if not self.token and not self.login():
            raise ConnectionError("Échec de l'authentification pour la récupération de la configuration complète")
        
        try:
            # Récupérer chaque partie de la configuration
            system_info = self.get_system_info()
            networks = self.get_networks()
            devices = self.get_devices()
            users = self.get_users()
            settings = self.get_settings()
            firewall = self.get_firewall_rules()
            
            # Récupérer également les clients réseau (nouvelle fonctionnalité)
            network_clients = self.get_network_clients()
            
            # Combiner toutes les parties dans un seul dictionnaire
            return {
                'system_info': system_info,
                'networks': networks,
                'devices': devices,
                'users': users,
                'settings': settings,
                'firewall': firewall,
                'network_clients': network_clients
            }
            
        except RequestException as e:
            _logger.error("Erreur lors de la récupération de la configuration complète: %s", str(e))
            raise
