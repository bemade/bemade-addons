# Modèles actuels du module d'intégration UniFi

Ce document décrit les modèles de données actuellement implémentés dans le module d'intégration UniFi pour Odoo.

## Structure générale

Les modèles du module sont organisés de manière hiérarchique, avec le modèle `udm.site` comme entité centrale. Tous les autres modèles sont liés à un site spécifique et sont supprimés automatiquement lorsque le site est supprimé (via le mécanisme `ondelete='cascade'`).

## Modèles principaux

### 1. udm.site

**Fichier :** `udm_site.py`  
**Description :** Représente un site UniFi géré par un ou plusieurs contrôleurs UniFi.

**Champs principaux :**
- `name` (Char) : Nom du site
- `site_id` (Char) : Identifiant du site dans UniFi (généralement 'default')
- `description` (Text) : Description du site
- `host` (Char) : Adresse IP ou nom d'hôte du contrôleur
- `port` (Integer) : Port du contrôleur (par défaut 443)
- `username` (Char) : Nom d'utilisateur pour l'authentification
- `password` (Char) : Mot de passe pour l'authentification (stocké de manière sécurisée)
- `verify_ssl` (Boolean) : Indique si la vérification SSL doit être effectuée
- `last_sync` (Datetime) : Date et heure de la dernière synchronisation
- `sync_interval` (Integer) : Intervalle de synchronisation en minutes

**Relations :**
- `network_ids` (One2many) : Réseaux associés au site
- `device_ids` (One2many) : Appareils associés au site
- `user_ids` (One2many) : Utilisateurs associés au site
- `vlan_ids` (One2many) : VLANs associés au site
- `firewall_rule_ids` (One2many) : Règles de pare-feu associées au site
- `port_forward_ids` (One2many) : Règles de redirection de port associées au site
- `system_info_id` (One2many) : Informations système associées au site

**Fonctionnalités :**
- Authentification au contrôleur UniFi
- Récupération et synchronisation des données
- Gestion des sessions et des cookies
- Journalisation des activités et des erreurs

### 2. udm.device

**Fichier :** `udm_device.py`  
**Description :** Représente un appareil réseau dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel l'appareil appartient
- `name` (Char) : Nom ou hostname de l'appareil
- `mac_address` (Char) : Adresse MAC de l'appareil
- `ip_address` (Char) : Adresse IP actuelle
- `device_type` (Selection) : Type d'appareil (point d'accès, switch, passerelle, etc.)
- `model` (Char) : Modèle de l'appareil
- `firmware` (Char) : Version du firmware
- `last_seen` (Datetime) : Dernière fois que l'appareil a été vu en ligne
- `uptime` (Integer) : Temps de fonctionnement en secondes
- `status` (Selection) : État de l'appareil (en ligne, hors ligne, provisionnement)
- `adopted` (Boolean) : Indique si l'appareil a été adopté par le contrôleur

### 3. udm.network

**Fichier :** `udm_network.py`  
**Description :** Représente un réseau dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel le réseau appartient
- `name` (Char) : Nom du réseau
- `purpose` (Selection) : Objectif du réseau (entreprise, invité, IoT, autre)
- `subnet` (Char) : Sous-réseau au format CIDR
- `vlan_id_number` (Integer) : Identifiant VLAN
- `vlan_id` (Many2one) : Relation avec le modèle VLAN
- `dhcp_enabled` (Boolean) : Indique si DHCP est activé
- `dhcp_start` (Char) : Adresse de début de la plage DHCP
- `dhcp_stop` (Char) : Adresse de fin de la plage DHCP
- `dhcp_lease_time` (Integer) : Durée du bail DHCP en secondes
- `domain_name` (Char) : Nom de domaine pour le réseau
- `dns_servers` (Char) : Serveurs DNS (séparés par des virgules)
- `enabled` (Boolean) : Indique si le réseau est activé

### 4. udm.user

**Fichier :** `udm_user.py`  
**Description :** Représente un utilisateur dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel l'utilisateur appartient
- `name` (Char) : Nom complet de l'utilisateur
- `email` (Char) : Adresse email de l'utilisateur
- `mac_address` (Char) : Adresse MAC de l'appareil
- `ip_address` (Char) : Adresse IP actuelle
- `network_id` (Many2one) : Réseau auquel l'utilisateur est connecté
- `device_id` (Many2one) : Appareil associé à l'utilisateur
- `role` (Selection) : Rôle de l'utilisateur (admin, opérateur, visualiseur)
- `blocked` (Boolean) : Indique si l'utilisateur est bloqué
- `last_seen` (Datetime) : Dernière fois que l'utilisateur a été vu en ligne
- `upload_usage` (Float) : Utilisation de la bande passante en upload
- `download_usage` (Float) : Utilisation de la bande passante en download
- `total_usage` (Float) : Utilisation totale de la bande passante

### 5. udm.vlan

**Fichier :** `udm_vlan.py`  
**Description :** Représente un VLAN dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel le VLAN appartient
- `name` (Char) : Nom du VLAN
- `vlan_id` (Integer) : Identifiant du VLAN
- `description` (Text) : Description du VLAN
- `enabled` (Boolean) : Indique si le VLAN est activé
- `network_ids` (One2many) : Réseaux associés à ce VLAN

