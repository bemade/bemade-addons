# Todo List - Module Portal Planning

## 1. Configuration initiale

- [x] 1.1 Créer la structure de base du module
  - [x] Créer le fichier `__manifest__.py` avec les dépendances (planning, portal, timesheet)
  - [x] Créer les dossiers de base (models, controllers, views, security, static)
  - [x] Créer le fichier `__init__.py` à la racine
  - **Observation**: La structure de base est déjà en place avec les dépendances nécessaires.

- [x] 1.2 Configurer les fichiers de sécurité
  - [x] Créer le fichier `security/portal_planning_security.xml` pour les groupes de sécurité
  - [x] Créer le fichier `security/ir.model.access.csv` pour les droits d'accès
  - [x] Définir les règles de sécurité pour les utilisateurs du portail
  - **Observation**: Les règles de sécurité de base sont en place, permettant aux utilisateurs du portail d'accéder à leurs propres créneaux de planning.

- [x] 1.3 Configurer les paramètres du module
  - [x] Créer le fichier `data/portal_planning_data.xml` pour les paramètres par défaut
  - **Observation**: Les paramètres par défaut ont été configurés, incluant les options d'approbation automatique et de génération de feuilles de temps.

## 2. Extensions de modèles

- [x] 2.1 Étendre le modèle `planning.slot`
  - [x] Ajouter les champs pour la modification via le portail
  - [x] Ajouter les champs pour la création via le portail
  - [x] Implémenter les méthodes de validation des modifications/créations
  - **Observation**: Le modèle a été étendu avec tous les champs nécessaires et les méthodes pour gérer les modifications et confirmations via le portail.

- [x] 2.2 Étendre le modèle `resource.resource`
  - [x] Ajouter les champs pour l'approbation automatique
  - **Observation**: Le modèle a été étendu pour permettre la configuration de l'approbation automatique au niveau de la ressource.

- [x] 2.3 Étendre le modèle `account.analytic.line` (timesheet)
  - [x] Ajouter les champs pour lier les entrées timesheet aux créneaux de planning
  - **Observation**: Le modèle a été étendu pour lier les feuilles de temps aux créneaux de planning et gérer leur création automatique.

## 3. Nouveaux modèles

- [x] 3.1 Créer le modèle `portal.planning.request`
  - [x] Définir les champs pour les demandes de planning
  - [x] Implémenter les méthodes de validation/refus
  - **Observation**: Un modèle `portal.planning.request` a été créé à la place des modèles `portal.planning.modification` et `portal.planning.creation` initialement prévus. Ce modèle gère les demandes de création de créneaux de planning par les utilisateurs du portail.

- [x] 3.2 Créer le modèle `portal.planning.exchange`
  - [x] Définir les champs pour les demandes d'échange
  - [x] Implémenter les méthodes de validation/refus
  - **Observation**: Le modèle a été créé avec tous les champs nécessaires et les méthodes pour gérer les demandes d'échange entre créneaux.

## 4. Contrôleurs

- [x] 4.1 Étendre le contrôleur `portal.CustomerPortal`
  - [x] Implémenter la route `/my/planning` pour afficher la liste des demandes de planning
  - [x] Implémenter la route `/my/planning/<int:planning_id>` pour afficher le détail d'une demande
  - [x] Implémenter la route `/my/planning/create` pour créer une nouvelle demande
  - [x] Implémenter la route `/my/planning/submit/<int:planning_id>` pour soumettre une demande
  - [x] Implémenter la route `/my/planning/cancel/<int:planning_id>` pour annuler une demande
  - **Observation**: Le contrôleur de base est implémenté pour gérer les demandes de planning, mais il manque les routes pour la gestion directe des créneaux de planning.

- [x] 4.2 Ajouter les routes pour la gestion des créneaux de planning
  - [x] Implémenter la route `/my/planning/slot/<int:slot_id>` pour afficher un créneau
  - [x] Implémenter la route `/my/planning/slot/<int:slot_id>/confirm` pour confirmer un créneau
  - [x] Implémenter la route `/my/planning/slot/<int:slot_id>/modify` pour modifier un créneau
  - [x] Implémenter la route `/my/planning/slot/<int:slot_id>/exchange` pour échanger un créneau
  - **Observation**: Les routes pour la gestion des créneaux ont été implémentées dans le fichier `controllers/planning_slot.py`.

- [x] 4.3 Créer le contrôleur pour l'API JSON
  - [x] Implémenter l'endpoint `/planning/slot/update` pour mettre à jour un créneau
  - [x] Implémenter l'endpoint `/planning/slot/confirm` pour confirmer un créneau
  - [x] Implémenter l'endpoint `/planning/slot/exchange/request` pour demander un échange
  - **Observation**: Les endpoints JSON ont été implémentés dans le fichier `controllers/api.py` pour permettre les interactions AJAX avec les créneaux de planning.

## 5. Vues et templates

