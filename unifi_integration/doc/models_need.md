# Modèles nécessaires pour l'intégration des API UniFi

Ce document détaille les modèles et champs nécessaires pour interagir avec les deux API UniFi (Site Manager et Controller), en maximisant la réutilisation des modèles entre les deux types d'API.

## Principes de conception

Pour permettre une intégration efficace avec les deux API tout en minimisant la duplication de code, nous adoptons les principes suivants :

1. **Modèle de base commun** : Chaque entité principale aura un modèle de base commun avec les champs partagés entre les deux API.
2. **Champs spécifiques à l'API** : Les champs spécifiques à chaque API seront clairement identifiés.
3. **Abstraction des méthodes d'accès** : Les méthodes d'accès aux API seront abstraites pour permettre une implémentation spécifique à chaque type d'API.
4. **Héritage et polymorphisme** : Utilisation de l'héritage Odoo pour spécialiser les modèles selon le type d'API.

## 1. Modèle principal : udm.site

Le modèle `udm.site` est le point central de l'intégration. Il doit être adapté pour supporter les deux types d'API.

### Champs communs

```python
# Champs communs à tous les sites UniFi
name = fields.Char(string='Nom', required=True)
description = fields.Text(string='Description')
api_type = fields.Selection([
    ('site_manager', 'Site Manager API (distant)'),
    ('controller', 'Controller API (locale)')
], string='Type d\'API', required=True)
site_id = fields.Char(string='ID du site', help="Identifiant du site dans UniFi")
last_sync = fields.Datetime(string='Dernière synchronisation')
sync_interval = fields.Integer(string='Intervalle de synchronisation (min)', default=60)
active = fields.Boolean(string='Actif', default=True)
```

### Champs spécifiques à l'API Site Manager

```python
# Champs spécifiques à l'API Site Manager
api_key = fields.Char(string='Clé API', help="Clé API pour l'accès au Site Manager")
api_key_encrypted = fields.Char(string='Clé API (chiffrée)', help="Version chiffrée de la clé API")
mfa_enabled = fields.Boolean(string='Authentification à deux facteurs', default=False)
mfa_token = fields.Char(string='Token MFA', help="Token d'authentification à deux facteurs")
cloud_site_id = fields.Char(string='ID du site cloud', help="Identifiant du site dans le cloud UniFi")
```

### Champs spécifiques à l'API Controller

```python
# Champs spécifiques à l'API Controller
host = fields.Char(string='Hôte/IP', help="Adresse IP ou nom d'hôte du contrôleur")
port = fields.Integer(string='Port', default=443)
username = fields.Char(string='Nom d'utilisateur')
password = fields.Char(string='Mot de passe')
password_encrypted = fields.Char(string='Mot de passe (chiffré)')
verify_ssl = fields.Boolean(string='Vérifier SSL', default=False)
controller_type = fields.Selection([
    ('udm', 'UDM Pro/UCG Max'),
    ('controller', 'Contrôleur UniFi standard')
], string='Type de contrôleur', default='udm')
```

### Méthodes abstraites

```python
def authenticate(self):
    """Authentifie auprès de l'API appropriée selon le type"""
    if self.api_type == 'site_manager':
        return self._authenticate_site_manager()
    else:
        return self._authenticate_controller()

def _authenticate_site_manager(self):
    """Implémentation spécifique pour l'API Site Manager"""
    pass

def _authenticate_controller(self):
    """Implémentation spécifique pour l'API Controller"""
    pass

def get_sites(self):
    """Récupère les sites disponibles selon le type d'API"""
    if self.api_type == 'site_manager':
        return self._get_sites_site_manager()
    else:
        return self._get_sites_controller()
```

## 2. Modèle d'authentification : udm.auth.session

Ce modèle gère les sessions d'authentification pour les deux types d'API.

```python
class UdmAuthSession(models.Model):
    _name = 'udm.auth.session'
    _description = 'Session d\'authentification UniFi'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    auth_type = fields.Selection([
        ('api_key', 'Clé API'),
        ('cookie', 'Cookie de session'),
        ('bearer', 'Token Bearer')
    ], string='Type d\'authentification', required=True)
    token = fields.Char(string='Token/Cookie', help="Token d'authentification ou cookie de session")
    token_encrypted = fields.Char(string='Token/Cookie (chiffré)')
    expiry = fields.Datetime(string='Expiration')
    is_valid = fields.Boolean(string='Valide', default=True)
    
    # Méthodes pour gérer les sessions d'authentification
    def validate(self):
        """Vérifie si la session est toujours valide"""
        pass
    
    def refresh(self):
        """Rafraîchit la session si nécessaire"""
        pass
```

