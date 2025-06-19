# Spécifications du module Portal Planning

## 1. Objectifs
- Permettre aux utilisateurs du portail d'accéder à leur planning personnel
- Offrir la possibilité de confirmer leur présence sur les créneaux affectés
- Permettre aux employés de modifier leurs créneaux (avec processus de reconfirmation)
- Permettre aux employés d'ajouter de nouveaux créneaux (avec processus de validation)
- Permettre les demandes d'échange de créneaux
- Notifier les employés des modifications de leur planning
- Fournir des statistiques personnelles sur les heures travaillées

## 2. Architecture technique
- Extension du contrôleur portal.CustomerPortal pour l'interface utilisateur
- Extension des modèles existants (planning.slot, resource.resource) pour les fonctionnalités de base
- Création de modèles dédiés pour les fonctionnalités spécifiques au portail (échanges, modifications, préférences)

## 3. Fonctionnalités détaillées
### 3.1 Visualisation du planning personnel
- Page d'accueil du portail avec compteur et aperçu des créneaux
- Page de planning détaillée avec vue calendrier
- Page de détail pour chaque créneau
- Filtres pour afficher les créneaux par statut (confirmé, à confirmer, modifié, en attente de validation)

### 3.2 Confirmation des créneaux
- Processus de confirmation via différentes interfaces (portail, email)
- Notifications de confirmation
- Historique des confirmations
- Création automatique des entrées timesheet lors de la confirmation
  - Création d'une nouvelle entrée timesheet si aucune n'existe pour cette période
  - Ajout uniquement des heures qui ne sont pas déjà couvertes par des entrées timesheet existantes
  - Conservation des entrées timesheet existantes qui chevauchent le créneau

### 3.3 Modification des créneaux par l'employé
- Interface de modification des détails du créneau (horaires, rôle, notes)
- Processus de validation des modifications
  - Modifications automatiquement approuvées selon les règles configurées
  - Modifications nécessitant une approbation par un responsable
- Statut "modifié" pour les créneaux en attente de reconfirmation
- Notifications aux responsables pour les modifications nécessitant une approbation
- Historique des modifications pour chaque créneau

### 3.4 Ajout de créneaux par l'employé
- Interface d'ajout de nouveaux créneaux (horaires, rôle, notes)
- Processus de validation des nouveaux créneaux
  - Tous les nouveaux créneaux nécessitent une validation par un responsable
  - Statut "en attente de validation" pour les nouveaux créneaux
- Notifications aux responsables pour les nouveaux créneaux à valider
- Une fois validé, le créneau passe au statut "à confirmer"
- L'employé peut alors confirmer sa présence sur le créneau

### 3.5 Échange de créneaux
- Processus de demande d'échange
- Système d'approbation
- Finalisation des échanges
- Historique des demandes d'échange

### 3.6 Notifications
- Types de notifications (affectation, modification, échange, approbation/refus de modification)
- Canaux de notification (email, portail)
- Préférences de notification personnalisables

### 3.7 Statistiques personnelles
- Heures travaillées par période
- Taux de confirmation
- Nombre de modifications effectuées
- Comparaison avec les heures contractuelles

## 4. Interface utilisateur
- Intégration au portail existant
- Design responsive pour tous les appareils
- Accessibilité
- Interfaces spécifiques pour la modification des créneaux

## 5. Sécurité
- Règles de sécurité pour limiter l'accès aux données personnelles
- Droits d'accès spécifiques pour les utilisateurs du portail
- Protection des données sensibles
- Règles pour déterminer quels champs peuvent être modifiés par l'employé

## 6. Modèles de données

### 6.1 Extensions de modèles existants

#### account.analytic.line (timesheet)
- `planning_slot_id`: Lien vers le créneau de planning associé
- `portal_generated`: Booléen indiquant si l'entrée a été générée via le portail
- `portal_confirmation_date`: Date de la confirmation qui a généré cette entrée



