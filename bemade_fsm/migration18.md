# Improved Field Service Management - Migration vers Odoo 18.0

## Description
Ce module étend les fonctionnalités de gestion des services sur site (Field Service Management) avec des fonctionnalités spécifiques à Durpro.

## Fonctionnalités Ajoutées
### Gestion améliorée des services sur site
- **Existe dans Odoo 18.0 ?** : Partiellement
- **Différences avec la version native** :
  - Gestion avancée des équipements et des contacts
  - Système de modèles de tâches personnalisé
  - Intégration approfondie avec les commandes de vente
  - Gestion des visites FSM
  - Propagation des affectations et des contacts
- **Alternatives** :
  - Utiliser le module FSM standard d'Odoo
  - Implémenter des fonctionnalités spécifiques via des modules personnalisés

## Modèles et Champs Modifiés
### Modèles impactés
- **project.task** :
  - **Champs ajoutés** :
    - work_order_contacts : Contacts liés au bon de travail
    - site_contacts : Contacts sur site
    - visit_id : Lien vers la visite FSM
    - relevant_order_lines : Lignes de commande pertinentes
    - work_order_number : Numéro de bon de travail
    - propagate_assignment : Propagation des affectations
    - is_closed : Indicateur de tâche fermée
    - root_ancestor : Tâche racine de la hiérarchie
  - **Méthodes modifiées** :
    - create() : Gestion des contacts et numéros de bon de travail
    - write() : Propagation des modifications aux sous-tâches
    - _compute_allow_billable() : Calcul de la facturabilité
    - _fsm_create_sale_order_line() : Création de lignes de commande
    - action_fsm_validate() : Validation des tâches FSM
    - synchronize_name_fsm() : Synchronisation des noms des tâches
  - **Recommandations de migration** :
    - Vérifier la compatibilité avec le nouveau système de tâches Odoo 18
    - Tester la propagation des modifications
    - Adapter les calculs de facturabilité
    - Vérifier la gestion des noms des tâches

- **task.template** :
  - **Nouveau modèle** : project.task.template
  - **Champs principaux** :
    - name : Nom du modèle
    - description : Description HTML
    - assignees : Utilisateurs assignés par défaut
    - customer : Client par défaut
    - project : Projet par défaut
    - tags : Tags par défaut
    - parent : Modèle parent
    - subtasks : Sous-tâches
    - sequence : Ordre d'affichage
    - company_id : Société
    - planned_hours : Heures planifiées
    - equipment_ids : Équipements à entretenir
  - **Méthodes principales** :
    - _prepare_new_task_values_from_self() : Prépare les valeurs pour une nouvelle tâche
    - create_task_from_self() : Crée une tâche à partir du modèle
  - **Recommandations de migration** :
    - Vérifier la compatibilité avec le nouveau système de modèles de tâches Odoo 18
    - Tester la création de tâches à partir des modèles
    - Adapter la gestion des équipements et des heures planifiées
- **product.template** :
  - **Champs ajoutés** :
    - task_template_id : Modèle de tâche associé
    - is_field_service : Indicateur de service sur site
  - **Recommandations de migration** :
    - Vérifier la compatibilité avec le nouveau système de produits Odoo 18
    - Tester la gestion des modèles de tâches
    - Adapter l'indicateur de service sur site
- **res.partner** :
  - **Champs ajoutés** :
    - is_site_contact : Indicateur de contact sur site
    - is_service_site : Indicateur de site de service
    - site_ids : Sites de travail liés
    - site_contacts : Contacts sur site
    - work_order_contacts : Destinataires des bons de travail
  - **Méthodes modifiées** :
    - _compute_is_site_contact() : Calcul de l'état de contact sur site
    - _search_is_site_contact() : Recherche des contacts sur site
    - _compute_is_service_site() : Calcul de l'état de site de service
  - **Recommandations de migration** :
    - Vérifier la compatibilité avec le nouveau système de partenaires Odoo 18
    - Tester les calculs des indicateurs
    - Adapter la gestion des relations entre sites et contacts
- **sale.order** :
  - **Champs ajoutés** :
    - valid_equipment_ids : Équipements valides
    - default_equipment_ids : Équipements par défaut à entretenir
    - summary_equipment_ids : Équipements en cours de maintenance
    - site_contacts : Contacts sur site
    - work_order_contacts : Destinataires du bon de travail
    - visit_ids : Visites FSM liées
    - is_fsm : Indicateur de commande FSM
  - **Méthodes modifiées** :
    - get_relevant_order_lines() : Récupère les lignes pertinentes pour une tâche
    - _compute_summary_equipment_ids() : Calcule les équipements en maintenance
    - _onchange_partner_shipping_id() : Gère les changements de partenaire
    - _compute_default_contacts() : Calcule les contacts par défaut
    - _compute_default_equipment() : Calcule les équipements par défaut
    - copy() : Gère la copie des visites
    - _create_default_visit() : Crée une visite par défaut
    - _create_or_organize_visits_if_needed() : Organise les visites FSM
    - action_confirm() : Confirmation de commande avec gestion FSM
    - write() : Gère les mises à jour des partenaires
  - **Recommandations de migration** :
    - Vérifier la compatibilité avec le nouveau système de commandes Odoo 18
    - Tester la gestion des équipements
    - Adapter la gestion des visites FSM
    - Vérifier les calculs de contacts et d'équipements

