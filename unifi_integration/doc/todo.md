# Liste des tâches pour le module d'intégration UniFi

Ce document détaille les tâches à accomplir pour atteindre les objectifs définis dans le fichier `objectifs.md`, en commençant par le refactoring des modèles.

## 1. Refactoring des modèles (udm_ → unifi_)

### 1.1 Modèle principal : Site
- [x] Créer le nouveau modèle `unifi.site` basé sur `udm.site`
- [x] Ajouter le champ `api_type` pour distinguer Site Manager et Controller
- [x] Ajouter les champs spécifiques à l'API Site Manager (api_key, mfa_enabled, etc.)
- [x] Ajouter les champs spécifiques à l'API Controller (host, port, controller_type, etc.)
- [x] Implémenter les méthodes abstraites d'authentification pour les deux types d'API
- [x] Mettre à jour les relations avec les autres modèles
- [x] Créer des vues adaptées au nouveau modèle
- [x] Refactoriser le modèle `unifi.site` en trois fichiers distincts :
  - `unifi_site.py` : code commun aux deux types d'API
  - `unifi_site_controller.py` : code spécifique à l'API Controller
  - `unifi_site_manager.py` : code spécifique à l'API Site Manager
- [x] Implémenter les méthodes de délégation dans le modèle principal pour la validation et le nettoyage des champs
- [x] Implémenter les méthodes `_check_required_fields` et `_clear_irrelevant_fields` dans les modèles spécifiques

### 1.2 Modèle : Authentification et Session
- [x] Créer le modèle `unifi.auth.session` pour gérer les sessions d'authentification
- [x] Implémenter les méthodes de validation et rafraîchissement des sessions
- [x] Corriger les erreurs de lint (imports inutilisés, méthodes abstraites)
- [x] Créer le modèle transitoire `unifi.mfa` pour l'authentification à deux facteurs
- [x] Intégrer le modèle MFA avec le flux d'authentification

### 1.2.1 Modèles de support
- [x] Créer le modèle `unifi.api.log` pour journaliser les appels API
- [x] Créer le modèle `unifi.sync.job` pour gérer les tâches de synchronisation
- [x] Créer les vues pour ces modèles de support
- [x] Corriger les erreurs de lint (champs manquants, méthodes référencées dans les vues)
  - [x] Ajouter les champs `start_time` et `end_time` au modèle `unifi.api.log`
  - [x] Ajouter les champs `api_type`, `status` et `message` au modèle `unifi.sync.job`
  - [x] Ajouter les attributs `verify_ssl` et `_name` aux classes `UnifiSiteController` et `UnifiSiteManager`
  - [x] Corriger l'erreur "Statement seems to have no effect" dans le fichier `__manifest__.py`
  - [x] Améliorer la gestion des exceptions dans la méthode de test de connexion
  - [x] Corriger les erreurs de lint restantes concernant les attributs `verify_ssl` et `api_type`
  - [x] Corriger les erreurs de lint dans le modèle `unifi.api.log` (imports inutilisés, méthodes abstraites)
  - [x] Remplacer l'exception générale `Exception` par des types d'exceptions spécifiques
  - [x] Corriger les erreurs de lint concernant l'accès aux méthodes `get_network_data` et `get_vlan_data`
  - [x] Corriger les erreurs "Could not find model" pour les modèles `unifi.site.controller` et `unifi.site.manager`
  - [x] Résoudre le problème de duplication de la méthode `get_vlan_data` dans le modèle `unifi.site`

### 1.3 Modèle : Device (Appareil)
- [x] Créer le nouveau modèle `unifi.device` basé sur `udm.device`
- [x] Ajouter les champs spécifiques (mac_address, ip_address, model, device_type, etc.)
- [x] Implémenter les méthodes de base pour la création et mise à jour des appareils
- [x] Créer des vues adaptées au nouveau modèle (tree, form, search)
- [x] Implémenter la méthode `get_device_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`
- [x] Ajouter la relation `device_ids` au modèle `unifi.site`