#### planning.slot (extension)
- `portal_can_modify`: Booléen indiquant si l'utilisateur du portail peut modifier ce créneau
- `portal_modified`: Booléen indiquant si le créneau a été modifié via le portail
- `portal_modification_date`: Date de la dernière modification via le portail
- `portal_modification_user_id`: Utilisateur ayant effectué la dernière modification
- `portal_modification_approved`: Statut d'approbation de la modification (en attente, approuvé, refusé)
- `portal_modification_notes`: Notes concernant la modification
- `portal_original_start`: Date de début originale avant modification
- `portal_original_end`: Date de fin originale avant modification
- `portal_original_role_id`: Rôle original avant modification
- `portal_created`: Booléen indiquant si le créneau a été créé via le portail
- `portal_creation_date`: Date de création via le portail
- `portal_creation_user_id`: Utilisateur ayant créé le créneau
- `portal_creation_approved`: Statut d'approbation de la création (en attente, approuvé, refusé)
- `portal_creation_notes`: Notes concernant la création

#### resource.resource (extension)
- `portal_modification_auto_approve`: Règles pour l'approbation automatique des modifications

### 6.2 Nouveaux modèles

#### portal.planning.modification
- `slot_id`: Lien vers le créneau modifié
- `user_id`: Utilisateur ayant effectué la modification
- `date`: Date de la modification
- `field_name`: Champ modifié
- `old_value`: Ancienne valeur
- `new_value`: Nouvelle valeur
- `state`: État de la modification (en attente, approuvé, refusé)
- `approver_id`: Utilisateur ayant approuvé/refusé la modification
- `approval_date`: Date d'approbation/refus
- `notes`: Notes concernant la modification

#### portal.planning.creation
- `slot_id`: Lien vers le créneau créé
- `user_id`: Utilisateur ayant créé le créneau
- `date`: Date de la création
- `state`: État de la création (en attente, approuvé, refusé)
- `approver_id`: Utilisateur ayant approuvé/refusé la création
- `approval_date`: Date d'approbation/refus
- `notes`: Notes concernant la création

## 7. Contrôleurs et routes

### 7.1 Extension de portal.CustomerPortal
- `/my/planning`: Vue d'ensemble du planning
- `/my/planning/slot/<int:slot_id>`: Détail d'un créneau
- `/my/planning/slot/<int:slot_id>/confirm`: Confirmation d'un créneau
- `/my/planning/slot/<int:slot_id>/modify`: Modification d'un créneau
- `/my/planning/slot/create`: Création d'un nouveau créneau
- `/my/planning/slot/<int:slot_id>/exchange`: Demande d'échange d'un créneau

### 7.2 API JSON pour les interactions dynamiques
- `/planning/slot/update`: Mise à jour d'un créneau (AJAX)
- `/planning/slot/create`: Création d'un créneau (AJAX)
- `/planning/slot/confirm`: Confirmation d'un créneau (AJAX)
- `/planning/slot/exchange/request`: Demande d'échange (AJAX)

## 8. Vues et templates

### 8.1 Templates portail
- `portal_planning_layout.xml`: Layout général pour les pages de planning
- `portal_planning_my_planning.xml`: Vue d'ensemble du planning
- `portal_planning_slot_detail.xml`: Détail d'un créneau
- `portal_planning_slot_modify.xml`: Formulaire de modification d'un créneau
- `portal_planning_slot_create.xml`: Formulaire de création d'un créneau
- `portal_planning_slot_exchange.xml`: Formulaire de demande d'échange

### 8.2 Vues backend
- `planning_slot_views.xml`: Extension des vues de planning.slot
- `portal_planning_modification_views.xml`: Vues pour le modèle portal.planning.modification
- `portal_planning_creation_views.xml`: Vues pour le modèle portal.planning.creation

## 9. Workflows