## Vues à modifier
- **Vues existantes** :
  - Formulaire de tâche :
    - Ajout d'une page "Equipment and Contacts"
    - Modification des boutons de validation
    - Ajout du champ propagate_assignment
  - Vue liste :
    - Ajout du champ work_order_number
    - Masquage de certains champs optionnels
  - Vue calendrier :
    - Personnalisation des couleurs par utilisateur
    - Suppression du champ worksheet_template_id
  - Vue de recherche :
    - Modification des filtres de planification
    - Ajout du filtre "Parent Task"
- **Nouvelles vues** :
  - Aucune nouvelle vue créée, uniquement des modifications des vues existantes
- **Recommandations pour Odoo 18** :
  - Vérifier la compatibilité avec les nouvelles vues Odoo 18
  - Adapter les modifications de vues aux nouveaux designs
  - Tester les fonctionnalités de recherche et de filtrage
  - Vérifier la gestion des couleurs dans le calendrier

## Rapports
- **Rapports personnalisés** :
  - **Nouveaux blocs de rapport** :
    - Tableau des matériaux
    - Tableau des temps et matériaux avec tarification
    - Liste des sous-tâches
    - Bloc d'informations sur la commande
    - Résumé des équipements
    - Entrées de feuille de temps
    - Bloc de signature
  - **Modifications principales** :
    - Intégration des contacts et informations client
    - Affichage des dates planifiées
    - Gestion des signatures numériques
    - Personnalisation de la mise en page
  - **Recommandations pour Odoo 18** :
    - Vérifier la compatibilité avec le nouveau système de rapports Odoo 18
    - Adapter les modèles de rapport aux nouvelles fonctionnalités
    - Tester l'affichage des différents blocs
    - Vérifier la gestion des signatures numériques

## Assistants (Wizards)
- **Nouveaux assistants** : À documenter

## Analyse des Alternatives Natives Odoo 18.0

### Fonctionnalités Natives à Explorer
1. **Gestion des Services** :
   - Module Industry FSM d'Odoo Enterprise
   - Nouvelles fonctionnalités de planification
   - Système de rapports amélioré

2. **Gestion des Équipements** :
   - Module Maintenance d'Odoo
   - Intégration avec FSM
   - Système de suivi des équipements

3. **Gestion des Contacts** :
   - Système de contacts hiérarchiques
   - Gestion des rôles des contacts
   - Système d'adresses de livraison

### Approche "Vanilla First"

1. **Fonctionnalités à Conserver en Custom** :
   - Gestion spécifique des visites FSM
   - Propagation des affectations
   - Modèles de tâches personnalisés
   - Gestion avancée des contacts sur site

2. **Fonctionnalités à Migrer vers Native** :
   - Utiliser le système de planification natif
   - Adopter le système de rapports standard
   - Utiliser la gestion des équipements native
   - Intégrer avec le système de contacts standard

## Plan de Migration

### Phase 1 : Analyse et Préparation
1. **Audit des Fonctionnalités** :
   - [ ] Identifier les fonctionnalités disponibles nativement
   - [ ] Lister les gaps fonctionnels
   - [ ] Évaluer l'impact sur les processus existants

2. **Planification** :
   - [ ] Définir la stratégie de migration
   - [ ] Établir un calendrier
   - [ ] Identifier les risques

### Phase 2 : Migration Technique
1. **Adaptation du Code** :
   - [ ] Mettre à jour les vues (tree -> list)
   - [ ] Supprimer les attrs obsolètes
   - [ ] Adapter les méthodes aux nouvelles API

2. **Intégration Native** :
   - [ ] Intégrer avec Industry FSM
   - [ ] Connecter avec le module Maintenance
   - [ ] Adapter le système de contacts

### Phase 3 : Tests et Validation
1. **Tests Fonctionnels** :
   - [ ] Validation des workflows
   - [ ] Tests des rapports
   - [ ] Vérification des intégrations

2. **Tests de Performance** :
   - [ ] Analyse des requêtes SQL
   - [ ] Tests de charge
   - [ ] Optimisation si nécessaire

## Recommandations Spécifiques

### Modèles et Champs
1. **project.task** :
   - Utiliser les champs natifs quand possible
   - Conserver uniquement les champs spécifiques
   - Adapter les méthodes aux nouvelles API