### 6. udm.firewall.rule

**Fichier :** `udm_firewall.py`  
**Description :** Représente une règle de pare-feu dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel la règle appartient
- `name` (Char) : Nom de la règle
- `description` (Text) : Description détaillée de l'objectif de la règle
- `enabled` (Boolean) : Indique si la règle est active
- `sequence` (Integer) : Ordre dans lequel les règles sont évaluées
- `action` (Selection) : Action à effectuer (accepter, rejeter, abandonner)
- `protocol` (Selection) : Protocole concerné (TCP, UDP, ICMP, tous)
- `source_type` (Selection) : Type de source (adresse, réseau, groupe)
- `source_address` (Char) : Adresse source
- `source_port` (Char) : Port source
- `destination_type` (Selection) : Type de destination (adresse, réseau, groupe)
- `destination_address` (Char) : Adresse de destination
- `destination_port` (Char) : Port de destination
- `direction` (Selection) : Direction du trafic (entrant, sortant, les deux)
- `logging` (Boolean) : Indique si la journalisation est activée pour cette règle

## Modèles de configuration

### 7. udm.port_forward

**Fichier :** `udm_port_forward.py`  
**Description :** Représente une règle de redirection de port dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel la règle appartient
- `name` (Char) : Nom de la règle
- `enabled` (Boolean) : Indique si la règle est active
- `source_port` (Integer) : Port source
- `destination_port` (Integer) : Port de destination
- `forward_ip` (Char) : Adresse IP de destination
- `protocol` (Selection) : Protocole (TCP, UDP, TCP et UDP)
- `log` (Boolean) : Indique si la journalisation est activée

### 8. udm.system_info

**Fichier :** `udm_system_info.py`  
**Description :** Représente les informations système du contrôleur UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel les informations appartiennent
- `version` (Char) : Version du logiciel
- `hardware_model` (Char) : Modèle matériel
- `hostname` (Char) : Nom d'hôte du système
- `uptime` (Integer) : Temps de fonctionnement en secondes
- `cpu_usage` (Float) : Utilisation du CPU en pourcentage
- `memory_usage` (Float) : Utilisation de la mémoire en pourcentage
- `disk_usage` (Float) : Utilisation du disque en pourcentage
- `temperature` (Float) : Température du système

### 9. udm.dns et udm.dns_config

**Fichiers :** `udm_dns.py` et `udm_dns_config.py`  
**Description :** Représentent les configurations DNS dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel la configuration appartient
- `hostname` (Char) : Nom d'hôte
- `ip_address` (Char) : Adresse IP associée
- `description` (Text) : Description de l'entrée DNS
- `enabled` (Boolean) : Indique si l'entrée est active

### 10. udm.routing et udm.routing_config

**Fichiers :** `udm_routing.py` et `udm_routing_config.py`  
**Description :** Représentent les configurations de routage dans le système UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel la configuration appartient
- `name` (Char) : Nom de la route
- `destination` (Char) : Destination de la route
- `gateway` (Char) : Passerelle
- `interface` (Char) : Interface réseau
- `enabled` (Boolean) : Indique si la route est active

## Modèles de tableau de bord

### 11. udm.dashboard_metric, udm.dashboard_stat, udm.dashboard_data_point

**Fichiers :** `udm_dashboard_metric.py`, `udm_dashboard_stat.py`, `udm_dashboard_data_point.py`  
**Description :** Représentent les métriques et statistiques pour le tableau de bord.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel les données appartiennent
- `name` (Char) : Nom de la métrique
- `value` (Float) : Valeur de la métrique
- `unit` (Char) : Unité de mesure
- `timestamp` (Datetime) : Horodatage de la mesure
- `category` (Selection) : Catégorie de la métrique (réseau, système, sécurité)

## Modèle de configuration du site

### 12. udm.site_configuration

**Fichier :** `udm_site_configuration.py`  
**Description :** Représente la configuration d'un site UniFi.

**Champs principaux :**
- `site_id` (Many2one) : Site auquel la configuration appartient
- `config_type` (Selection) : Type de configuration
- `config_data` (Text) : Données de configuration au format JSON
- `version` (Char) : Version de la configuration
- `timestamp` (Datetime) : Horodatage de la configuration

## Relations entre les modèles

Le modèle `udm.site` est au centre de l'architecture et toutes les autres entités lui sont liées. Les relations principales sont :

1. **Site → Réseaux** : Un site peut avoir plusieurs réseaux
2. **Site → Appareils** : Un site peut avoir plusieurs appareils
3. **Site → Utilisateurs** : Un site peut avoir plusieurs utilisateurs
4. **Site → VLANs** : Un site peut avoir plusieurs VLANs
5. **Réseau → VLAN** : Un réseau peut être associé à un VLAN
6. **Utilisateur → Réseau** : Un utilisateur peut être connecté à un réseau
7. **Utilisateur → Appareil** : Un utilisateur peut être associé à un appareil

Cette architecture permet une gestion complète et cohérente des environnements UniFi dans Odoo, avec une séparation claire des différentes composantes du système.