### 9.1 Workflow de création d'un créneau
1. L'employé accède à la page de création de créneau via le portail
2. Il remplit le formulaire avec les détails du nouveau créneau (dates, horaires, rôle, notes)
3. Le système enregistre le créneau avec le statut "en attente de validation"
4. Le responsable est notifié de la demande de création de créneau
5. Le responsable examine la demande et l'approuve ou la refuse
6. L'employé est notifié de la décision
7. Si approuvé, le créneau est créé et marqué comme "à confirmer"
8. L'employé peut alors confirmer sa présence sur le créneau

### 9.2 Workflow de modification d'un créneau
1. L'employé accède à son créneau via le portail
2. Il clique sur "Modifier" et effectue les changements souhaités
3. Le système vérifie si les modifications nécessitent une approbation
   - Si non, les modifications sont appliquées immédiatement
   - Si oui, les modifications sont enregistrées avec le statut "en attente"
4. Le responsable est notifié des modifications en attente
5. Le responsable approuve ou refuse les modifications
6. L'employé est notifié de la décision
7. Si approuvé, le créneau est mis à jour et marqué comme "à confirmer"
8. L'employé doit confirmer à nouveau sa présence sur le créneau modifié

### 9.3 Workflow de confirmation et génération de timesheet
1. L'employé accède à son créneau via le portail
2. Il confirme sa présence/exécution pour ce créneau
3. Le système vérifie si des entrées timesheet existent pour cette période
   - Si aucune entrée n'existe, une nouvelle entrée est créée avec les détails du créneau
   - Si des entrées existent et chevauchent partiellement le créneau:
     - Les entrées existantes sont conservées telles quelles
     - De nouvelles entrées sont créées uniquement pour les périodes du créneau qui ne sont pas déjà couvertes
   - Si une entrée existe et couvre exactement le créneau, aucune nouvelle entrée n'est créée
4. Les entrées timesheet générées sont liées au créneau de planning
5. Le créneau est marqué comme confirmé
6. L'employé et le responsable sont notifiés de la confirmation

## 10. Configuration

### 10.1 Paramètres du module
- `portal_planning.allow_modification`: Activer/désactiver la possibilité de modifier les créneaux
- `portal_planning.modification_approval_required`: Définir si l'approbation est requise pour les modifications
- `portal_planning.allow_creation`: Activer/désactiver la possibilité de créer des créneaux
- `portal_planning.fields_modifiable`: Liste des champs modifiables par l'employé
- `portal_planning.auto_create_timesheet`: Activer/désactiver la création automatique des entrées timesheet lors de la confirmation
- `portal_planning.timesheet_project_id`: Projet par défaut pour les entrées timesheet générées
- `portal_planning.timesheet_task_mapping`: Mappage entre les rôles de planning et les tâches de projet

### 10.2 Groupes de sécurité
- `group_portal_planning_user`: Utilisateurs du portail ayant accès au planning
- `group_portal_planning_manager`: Gestionnaires pouvant approuver les modifications

## 11. Intégrations
- Intégration avec les autres modules de planning (contract, holidays, skills)
- Intégration avec les modules hr et mail
- Intégration avec le module timesheet pour la génération automatique des entrées
- Intégration avec le module project pour l'association des entrées timesheet aux projets et tâches
- API pour intégrations externes

## 12. Déploiement et maintenance
- Prérequis (Odoo Enterprise 16.0+, modules planning et portal)
- Processus d'installation et configuration
- Stratégie de mise à jour et maintenance

## 13. Tests et validation
- Tests unitaires pour les modèles et méthodes
- Tests d'intégration pour les flux complets
- Tests utilisateurs pour valider l'expérience

## 14. Documentation
- Documentation technique des modèles et API
- Guide utilisateur pour les fonctionnalités du portail
- Guide administrateur pour la configuration

## 15. Roadmap et évolutions futures
- Application mobile dédiée
- Intégration avec des calendriers externes
- Système de rappels personnalisables
- Statistiques avancées sur les modifications et confirmations