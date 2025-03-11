# Documentation des Modèles d'Intégration UniFi

Ce document décrit les modèles de données utilisés dans le module d'intégration UniFi pour Odoo 17.0.

## Modèles Principaux

### Site UniFi (`udm.site`)

Représente un site UniFi géré par un UDM/UDR ou un contrôleur logiciel.

**Champs:**
- `name` (Char): Nom du site
- `site_id` (Char): Identifiant du site dans UniFi (toujours 'default')
- `description` (Text): Description du site
- `address` (Text): Adresse physique
- `active` (Boolean): Statut actif
- `controller_type` (Selection): Type de contrôleur (UDM/UDR, Software)
- `host` (Char): Adresse IP ou nom d'hôte du contrôleur
- `port` (Integer): Numéro de port (par défaut: 443)
- `username` (Char): Nom d'utilisateur pour l'authentification
- `password` (Char): Mot de passe pour l'authentification
- `mfa_token` (Char): Code d'authentification à deux facteurs
- `timestamp` (Datetime): Horodatage de la dernière mise à jour
- `raw_data` (Text): Données de configuration brutes au format JSON

**Relations:**
- `system_info_id` (Many2one): Informations système
- `network_ids` (One2many): Configurations réseau
- `vlan_ids` (One2many): Configurations VLAN
- `device_ids` (One2many): Appareils connectés
- `user_ids` (One2many): Comptes utilisateur
- `settings_id` (Many2one): Paramètres généraux
- `firewall_rule_ids` (One2many): Règles de pare-feu
- `port_forward_ids` (One2many): Règles de redirection de port
- `dns_config_id` (Many2one): Configuration DNS
- `routing_config_id` (Many2one): Configuration de routage
- `dashboard_ids` (One2many): Métriques du tableau de bord
- `statistic_ids` (One2many): Statistiques

## Modèles de Réseau

### Network (`udm.network`)

Représente une configuration réseau.

**Champs:**
- `name` (Char): Nom du réseau
- `purpose` (Selection): Objectif du réseau (entreprise, invité, etc.)
- `subnet` (Char): Sous-réseau
- `vlan_enabled` (Boolean): Statut VLAN
- `vlan_id` (Integer): Identifiant VLAN
- `dhcp_enabled` (Boolean): Statut DHCP
- `dhcp_start` (Char): Adresse de début DHCP
- `dhcp_stop` (Char): Adresse de fin DHCP
- `domain_name` (Char): Nom de domaine du réseau
- `raw_data` (Text): Données réseau brutes

### VLAN (`udm.vlan`)

Stocke la configuration VLAN.

**Champs:**
- `vlan_id` (Integer): Identifiant VLAN
- `name` (Char): Nom du VLAN
- `raw_data` (Text): Données VLAN brutes

## Modèles de Sécurité

### Firewall Rule (`udm.firewall.rule`)

Définit les règles du pare-feu.

**Champs:**
- `name` (Char): Nom de la règle
- `description` (Text): Description de la règle
- `action` (Selection): Action (accepter, rejeter, bloquer)
- `protocol` (Char): Protocole réseau
- `source` (Char): Adresse/réseau source
- `destination` (Char): Adresse/réseau de destination
- `enabled` (Boolean): Statut de la règle
- `raw_data` (Text): Données de règle brutes

### Port Forward (`udm.port.forward`)

Définit les règles de redirection de port.

**Champs:**
- `name` (Char): Nom de la règle
- `enabled` (Boolean): Statut de la règle
- `src_port` (Char): Port source
- `dst_port` (Char): Port de destination
- `protocol` (Selection): Protocole (TCP, UDP, les deux)
- `dst_address` (Char): Adresse de destination
- `raw_data` (Text): Données de règle brutes

## Modèles Système

### System Info (`udm.system.info`)

Stocke les informations système de l'UDM Pro.

**Champs:**
- `hostname` (Char): Nom d'hôte du système
- `version` (Char): Version du firmware
- `model` (Char): Modèle de l'appareil
- `uptime` (Integer): Temps de fonctionnement
- `serial` (Char): Numéro de série
- `mac_address` (Char): Adresse MAC
- `raw_data` (Text): Données système brutes

### Settings (`udm.settings`)

Stocke les paramètres généraux de l'UDM Pro.

**Champs:**
- `timezone` (Char): Fuseau horaire du système
- `ntp_servers` (Char): Liste des serveurs NTP
- `dns_servers` (Char): Liste des serveurs DNS
- `raw_data` (Text): Données de paramètres brutes

### DNS Config (`udm.dns.config`)

Stocke la configuration DNS.

**Champs:**
- `enabled` (Boolean): Statut du service DNS
- `filters_enabled` (Boolean): Statut du filtrage de contenu
- `custom_dns` (Char): Serveurs DNS personnalisés
- `raw_data` (Text): Configuration DNS brute

### Routing Config (`udm.routing.config`)

Stocke la configuration de routage.

**Champs:**
- `ospf_enabled` (Boolean): Statut OSPF
- `static_routes` (Text): Liste des routes statiques
- `raw_data` (Text): Données de routage brutes

## Modèles Utilisateur

### User (`udm.user`)

Représente un compte utilisateur UniFi.

**Champs:**
- `name` (Char): Nom d'utilisateur
- `email` (Char): Adresse email
- `role` (Char): Rôle de l'utilisateur
- `enabled` (Boolean): Statut du compte
- `raw_data` (Text): Données utilisateur brutes

### Device (`udm.device`)

Représente un appareil réseau.

**Champs:**
- `name` (Char): Nom de l'appareil
- `mac` (Char): Adresse MAC
- `ip` (Char): Adresse IP
- `device_type` (Char): Type d'appareil
- `model` (Char): Modèle de l'appareil
- `last_seen` (Datetime): Dernier horodatage de connexion
- `raw_data` (Text): Données de l'appareil brutes