## 3. Modèle pour l'authentification à deux facteurs : udm.mfa

```python
class UdmMfa(models.TransientModel):
    _name = 'udm.mfa'
    _description = 'Authentification à deux facteurs UniFi'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True)
    mfa_type = fields.Selection([
        ('totp', 'TOTP (Google Authenticator)'),
        ('sms', 'SMS'),
        ('email', 'Email')
    ], string='Type de MFA', default='totp')
    mfa_code = fields.Char(string='Code MFA', required=True)
    
    def validate_mfa(self):
        """Valide le code MFA et complète l'authentification"""
        pass
```

## 4. Modèle de configuration : udm.api.config

Ce modèle stocke les configurations spécifiques à chaque type d'API.

```python
class UdmApiConfig(models.Model):
    _name = 'udm.api.config'
    _description = 'Configuration API UniFi'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    api_type = fields.Selection(related='site_id.api_type', string='Type d\'API')
    base_url = fields.Char(string='URL de base', compute='_compute_base_url')
    endpoints = fields.Text(string='Endpoints', help="Configuration JSON des endpoints API")
    rate_limit = fields.Integer(string='Limite de taux', default=60)
    timeout = fields.Integer(string='Timeout (secondes)', default=30)
    
    def _compute_base_url(self):
        """Calcule l'URL de base en fonction du type d'API"""
        for config in self:
            if config.api_type == 'site_manager':
                config.base_url = 'https://unifi.ui.com/api'
            else:
                site = config.site_id
                prefix = '/proxy/network' if site.controller_type == 'udm' else ''
                config.base_url = f'https://{site.host}:{site.port}{prefix}'
```

## 5. Adaptations des modèles existants

Les modèles existants doivent être adaptés pour fonctionner avec les deux types d'API. Voici les principales adaptations nécessaires :

### 5.1 udm.device

```python
# Champs communs
site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
name = fields.Char(string='Nom')
mac_address = fields.Char(string='Adresse MAC', required=True)
ip_address = fields.Char(string='Adresse IP')
model = fields.Char(string='Modèle')
device_type = fields.Selection([...], string='Type d\'appareil')

# Champs spécifiques à l'API Site Manager
cloud_device_id = fields.Char(string='ID de l\'appareil cloud')

# Champs spécifiques à l'API Controller
device_id = fields.Char(string='ID de l\'appareil local')
adopted = fields.Boolean(string='Adopté')
```

### 5.2 udm.network

```python
# Champs communs
site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
name = fields.Char(string='Nom', required=True)
subnet = fields.Char(string='Sous-réseau')
purpose = fields.Selection([...], string='Objectif')

# Champs spécifiques à l'API Site Manager
cloud_network_id = fields.Char(string='ID du réseau cloud')

# Champs spécifiques à l'API Controller
network_id = fields.Char(string='ID du réseau local')
```

### 5.3 udm.firewall.rule

```python
# Champs communs
site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
name = fields.Char(string='Nom', required=True)
action = fields.Selection([...], string='Action')
enabled = fields.Boolean(string='Activé', default=True)

# Champs spécifiques à l'API Site Manager
cloud_rule_id = fields.Char(string='ID de la règle cloud')

# Champs spécifiques à l'API Controller
rule_id = fields.Char(string='ID de la règle locale')
```

## 6. Nouveaux modèles pour la gestion des sites

### 6.1 udm.site.discovery

Ce modèle transitoire est utilisé pour découvrir les sites disponibles lors de l'ajout d'un nouveau site.

```python
class UdmSiteDiscovery(models.TransientModel):
    _name = 'udm.site.discovery'
    _description = 'Découverte de sites UniFi'
    
    wizard_id = fields.Many2one('udm.site.import.wizard', string='Assistant')
    api_type = fields.Selection(related='wizard_id.api_type')
    site_name = fields.Char(string='Nom du site')
    site_id = fields.Char(string='ID du site')
    description = fields.Text(string='Description')
    selected = fields.Boolean(string='Sélectionné', default=False)
    
    def import_site(self):
        """Importe le site sélectionné"""
        pass
```

### 6.2 udm.site.import.wizard (extension)

Extension du wizard existant pour supporter les deux types d'API.