### 1.4 Modèle : Network (Réseau)
- [x] Créer le nouveau modèle `unifi.network` basé sur `udm.network`
- [x] Ajouter les champs spécifiques à chaque type d'API
- [x] Implémenter les méthodes de synchronisation pour les deux types d'API
- [x] Mettre à jour les relations avec les autres modèles
- [x] Créer des vues adaptées au nouveau modèle
- [x] Implémenter la méthode `get_network_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`

### 1.5 Modèle : VLAN
- [x] Créer le nouveau modèle `unifi.vlan` basé sur `udm.vlan`
- [x] Ajouter les champs spécifiques à chaque type d'API
- [x] Implémenter les méthodes de synchronisation pour les deux types d'API
- [x] Mettre à jour les relations avec les autres modèles
- [x] Créer des vues adaptées au nouveau modèle
- [x] Implémenter la méthode `get_vlan_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`

### 1.6 Modèle : User (Utilisateur)
- [x] Créer le nouveau modèle `unifi.user` basé sur `udm.user`
- [x] Ajouter les champs spécifiques à chaque type d'API
- [x] Implémenter les méthodes de synchronisation pour les deux types d'API
- [x] Mettre à jour les relations avec les autres modèles
- [x] Créer des vues adaptées au nouveau modèle
- [x] Implémenter la méthode `get_user_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`

### 1.7 Modèle : Firewall (Pare-feu)
- [x] Créer le nouveau modèle `unifi.firewall.rule` basé sur `udm.firewall.rule`
- [x] Ajouter les champs spécifiques à chaque type d'API
- [x] Implémenter les méthodes de synchronisation pour les deux types d'API
- [x] Mettre à jour les relations avec les autres modèles
- [x] Créer des vues adaptées au nouveau modèle
- [x] Implémenter la méthode `get_firewall_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`

### 1.8 Modèle : Port Forward (Redirection de port)
- [x] Créer le nouveau modèle `unifi.port_forward` basé sur `udm.port_forward`
- [x] Ajouter les champs spécifiques à chaque type d'API
- [x] Implémenter les méthodes de synchronisation pour les deux types d'API
- [x] Améliorer l'interface utilisateur pour la gestion des redirections
- [x] Ajouter des validations pour éviter les configurations incorrectes
- [x] Mettre à jour les relations avec les autres modèles
- [x] Créer des vues adaptées au nouveau modèle
- [x] Implémenter la méthode `get_port_forward_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`

### 1.9 Modèles de configuration et système
- [x] Créer le nouveau modèle `unifi.system_info` basé sur `udm.system_info`
- [x] Implémenter la méthode `get_system_info_data` dans les modèles `unifi.site.controller` et `unifi.site.manager`
- [x] Créer le nouveau modèle `unifi.dns` basé sur `udm.dns`
- [x] Créer le nouveau modèle `unifi.dns_config` basé sur `udm.dns_config`
- [x] Créer le nouveau modèle `unifi.routing` basé sur `udm.routing`
- [x] Créer le nouveau modèle `unifi.routing_config` basé sur `udm.routing_config`

### 1.10 Modèles de support
- [x] Créer le modèle `unifi.api.config` pour stocker les configurations API
- [x] Créer le modèle `unifi.api.log` pour la journalisation des appels API
- [x] Créer le modèle `unifi.sync.job` pour gérer les tâches de synchronisation
- [x] Résoudre les problèmes d'accès aux attributs dans les classes héritées (verify_ssl, api_type, name, etc.)

## 2. Amélioration de l'assistant d'ajout de site

### 2.1 Refactorisation de l'assistant existant
- [x] Créer le nouveau modèle `unifi.site.import.wizard` basé sur `udm.site.import.wizard`
- [x] Restructurer l'assistant pour supporter plusieurs étapes
- [x] Implémenter un système de navigation entre les étapes (précédent/suivant)
- [x] Ajouter un état pour suivre la progression dans l'assistant

