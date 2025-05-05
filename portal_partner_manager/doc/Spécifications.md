# Spécifications du Module Portal Partner Manager

## 1. Présentation Générale

### 1.1 Objectif du Module

Le module Portal Partner Manager est conçu pour étendre les fonctionnalités du portail standard d'Odoo en permettant aux utilisateurs du portail (généralement des clients) de gérer leur société parente et leurs contacts depuis l'interface du portail. Ce module offre une flexibilité accrue aux clients pour maintenir à jour leurs informations sans intervention de l'administrateur Odoo.

### 1.2 Fonctionnalités Principales

- Affichage et modification des informations de la société parente
- Gestion complète des contacts (création, modification, archivage)
- Attribution d'accès portail aux contacts
- Définition des mots de passe pour les utilisateurs du portail
- Journalisation des actions effectuées via le portail
- Configuration fine des permissions d'édition

## 2. Configuration Technique

### 2.1 Dépendances

Le module dépend des modules Odoo suivants :
- base
- portal
- contacts
- mail
- web_editor
- website
- website_mail
- portal_rating
- http_routing

### 2.2 Installation et Activation

Le module s'installe comme tout module standard d'Odoo et ne nécessite pas de configuration particulière après installation. Il est compatible avec Odoo 18.0.

## 3. Architecture du Module

### 3.1 Modèles de Données

#### 3.1.1 Mixin Portal Editable (`portal.editable.mixin`)

Un modèle abstrait qui ajoute des capacités d'édition via le portail à n'importe quel modèle.

**Champs :**
- `portal_last_update` (Datetime) : Date de la dernière mise à jour via le portail
- `portal_updated_by` (Many2one vers res.users) : Utilisateur ayant effectué la dernière mise à jour
- `allow_portal_edit` (Boolean) : Autorise l'édition via le portail si coché

**Méthodes principales :**
- `write()` : Surcharge pour gérer les mises à jour via le portail
- `_check_portal_edit_access()` : Vérifie les permissions d'édition
- `_get_portal_allowed_fields()` : Retourne la liste des champs éditables via le portail

#### 3.1.2 Extension de Partenaire (`res.partner`)

Étend le modèle `res.partner` pour ajouter des fonctionnalités d'édition via le portail.

**Champs ajoutés :**
- Extension des champs du mixin avec descriptions spécifiques
- `allow_portal_parent_edit` (Boolean, related à `allow_portal_edit`) : Champ hérité pour compatibilité

**Méthodes principales :**
- `_check_portal_edit_access()` : Implémentation spécifique pour les partenaires
- `_get_portal_allowed_fields()` : Liste des champs modifiables pour les partenaires
- `get_portal_children()` : Retourne les contacts enfants visibles pour l'utilisateur du portail
- `create_portal_contact()` : Crée un nouveau contact via le portail

#### 3.1.3 Configuration d'Accès au Portail (`portal.access`)

Modèle pour configurer les accès au portail par entreprise.

**Champs :**
- `name` (Char) : Nom de la configuration
- `active` (Boolean) : Statut actif/inactif
- `partner_id` (Many2one vers res.partner) : Société concernée
- `allow_edit` (Boolean) : Autoriser l'édition des informations de la société
- `allow_add_contacts` (Boolean) : Autoriser l'ajout de contacts
- `allowed_fields_ids` (Many2many vers ir.model.fields) : Champs autorisés à l'édition
- `portal_user_ids` (Many2many vers res.users) : Utilisateurs du portail ayant accès
- `log_ids` (One2many vers portal.access.log) : Journaux d'accès

**Méthodes principales :**
- `create()` et `write()` : Mettent à jour les permissions sur le partenaire
- `get_allowed_fields()` : Retourne les champs autorisés pour un partenaire
- `log_access()` : Enregistre une entrée dans le journal d'accès

#### 3.1.4 Journal d'Activités du Portail (`portal.activity.log`)

Ce modèle remplace l'ancien `portal.access.log` et enregistre toutes les activités des utilisateurs du portail.

**Champs principaux :**
| Champ            | Type       | Description                                                   |
|------------------|------------|---------------------------------------------------------------|
| `user_id`        | Many2one   | Utilisateur ayant effectué l'action                           |
| `ip`             | Char       | Adresse IP de l'utilisateur                                   |
| `model`          | Char       | Modèle de l'enregistrement concerné                           |
| `res_id`         | Integer    | ID de l'enregistrement                                         |
| `action`         | Selection  | Type d'action (view, edit, create, archive, grant_access, etc.)|
| `details`        | Text       | Détails supplémentaires                                        |
| `create_date`    | Datetime   | Date de l'action                                              |
| `resource_name`  | Char       | Nom d'affichage de l'enregistrement ou mention s'il est supprimé |