- [x] 5.1 Créer les templates du portail pour les demandes de planning
  - [x] Intégrer le planning dans le portail (menu et breadcrumbs)
  - [x] Créer la vue d'ensemble des demandes de planning
  - [x] Créer la vue détaillée d'une demande de planning
  - [x] Créer le formulaire de création d'une demande
  - **Observation**: Les templates de base pour la gestion des demandes de planning sont en place.

- [x] 5.2 Créer les templates pour la gestion des créneaux de planning
  - [x] Créer la vue d'ensemble des créneaux de planning
  - [x] Créer la vue détaillée d'un créneau
  - [x] Créer le formulaire de modification d'un créneau
  - [x] Créer l'interface pour les échanges de créneaux
  - **Observation**: Les templates pour la gestion des créneaux ont été créés dans les fichiers `views/portal_planning_slot_templates.xml` et `views/portal_planning_exchange_templates.xml`.

- [x] 5.3 Créer les vues backend
  - [x] Créer les vues pour le modèle `portal.planning.request`
  - **Observation**: Les vues backend pour le modèle `portal.planning.request` sont en place.

- [x] 5.4 Compléter les vues backend
  - [x] Étendre les vues du modèle `planning.slot` pour intégrer les fonctionnalités du portail
  - [x] Créer les vues pour le modèle `portal.planning.exchange`
  - [x] Créer les vues pour le modèle `portal.planning.modification`
  - **Observation**: Toutes les vues backend ont été créées pour les modèles du module.

## 6. Fonctionnalités de confirmation et timesheet

- [x] 6.1 Implémenter la confirmation des créneaux
  - [x] Développer la logique de confirmation
  - [x] Ajouter les notifications de confirmation
  - **Observation**: La logique de confirmation des créneaux a été implémentée dans le modèle `planning.slot`.

- [x] 6.2 Implémenter la génération automatique des timesheets
  - [x] Développer la logique de vérification des entrées existantes
  - [x] Implémenter la création des entrées pour les périodes non couvertes
  - [x] Lier les entrées timesheet aux créneaux de planning
  - **Observation**: La génération automatique des feuilles de temps a été implémentée dans le modèle `planning.slot`.

## 7. Fonctionnalités de modification

- [x] 7.1 Implémenter la modification des créneaux
  - [x] Développer la logique de validation des modifications
  - [x] Implémenter le processus d'approbation
  - [x] Ajouter les notifications de modification
  - **Observation**: La logique de modification des créneaux a été implémentée dans le modèle `planning.slot` et `portal.planning.modification`.

## 8. Fonctionnalités d'échange

- [x] 8.1 Implémenter l'échange de créneaux
  - [x] Développer la logique de demande d'échange
  - [x] Implémenter le processus d'approbation
  - [x] Ajouter les notifications d'échange
  - **Observation**: La logique d'échange des créneaux a été implémentée dans le modèle `portal.planning.exchange`.

## 9. Interface utilisateur et expérience

- [x] 9.1 Développer les assets frontend
  - [x] Créer les fichiers CSS pour le style du planning dans le portail
  - [x] Créer les fichiers JavaScript pour les interactions dynamiques
  - **Observation**: Les assets frontend ont été développés pour améliorer l'expérience utilisateur dans le portail.

- [x] 9.2 Implémenter la vue calendrier
  - [x] Intégrer une bibliothèque de calendrier (FullCalendar.js)
  - [x] Développer les interactions avec le calendrier
  - **Observation**: La vue calendrier a été implémentée avec FullCalendar.js, permettant aux utilisateurs du portail de visualiser leur planning sous forme de calendrier interactif. Un endpoint API `/planning/api/slots` a été créé pour alimenter le calendrier avec les données des créneaux de planning.

## 10. Tests

- [x] 10.1 Écrire les tests unitaires
  - [x] Tests pour les modèles
  - [x] Tests pour les contrôleurs
  - **Observation**: Les tests unitaires ont été implémentés pour les principaux modèles du module (`portal.planning.request`, `portal.planning.exchange`, `planning.slot`). Ces tests vérifient le bon fonctionnement des méthodes et des contraintes de validation.

- [x] 10.2 Écrire les tests d'intégration
  - [x] Tests pour les workflows complets
  - [x] Tests pour les interactions entre modules
  - **Observation**: Les tests d'intégration ont été implémentés pour vérifier les workflows complets (création, soumission, approbation) et les interactions entre les différents modules (planning, timesheet, mail, portal).

## 11. Documentation

- [ ] 11.1 Écrire la documentation technique
  - [ ] Documentation des modèles et API
  - [ ] Documentation des workflows

- [ ] 11.2 Écrire la documentation utilisateur
  - [ ] Guide d'utilisation du portail planning
  - [ ] Guide d'administration et configuration

## 12. Déploiement

- [ ] 12.1 Préparer le module pour le déploiement
  - [ ] Vérifier les dépendances
  - [ ] Tester l'installation sur un environnement propre

- [ ] 12.2 Créer les scripts de migration
  - [ ] Script de migration pour les données existantes