### 2.2 Ajout du choix du type d'API
- [x] Créer une vue pour le choix du type d'API (Site Manager ou Controller)
- [x] Implémenter la logique de branchement en fonction du choix de l'API
- [x] Ajouter des descriptions et aides contextuelles pour guider l'utilisateur

### 2.3 Modèle de découverte de sites
- [x] Créer le modèle transitoire `unifi.site.discovery` pour la découverte de sites
- [x] Implémenter les méthodes de découverte pour les deux types d'API
- [x] Créer une interface pour afficher et sélectionner les sites disponibles

## 3. Implémentation des API

### 3.1 API Controller (locale)
- [x] Implémenter la logique d'authentification pour les contrôleurs UniFi
- [x] Adapter les endpoints API en fonction du type de contrôleur sélectionné
- [x] Implémenter la logique de validation spécifique à chaque type de contrôleur
- [x] Créer des classes utilitaires pour les appels API communs
- [x] Implémenter la gestion des erreurs et des timeouts
- [x] Intégrer la logique API directement dans le modèle unifi.site.controller
- [x] Ajouter la journalisation des appels API dans unifi.api.log
- [x] Implémenter la gestion des cookies de session et des tokens CSRF
- [x] Implémenter les méthodes de synchronisation des données dans unifi.site
- [x] Corriger les erreurs de lint dans les méthodes de synchronisation
- [x] Implémenter la gestion des certificats auto-signés
- [x] Ajouter des tests unitaires pour les méthodes API

### 3.2 API Site Manager (distante)
- [x] Implémenter l'interface d'authentification à l'API Site Manager
- [x] Développer le processus d'obtention et de validation d'une clé API
- [x] Implémenter la gestion de l'authentification à deux facteurs
- [x] Créer des classes utilitaires pour les appels API communs
- [x] Implémenter la gestion des erreurs et des limites de taux
- [x] Implémenter la méthode test_connection pour vérifier la connexion à l'API Site Manager
- [x] Implémenter la méthode _make_request pour effectuer des requêtes HTTP vers l'API Site Manager

## 4. Synchronisation et gestion des données

### 4.1 Synchronisation automatique
- [x] Implémenter un mécanisme de synchronisation périodique (cron)
- [x] Ajouter des options de configuration pour la fréquence de synchronisation
- [ ] Développer une logique de synchronisation incrémentielle pour optimiser les performances
- [x] Créer des journaux détaillés des opérations de synchronisation
- [x] Implémenter les méthodes _sync_controller et _sync_site_manager dans le modèle unifi.site

### 4.2 Gestion des erreurs et notifications
- [ ] Implémenter un système robuste de gestion des erreurs
- [ ] Créer des notifications pour les événements importants (déconnexion, échec de synchronisation)
- [ ] Ajouter des alertes configurables basées sur les données UniFi
- [ ] Développer un tableau de bord pour visualiser l'état des connexions

### 4.3 Historique et comparaison des configurations
- [ ] Implémenter un système de versionnement des configurations
- [ ] Créer une interface pour comparer les configurations dans le temps
- [ ] Ajouter la possibilité de restaurer

## 5. Nettoyage du code

### 5.1 Suppression des anciens modèles
- [x] Supprimer les importations des modèles `udm_*` dans le fichier `__init__.py`
- [x] Supprimer le champ `settings_id` du modèle `unifi.site`
- [x] Supprimer les fichiers de vues `udm_*.xml`
- [x] Renommer le fichier de sécurité `udm_pro_security.xml` en `unifi_security.xml`
- [x] Mettre à jour le fichier `__manifest__.py` pour refléter ces changements
- [x] Supprimer les fichiers des modèles `udm_*.py`