#### 3.1.5 Mixin de Journalisation (`portal.logging.mixin`)

Fournit la méthode `log_portal_activity(user_id, action, details=None, ip=None)` pour ajouter facilement des entrées de journal d'activité depuis n'importe quel modèle.

### 3.2 Contrôleurs

Le module définit un contrôleur principal `PortalPartnerController` qui étend `CustomerPortal` et implémente les routes suivantes :

#### 3.2.1 Routes pour la Gestion de la Société

- `/my/company` : Affiche les informations de la société parente
- `/my/company/edit` : Formulaire d'édition de la société
- `/my/company/update` : Traitement de la mise à jour de la société

#### 3.2.2 Routes pour la Gestion des Contacts

- `/my/contacts` : Liste des contacts de la société
- `/my/contacts/add` : Formulaire d'ajout d'un contact
- `/my/contacts/create` : Traitement de la création d'un contact
- `/my/contacts/edit/<int:contact_id>` : Édition d'un contact existant
- `/my/contacts/update` : Mise à jour d'un contact

#### 3.2.3 Routes pour la Gestion des Accès Portail

- `/my/contacts/grant_access/<int:contact_id>` : Attribution d'un accès portail
- `/my/contacts/set_password_form/<int:contact_id>` : Formulaire de définition de mot de passe
- `/my/contacts/set_password` : Traitement du mot de passe
- `/my/contacts/change_status/<int:contact_id>` : Changement de statut d'un contact (archivage, accès)
- `/my/contacts/archive/<int:contact_id>` : Route héritée pour l'archivage (redirection)

### 3.3 Sécurité et Règles d'Accès

#### 3.3.1 Groupes de Sécurité

- `group_portal_manager` : Groupe pour les gestionnaires des accès portail

#### 3.3.2 Règles d'Accès

- `portal_partner_rule` : Accès en lecture pour les utilisateurs du portail (propre profil, société parente, contacts frères)
- `portal_partner_write_rule` : Accès en écriture à la société parente (si autorisé)
- `portal_partner_self_write_rule` : Accès en écriture à son propre profil
- Règles spécifiques définies dans `portal_partner_manager_rules.xml`

### 3.4 Vues et Templates

#### 3.4.1 Vues Backend

- Vues pour les partenaires (`res_partner_views.xml`)
- Vues pour les configurations d'accès

#### 3.4.2 Templates Portail

- `portal_company_templates.xml` : Templates pour la gestion de la société
- `portal_contact_templates.xml` : Templates pour la gestion des contacts
- `portal_menu_templates.xml` : Items de menu du portail
- `portal_set_password.xml` : Formulaire de définition de mot de passe
- `portal_archive_contact_confirm.xml` : Confirmation d'archivage
- `portal_fix_template.xml` : Correctifs pour le portail standard

### 3.5 Assets Frontend

- CSS : `/static/src/scss/portal_partner.scss`
- JS : `/static/src/js/portal_fix.js` (chargé directement)
- JS : `/static/src/js/portal_partner.js` (chargé en lazy-loading)

## 4. Fonctionnalités Détaillées

### 4.1 Gestion de la Société

Les utilisateurs du portail peuvent visualiser et modifier les informations de leur société parente si celle-ci a activé l'option `allow_portal_edit`. Les modifications sont journalisées et seuls les champs autorisés peuvent être modifiés.

### 4.2 Gestion des Contacts

#### 4.2.1 Affichage des Contacts

Les utilisateurs du portail peuvent voir tous les contacts de leur société parente, y compris les contacts archivés, avec pagination et tri.

#### 4.2.2 Ajout de Contacts

Si autorisé, les utilisateurs peuvent ajouter de nouveaux contacts à leur société. Si un contact avec le même email existe mais est archivé, il sera réactivé plutôt que de créer un doublon.

#### 4.2.3 Modification de Contacts

Les utilisateurs peuvent modifier les informations des contacts existants, avec les mêmes restrictions que pour la société.

#### 4.2.4 Archivage de Contacts

Les contacts peuvent être archivés temporairement et restaurés ultérieurement.

### 4.3 Gestion des Accès Portail

#### 4.3.1 Attribution d'Accès

Les utilisateurs peuvent attribuer des accès portail à d'autres contacts de leur société. Le système vérifie si un utilisateur avec le même email existe déjà et gère les cas appropriés.

