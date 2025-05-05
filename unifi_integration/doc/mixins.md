# Documentation des Mixins pour UniFi Integration

## Introduction

Ce document décrit les mixins utilisés dans le module UniFi Integration pour gérer les différents types d'API UniFi. Ces mixins permettent de séparer la logique spécifique à chaque type d'API, rendant le code plus maintenable et extensible.

## Vue d'ensemble

Le module UniFi Integration utilise trois mixins principaux :

1. **UnifiCommonMixin** : Fonctionnalités communes à tous les modèles UniFi
2. **UnifiControllerAPIMixin** : Fonctionnalités spécifiques à l'API Controller (locale)
3. **UnifiSiteManagerAPIMixin** : Fonctionnalités spécifiques à l'API Site Manager (cloud)

## UnifiCommonMixin

### Description

Ce mixin fournit des fonctionnalités communes utilisées par plusieurs modèles UniFi, comme le formatage des données JSON brutes.

### Emplacement du fichier

`/models/unifi_common.py`

### Méthodes principales

- **format_raw_data_json(raw_data)** : Formate les données JSON brutes en supprimant les accolades externes et en ajustant l'indentation.

### Exemple d'utilisation

```python
class UnifiSite(models.Model, UnifiCommonMixin):
    _name = 'unifi.site'
    
    def format_data(self):
        raw_data = '{"key": "value"}'
        formatted_data = self.format_raw_data_json(raw_data)
        return formatted_data
```

## UnifiControllerAPIMixin

### Description

Ce mixin fournit des méthodes et des fonctionnalités spécifiques à l'API Controller UniFi (locale). Il est utilisé par le modèle UnifiSite lorsque `api_type` est défini sur 'controller'.

### Emplacement du fichier

`/models/unifi_controller_api_mixin.py`

### Méthodes principales

#### Méthodes de test de connexion

- **_test_controller_connection(site, api_log=None)** : Teste la connexion à l'API Controller UniFi.

#### Méthodes de récupération de données

- **_get_controller_device_data(site)** : Récupère les données des appareils depuis l'API Controller.
- **_get_controller_network_data(site)** : Récupère les données des réseaux depuis l'API Controller.
- **_get_controller_vlan_data(site)** : Récupère les données des VLANs depuis l'API Controller.
- **_get_controller_user_data(site)** : Récupère les données des utilisateurs depuis l'API Controller.
- **_get_controller_firewall_data(site)** : Récupère les données des règles de pare-feu depuis l'API Controller.
- **_get_controller_port_forward_data(site)** : Récupère les données des redirections de port depuis l'API Controller.
- **_get_controller_system_info_data(site)** : Récupère les données d'information système depuis l'API Controller.
- **_get_controller_dns_data(site)** : Récupère les données DNS depuis l'API Controller.

#### Méthodes de synchronisation

- **_sync_controller(site)** : Synchronise toutes les données depuis l'API Controller.
- **_sync_controller_devices(site)** : Synchronise les données des appareils depuis l'API Controller.
- **_sync_controller_networks(site)** : Synchronise les données des réseaux depuis l'API Controller.
- **_sync_controller_vlans(site)** : Synchronise les données des VLANs depuis l'API Controller.
- **_sync_controller_users(site)** : Synchronise les données des utilisateurs depuis l'API Controller.
- **_sync_controller_firewall_rules(site)** : Synchronise les données des règles de pare-feu depuis l'API Controller.
- **_sync_controller_port_forwards(site)** : Synchronise les données des redirections de port depuis l'API Controller.
- **_sync_controller_system_info(site)** : Synchronise les données d'information système depuis l'API Controller.
- **_sync_controller_dns(site)** : Synchronise les données DNS depuis l'API Controller.
- **_sync_controller_wifi(site)** : Synchronise les données WiFi depuis l'API Controller.
- **_sync_controller_routing(site)** : Synchronise les données de routage depuis l'API Controller.

### Paramètres communs

- **site** : L'enregistrement UnifiSite pour lequel effectuer l'opération.
- **api_log** : Enregistrement de journal API optionnel à mettre à jour avec les résultats.

### Exemple d'utilisation

```python
def get_device_data(self):
    self.ensure_one()
    if self.api_type == 'controller':
        controller_api = self.env['unifi.controller.api.mixin']
        return controller_api._get_controller_device_data(self)
    # ...
```

## UnifiSiteManagerAPIMixin

### Description

Ce mixin fournit des méthodes et des fonctionnalités spécifiques à l'API Site Manager UniFi (cloud). Il est utilisé par le modèle UnifiSite lorsque `api_type` est défini sur 'site_manager'.

### Emplacement du fichier

`/models/unifi_site_manager_api_mixin.py`

### Méthodes principales

#### Méthodes de test de connexion

- **_test_site_manager_connection(site, api_log=None)** : Teste la connexion à l'API Site Manager UniFi.