### 5.2 À nettoyer
- [x] Mettre à jour le contrôleur principal (`controllers/main.py`) qui fait encore référence aux anciens modèles
  - [x] Corriger les références à `host`, `username`, `password` et `port` pour les récupérer depuis le modèle `unifi.site.controller` au lieu de `unifi.site`
  - [x] Remplacer la méthode `import_configuration` qui n'existe plus par une création directe d'enregistrements `unifi.site` et `unifi.site.controller`
- [x] Renommer les groupes de sécurité qui conservent encore les anciens noms (`group_udm_pro_user` et `group_udm_pro_manager`)
  - [x] Mise à jour des références dans le fichier `unifi_menu_views.xml`
  - [x] Mise à jour des références dans le fichier `ir.model.access.csv`
  - [x] Vérification que le contrôleur principal utilise déjà les nouveaux noms de groupes
- [x] Corriger l'erreur de lint dans le fichier `unifi_site_manager.py` concernant la variable `api_log` qui est peut-être indépendante
- [x] Corriger les erreurs de lint dans le fichier `unifi_site_controller.py` concernant les variables `auth_api_log` et `logout_api_log` qui sont peut-être indépendantes
- [x] Vérifier et corriger les autres références aux anciens modèles dans d'autres parties du code
- [x] Mettre à jour les références textuelles à "UDM Pro" par "UniFi" dans les templates pour maintenir la cohérence avec les autres changements

## 6. Interface utilisateur et expérience utilisateur

### 6.1 Implémentation de boutons d'action OWL dans les vues liste (Odoo 18.0)

Odoo 18.0 a introduit plusieurs changements dans la façon dont les composants OWL et les vues personnalisées sont implémentés. Voici les étapes à suivre pour ajouter un bouton d'action personnalisé dans une vue liste :

#### 6.1.1 Structure de fichiers
- [x] Créer un répertoire pour le composant dans `static/src/components/`
- [x] Créer un fichier JavaScript pour le composant du bouton
- [x] Créer un fichier XML pour le template du bouton

#### 6.1.2 Implémentation du composant
- [x] Créer un composant OWL qui utilise le hook `useService` pour accéder au service d'action
- [x] Implémenter la méthode pour déclencher l'action d'importation
- [x] Enregistrer le composant dans le registre des composants avec `registry.category("components").add()`

#### 6.1.3 Définition du template XML
- [x] Créer un template pour le bouton avec les attributs appropriés
- [x] Lier le bouton à la méthode du composant avec `t-on-click`

#### 6.1.4 Configuration dans le manifeste
- [x] Déclarer les assets dans la section `'assets'` du fichier `__manifest__.py`
- [x] Spécifier les fichiers JavaScript et XML dans la clé `'web.assets_backend'`

#### 6.1.5 Configuration de la vue XML
- [x] Ajouter le composant directement dans la vue liste en utilisant la balise appropriée
- [x] S'assurer que le composant est correctement référencé dans la vue

### 6.2 Amélioration des vues
- [ ] Optimiser les vues existantes pour une meilleure ergonomie
- [ ] Créer des vues spécifiques pour les différents types de contrôleurs
- [ ] Ajouter des filtres et regroupements pertinents pour faciliter la navigation
- [ ] Implémenter des actions contextuelles pour les opérations courantes

### 6.2 Tableau de bord
- [ ] Développer un tableau de bord complet avec les métriques importantes
- [ ] Implémenter des graphiques pour visualiser les tendances
- [ ] Ajouter des indicateurs de performance et d'état
- [ ] Créer des vues personnalisables selon les besoins de l'utilisateur

## 7. Documentation et tests

### 7.1 Documentation utilisateur
- [ ] Créer un guide d'installation détaillé
- [ ] Rédiger un manuel utilisateur complet
- [ ] Ajouter des tutoriels pour les cas d'utilisation courants
- [ ] Documenter les API et les modèles pour les développeurs