#### 4.3.2 Définition de Mot de Passe

Pour les nouveaux utilisateurs du portail, un email d'invitation est envoyé. Pour les utilisateurs réactivés, un formulaire permet de définir un nouveau mot de passe directement.

#### 4.3.3 Changement de Statut

Les utilisateurs peuvent changer le statut des contacts entre trois états :
- Accès portail (avec compte utilisateur)
- Accès standard (contact sans compte utilisateur)
- Archivé (contact désactivé)

### 4.4 Journalisation et Suivi

Toutes les actions effectuées via le portail sont journalisées pour assurer un suivi et un audit complet, à l'aide du modèle `portal.activity.log` et du mixin `portal.logging.mixin` :
- Consultation des informations
- Modifications apportées
- Ajout de contacts
- Attribution d'accès portail

### 4.5 Journal d'Activités du Portail

Ce modèle remplace l'ancien `portal.access.log` et enregistre toutes les activités des utilisateurs du portail.

## 5. Personnalisation et Extension

### 5.1 Configuration des Champs Autorisés

Les administrateurs peuvent configurer précisément quels champs peuvent être modifiés par les utilisateurs du portail via le modèle `portal.access`.

### 5.2 Extension du Module

Le module est conçu pour être facilement extensible :
- Le mixin `portal.editable.mixin` peut être appliqué à d'autres modèles
- Les méthodes de vérification d'accès peuvent être surchargées
- De nouvelles fonctionnalités peuvent être ajoutées aux contrôleurs existants

## 6. Tests et Qualité

Le module inclut des tests automatisés pour vérifier :
- La synchronisation des emails et logins
- Les fonctionnalités de gestion des partenaires via le portail

## 7. État Actuel et Améliorations Futures

### 7.1 État d'Avancement

**État actuel:** Fonctionnel mais avec des opportunités d'amélioration

Le module est globalement fonctionnel et implémente toutes les fonctionnalités principales décrites dans les spécifications. Les utilisateurs du portail peuvent consulter et modifier leur société parente, ainsi que gérer leurs contacts. Cependant, certaines tâches du fichier `todo.md` restent marquées comme non complétées, ce qui indique que le module pourrait bénéficier d'améliorations supplémentaires.

### 7.2 Tâches Restantes

1. **Finalisation de la documentation**
   - Compléter la documentation utilisateur avec des captures d'écran
   - Ajouter plus d'exemples d'utilisation dans README.md

2. **Tests additionnels**
   - Augmenter la couverture des tests pour inclure les cas limites
   - Ajouter des tests pour les fonctionnalités d'archivage et de restauration
   - Tester les scénarios multi-utilisateurs (plusieurs utilisateurs portail pour une même société)

3. **Optimisations visuelles**
   - Améliorer le design responsive des formulaires sur mobile
   - Ajouter des indicateurs de chargement pendant les actions AJAX
   - Améliorer l'accessibilité des formulaires et boutons

### 7.3 Commentaires et Suggestions

#### 7.3.1 Améliorations Fonctionnelles

1. **Gestion avancée des permissions**
   - Implémenter un système de rôles pour les utilisateurs du portail (admin portail, utilisateur standard)
   - Permettre de configurer les permissions par champ et par utilisateur

2. **Intégration avec d'autres modules**
   - Ajouter une intégration avec les modules de signature électronique pour la validation des modifications
   - Intégrer avec le module CRM pour permettre aux contacts de gérer leurs opportunités

3. **Fonctionnalités de collaboration**
   - Ajouter un système de commentaires/notes sur les contacts
   - Implémenter un fil d'activité pour suivre les modifications sur les contacts

#### 7.3.2 Améliorations Techniques

1. **Performance**
   - Optimiser les requêtes SQL pour les listes de contacts volumineuses
   - Implémenter le chargement paresseux des informations non critiques

2. **Sécurité**
   - Ajouter un système de vérification par email pour les modifications sensibles
   - Renforcer la validation des données côté serveur

3. **Extensibilité**
   - Extraire certaines fonctionnalités génériques dans des mixins réutilisables
   - Documenter les points d'extension du module pour faciliter les personnalisations

#### 7.3.3 Priorités Recommandées

Les tâches suivantes devraient être considérées comme prioritaires pour améliorer le module :

1. Compléter les tests pour garantir la stabilité des fonctionnalités existantes
2. Améliorer la gestion des permissions pour les environnements multi-utilisateurs
3. Optimiser l'expérience mobile pour les utilisateurs du portail
4. Documenter les cas d'utilisation avancés pour faciliter l'adoption