#### Méthodes de récupération de données

- **_get_site_manager_device_data(site)** : Récupère les données des appareils depuis l'API Site Manager.
- **_get_site_manager_network_data(site)** : Récupère les données des réseaux depuis l'API Site Manager.
- **_get_site_manager_vlan_data(site)** : Récupère les données des VLANs depuis l'API Site Manager.
- **_get_site_manager_user_data(site)** : Récupère les données des utilisateurs depuis l'API Site Manager.
- **_get_site_manager_firewall_data(site)** : Récupère les données des règles de pare-feu depuis l'API Site Manager.
- **_get_site_manager_port_forward_data(site)** : Récupère les données des redirections de port depuis l'API Site Manager.
- **_get_site_manager_system_info_data(site)** : Récupère les données d'information système depuis l'API Site Manager.
- **_get_site_manager_dns_data(site)** : Récupère les données DNS depuis l'API Site Manager.

#### Méthodes de synchronisation

- **_sync_site_manager(site)** : Synchronise toutes les données depuis l'API Site Manager.
- **_sync_site_manager_devices(site)** : Synchronise les données des appareils depuis l'API Site Manager.
- **_sync_site_manager_networks(site)** : Synchronise les données des réseaux depuis l'API Site Manager.
- **_sync_site_manager_vlans(site)** : Synchronise les données des VLANs depuis l'API Site Manager.
- **_sync_site_manager_users(site)** : Synchronise les données des utilisateurs depuis l'API Site Manager.
- **_sync_site_manager_firewall_rules(site)** : Synchronise les données des règles de pare-feu depuis l'API Site Manager.
- **_sync_site_manager_port_forwards(site)** : Synchronise les données des redirections de port depuis l'API Site Manager.
- **_sync_site_manager_system_info(site)** : Synchronise les données d'information système depuis l'API Site Manager.
- **_sync_site_manager_dns(site)** : Synchronise les données DNS depuis l'API Site Manager.

### Paramètres communs

- **site** : L'enregistrement UnifiSite pour lequel effectuer l'opération.
- **api_log** : Enregistrement de journal API optionnel à mettre à jour avec les résultats.

### Exemple d'utilisation

```python
def get_device_data(self):
    self.ensure_one()
    if self.api_type == 'site_manager':
        site_manager_api = self.env['unifi.site.manager.api.mixin']
        return site_manager_api._get_site_manager_device_data(self)
    # ...
```

## Intégration avec le modèle UnifiSite

Le modèle UnifiSite utilise ces mixins pour déléguer les appels aux méthodes spécifiques à chaque type d'API. Voici comment cela fonctionne :

1. Le modèle UnifiSite hérite de UnifiCommonMixin pour les fonctionnalités communes.
2. Pour les méthodes spécifiques à un type d'API, le modèle UnifiSite vérifie le type d'API et délègue l'appel au mixin approprié.

### Exemple de délégation

```python
def get_device_data(self):
    self.ensure_one()
    
    # Delegate to the appropriate API mixin
    if self.api_type == 'controller':
        controller_api = self.env['unifi.controller.api.mixin']
        return controller_api._get_controller_device_data(self)
    elif self.api_type == 'site_manager':
        site_manager_api = self.env['unifi.site.manager.api.mixin']
        return site_manager_api._get_site_manager_device_data(self)
    else:
        return False
```

## Avantages de cette approche

1. **Séparation des préoccupations** : Chaque mixin contient uniquement le code spécifique à un type d'API.
2. **Réduction de la taille des fichiers** : Le fichier principal devient beaucoup plus petit et gérable.
3. **Facilité d'extension** : Ajouter un nouveau type d'API nécessite simplement de créer un nouveau mixin.
4. **Meilleure testabilité** : Les mixins peuvent être testés indépendamment du modèle principal.
5. **Clarté du code** : Les développeurs peuvent facilement identifier où se trouve l'implémentation d'une fonctionnalité pour un type d'API spécifique.

## Bonnes pratiques pour l'utilisation des mixins

1. **Nommage cohérent** : Utilisez un préfixe commun pour les méthodes de chaque mixin (par exemple, `_get_controller_*` et `_get_site_manager_*`).
2. **Documentation** : Documentez clairement chaque méthode avec des docstrings.
3. **Paramètres** : Passez toujours l'enregistrement UnifiSite comme premier paramètre aux méthodes des mixins.
4. **Gestion des erreurs** : Gérez correctement les erreurs et mettez à jour les journaux API en conséquence.
5. **Tests** : Écrivez des tests unitaires pour chaque mixin.

## Conclusion

L'utilisation de mixins dans le module UniFi Integration permet de séparer la logique spécifique à chaque type d'API, rendant le code plus maintenable et extensible. Cette approche facilite également l'ajout de nouveaux types d'API à l'avenir.