### 7.2 Tests automatisés
- [ ] Développer des tests unitaires pour les fonctionnalités clés
- [ ] Implémenter des tests d'intégration pour les flux complets
- [ ] Créer des scénarios de test pour les différentes configurations
- [ ] Mettre en place un système d'intégration continue
- [ ] Tester les méthodes de synchronisation avec des données réelles

## 8. Nettoyage et finalisation

### 8.1 Nettoyage du code
- [x] Supprimer les anciens modèles udm_* une fois la migration terminée
- [x] Nettoyer les imports inutilisés et optimiser les dépendances
- [x] Standardiser les noms de variables et les commentaires
- [x] Corriger les erreurs de lint dans les méthodes de synchronisation
- [x] Corriger les erreurs de lint concernant les modèles unifi.dashboard.metric et unifi.dashboard.stat
  - [x] Remplacer l'utilisation de `datetime.now()` par `fields.Datetime.now()` dans unifi_dashboard_stat.py
  - [x] Supprimer les méthodes `create` et `write` qui n'implémentent pas de logique spécifique
- [x] Mettre à jour le contrôleur principal (controllers/main.py) qui fait encore référence aux anciens modèles
  - [x] Corriger les références à `host`, `username`, `password` et `port` pour les récupérer depuis le modèle `unifi.site.controller`
  - [x] Remplacer la méthode `import_configuration` qui n'existe plus par une création directe d'enregistrements
- [x] Renommer les groupes de sécurité (group_udm_pro_user et group_udm_pro_manager)
  - [x] Mise à jour des références dans le fichier `unifi_menu_views.xml`
- [x] Corriger l'erreur de lint dans unifi_site_manager.py concernant la variable api_log
- [x] Corriger les erreurs dans le fichier ir.model.access.csv
- [ ] Mettre à jour les vues XML pour refléter la nouvelle structure des modèles
  - [x] Commenter temporairement les sections des vues qui font référence aux champs déplacés
  - [ ] Créer de nouvelles vues pour les modèles unifi.site.controller et unifi.site.manager
  - [ ] Mettre à jour les vues existantes pour utiliser les nouveaux modèles
- [ ] Corriger l'action action_import_unifi_site
  - [x] Modifier la référence dans le bouton pour utiliser l'ID externe complet
  - [x] Commenter temporairement le bouton d'importation pour permettre l'installation du module
  - [ ] Créer une nouvelle action pour l'importation de sites qui utilise le wizard unifi.site.import.wizard
  - [x] Mise à jour des références dans le fichier `ir.model.access.csv`
- [x] Nettoyer complètement le fichier `ir.model.access.csv`
  - [x] Supprimer toutes les références aux anciens modèles `udm_*`
  - [x] Ajouter les droits d'accès pour les modèles `unifi.dashboard.metric` et `unifi.dashboard.stat`
- [x] Mettre à jour les références textuelles à "UDM Pro" par "UniFi" dans les templates

### 8.2 Tests et validation
- [ ] Créer des tests unitaires pour tous les modèles
- [ ] Implémenter des tests d'intégration pour les flux principaux
- [ ] Valider la compatibilité avec différentes versions d'Odoo
- [ ] Tester avec différentes versions de contrôleurs UniFi

## 9. Déploiement et maintenance

### 9.1 Préparation pour la production
- [ ] Optimiser les performances pour les environnements de production
- [ ] Sécuriser toutes les communications et le stockage des données sensibles
- [ ] Implémenter des mécanismes de sauvegarde et restauration
- [ ] Créer des scripts de migration pour les mises à jour futures

### 9.2 Support et maintenance
- [ ] Établir un processus de suivi des problèmes
- [ ] Créer un système de mise à jour pour suivre les évolutions des API UniFi
- [ ] Documenter les procédures de dépannage courants
- [ ] Préparer des plans de maintenance préventive