2. **task.template** :
   - Évaluer le système de modèles natif
   - Simplifier la structure si possible
   - Optimiser la création de tâches

3. **sale.order** :
   - Utiliser les fonctionnalités FSM natives
   - Optimiser la gestion des visites
   - Simplifier les calculs

### Vues et Interface
1. **Modifications Prioritaires** :
   - Remplacer tree par list
   - Supprimer les attrs obsolètes
   - Adapter aux nouveaux standards UI

2. **Améliorations Suggérées** :
   - Utiliser les nouveaux widgets
   - Simplifier les vues
   - Améliorer l'expérience utilisateur

### Rapports
1. **Stratégie de Migration** :
   - Utiliser le nouveau système de rapports
   - Adapter les modèles existants
   - Optimiser le rendu

## État de la Migration
⚪ En analyse préliminaire

## Notes Importantes
- Module complexe nécessitant une approche progressive
- Forte dépendance avec d'autres modules
- Impact important sur les processus métier
- Nécessité de formation des utilisateurs

## Prochaines Étapes
1. Valider l'approche avec les parties prenantes
2. Créer un environnement de test
3. Commencer par les fonctionnalités critiques
4. Planifier la formation des utilisateurs

## Analyse Technique

### Fonctionnalités Natives dans Odoo 18.0

Le module `industry_fsm` d'Odoo Enterprise 18.0 inclut déjà plusieurs fonctionnalités avancées :

1. **Gestion des Tâches FSM**
   - Champ `is_fsm` sur les projets pour identifier les projets FSM
   - Champ `fsm_done` sur les tâches pour marquer leur complétion
   - Gestion des signatures sur les rapports de travail
   - Gestion des coordonnées client (téléphone, adresse, etc.)
   - Planification avec dates de début/fin

2. **Fonctionnalités de Base**
   - Vue spécifique pour les travailleurs sur le terrain
   - Rapports sur les tâches
   - Intégration avec les feuilles de temps
   - Géolocalisation des clients
   - Gestion des produits sur les tâches

3. **Sécurité et Contraintes**
   - Règles de sécurité spécifiques FSM
   - Contraintes sur les projets FSM (company_id requis)
   - Restrictions sur les dépendances de tâches et les jalons

### Différences avec Notre Module

1. **Fonctionnalités à Migrer**
   - [ ] Fonctionnalités spécifiques de gestion d'équipement
   - [ ] Workflows personnalisés
   - [ ] Rapports et analyses spécifiques
   - [ ] Intégrations avec d'autres modules custom

2. **Fonctionnalités à Adapter**
   - [ ] Utiliser les champs natifs plutôt que nos champs customs
   - [ ] Adapter nos vues aux nouvelles conventions Odoo 18.0
   - [ ] Intégrer nos processus avec le système natif

## Plan de Migration

### Phase 1 : Préparation
1. **Analyse des Données**
   - [ ] Identifier les données spécifiques à notre module
   - [ ] Mapper les champs actuels vers les champs natifs
   - [ ] Lister les fonctionnalités uniques à préserver

2. **Configuration**
   - [ ] Activer et configurer le module `industry_fsm`
   - [ ] Vérifier les dépendances et les conflits
   - [ ] Préparer les scripts de migration des données

### Phase 2 : Migration
1. **Migration des Données**
   - [ ] Transférer les données vers les structures natives
   - [ ] Adapter les configurations existantes
   - [ ] Mettre à jour les vues et rapports

2. **Développement**
   - [ ] Adapter le code pour utiliser l'API Odoo 18.0
   - [ ] Implémenter les fonctionnalités manquantes
   - [ ] Mettre à jour les vues XML (plus d'attrs, list au lieu de tree)

### Phase 3 : Tests
1. **Validation Fonctionnelle**
   - [ ] Tester les fonctionnalités de base FSM
   - [ ] Vérifier nos fonctionnalités spécifiques
   - [ ] Valider les workflows

2. **Tests d'Intégration**
   - [ ] Tester avec les autres modules
   - [ ] Vérifier la compatibilité mobile
   - [ ] Valider les performances

## État de la Migration
🟡 En cours d'analyse - Utilisation maximale des fonctionnalités natives

## Notes Importantes
- Le module `industry_fsm` d'Odoo Enterprise offre une base solide
- Plusieurs de nos fonctionnalités peuvent être remplacées par des fonctionnalités natives
- Certaines personnalisations spécifiques devront être maintenues
- La nouvelle interface utilisateur nécessitera une formation des utilisateurs

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Créer les scripts de migration des données
3. Développer les fonctionnalités manquantes
4. Planifier la formation des utilisateurs

## Notes de Version
- Version originale: 17.0.1.0.0
- Dernière analyse: 26/01/2025