```python
class UdmSiteImportWizard(models.TransientModel):
    _name = 'udm.site.import.wizard'
    _description = 'Assistant d\'importation de site UniFi'
    
    # Étape actuelle
    state = fields.Selection([
        ('api_type', 'Choix du type d\'API'),
        ('controller_config', 'Configuration du contrôleur'),
        ('site_manager_config', 'Configuration du Site Manager'),
        ('mfa', 'Authentification à deux facteurs'),
        ('site_selection', 'Sélection du site'),
        ('summary', 'Résumé')
    ], string='Étape', default='api_type')
    
    # Choix du type d'API
    api_type = fields.Selection([
        ('site_manager', 'Site Manager API (distant)'),
        ('controller', 'Controller API (locale)')
    ], string='Type d\'API')
    
    # Configuration du contrôleur
    name = fields.Char(string='Nom du site')
    host = fields.Char(string='Hôte/IP')
    port = fields.Integer(string='Port', default=443)
    username = fields.Char(string='Nom d\'utilisateur')
    password = fields.Char(string='Mot de passe')
    verify_ssl = fields.Boolean(string='Vérifier SSL', default=False)
    controller_type = fields.Selection([
        ('udm', 'UDM Pro/UCG Max'),
        ('controller', 'Contrôleur UniFi standard')
    ], string='Type de contrôleur', default='udm')
    
    # Configuration du Site Manager
    api_key = fields.Char(string='Clé API')
    mfa_enabled = fields.Boolean(string='Authentification à deux facteurs', default=False)
    
    # Sites découverts
    discovered_site_ids = fields.One2many('udm.site.discovery', 'wizard_id', string='Sites découverts')
    
    # Méthodes de navigation
    def action_next(self):
        """Passe à l'étape suivante"""
        pass
    
    def action_previous(self):
        """Revient à l'étape précédente"""
        pass
    
    # Méthodes spécifiques à chaque étape
    def action_discover_sites(self):
        """Découvre les sites disponibles"""
        pass
    
    def action_import_sites(self):
        """Importe les sites sélectionnés"""
        pass
```

## 7. Modèle pour la gestion des erreurs et journalisation

```python
class UdmApiLog(models.Model):
    _name = 'udm.api.log'
    _description = 'Journal API UniFi'
    _order = 'timestamp desc'
    
    site_id = fields.Many2one('udm.site', string='Site', ondelete='cascade')
    api_type = fields.Selection(related='site_id.api_type')
    timestamp = fields.Datetime(string='Horodatage', default=fields.Datetime.now)
    endpoint = fields.Char(string='Endpoint')
    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE')
    ], string='Méthode')
    request_data = fields.Text(string='Données de requête')
    response_data = fields.Text(string='Données de réponse')
    status_code = fields.Integer(string='Code de statut')
    success = fields.Boolean(string='Succès', compute='_compute_success')
    error_message = fields.Text(string='Message d\'erreur')
    
    def _compute_success(self):
        """Détermine si la requête a réussi en fonction du code de statut"""
        for log in self:
            log.success = 200 <= log.status_code < 300
```

## 8. Modèle pour la synchronisation

```python
class UdmSyncJob(models.Model):
    _name = 'udm.sync.job'
    _description = 'Tâche de synchronisation UniFi'
    _order = 'start_time desc'
    
    site_id = fields.Many2one('udm.site', string='Site', required=True, ondelete='cascade')
    api_type = fields.Selection(related='site_id.api_type')
    start_time = fields.Datetime(string='Heure de début', default=fields.Datetime.now)
    end_time = fields.Datetime(string='Heure de fin')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('running', 'En cours'),
        ('done', 'Terminé'),
        ('failed', 'Échoué')
    ], string='État', default='draft')
    sync_type = fields.Selection([
        ('full', 'Complète'),
        ('incremental', 'Incrémentielle')
    ], string='Type de synchronisation', default='incremental')
    log_ids = fields.One2many('udm.api.log', 'sync_job_id', string='Journaux')
    result_summary = fields.Text(string='Résumé des résultats')
    
    def action_run(self):
        """Exécute la tâche de synchronisation"""
        pass
    
    def action_cancel(self):
        """Annule la tâche de synchronisation"""
        pass
```

## Conclusion

Cette structure de modèles permet une intégration efficace avec les deux types d'API UniFi tout en maximisant la réutilisation du code. Les points clés sont :

1. **Séparation claire** des champs communs et spécifiques à chaque API
2. **Abstraction des méthodes d'accès** pour permettre des implémentations spécifiques
3. **Modèles de support** pour l'authentification, la journalisation et la synchronisation
4. **Assistant flexible** pour guider l'utilisateur à travers le processus d'ajout de site

Cette conception facilite la maintenance et l'évolution du module, tout en offrant une expérience utilisateur cohérente quel que soit le type d'API utilisé.
