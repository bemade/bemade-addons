# Module Portal Partner Manager

## Introduction

Le module Portal Partner Manager est une extension pour Odoo 18.0 Enterprise qui permet aux utilisateurs du portail de modifier les informations de leur société parente et d'ajouter de nouveaux contacts à cette société. Cette fonctionnalité n'est pas disponible dans Odoo standard, car les utilisateurs du portail n'ont normalement que des droits de lecture.

## Fonctionnalités principales

- **Modification des informations de la société parente** : Les utilisateurs du portail peuvent modifier les informations générales de leur société parente (nom, adresse, téléphone, email, etc.).
- **Visualisation des contacts** : Les utilisateurs du portail peuvent voir la liste des contacts existants de leur société parente.
- **Ajout de nouveaux contacts** : Les utilisateurs du portail peuvent ajouter de nouveaux contacts à leur société parente, avec validation de l'email.
- **Tracking des modifications** : Toutes les modifications effectuées par les utilisateurs du portail sont tracées et journalisées.
- **Configuration des accès** : Les administrateurs peuvent configurer quels utilisateurs du portail peuvent modifier quelles sociétés et quels champs.

## Installation

1. Téléchargez le module et placez-le dans le répertoire des modules additionnels d'Odoo.
2. Mettez à jour la liste des modules dans Odoo.
3. Installez le module "Portal Partner Manager".
4. Configurez les accès portail pour les sociétés concernées.

## Configuration

### Configuration des accès portail

1. Accédez à **Contacts > Accès portail > Configurations d'accès**.
2. Créez une nouvelle configuration d'accès :
   - Sélectionnez la société pour laquelle vous souhaitez configurer l'accès.
   - Cochez "Autoriser modification" si vous souhaitez que les utilisateurs du portail puissent modifier les informations de cette société.
   - Cochez "Autoriser ajout de contacts" si vous souhaitez que les utilisateurs du portail puissent ajouter de nouveaux contacts à cette société.
   - Sélectionnez les utilisateurs du portail qui auront accès à cette configuration.
   - Optionnellement, sélectionnez les champs spécifiques que les utilisateurs du portail sont autorisés à modifier.

### Configuration au niveau de la société

Vous pouvez également configurer l'accès portail directement depuis la fiche de la société :
1. Accédez à la fiche de la société.
2. Allez dans l'onglet "Accès portail".
3. Cochez ou décochez "Autoriser modification par portail" selon vos besoins.

## Utilisation

### Pour les utilisateurs du portail

1. Connectez-vous au portail Odoo.
2. Accédez à la section "Ma société" depuis le tableau de bord du portail.
3. Visualisez les informations de votre société parente.
4. Cliquez sur "Modifier" pour mettre à jour les informations de la société.
5. Accédez à la section "Contacts" pour voir la liste des contacts existants.
6. Cliquez sur "Ajouter un contact" pour créer un nouveau contact pour votre société.

### Pour les administrateurs

1. Accédez à **Contacts > Accès portail > Configurations d'accès** pour gérer les configurations d'accès.
2. Accédez à **Contacts > Accès portail > Journaux d'accès** pour consulter l'historique des actions effectuées par les utilisateurs du portail.

## Sécurité

Le module implémente plusieurs niveaux de sécurité :

1. **Règles d'accès** : Les utilisateurs du portail ne peuvent accéder qu'à leur propre société parente et aux contacts associés.
2. **Validation des données** : Les données saisies par les utilisateurs du portail sont validées avant d'être enregistrées.
3. **Journalisation** : Toutes les actions effectuées par les utilisateurs du portail sont journalisées pour audit.
4. **Configuration granulaire** : Les administrateurs peuvent configurer précisément quels utilisateurs peuvent modifier quelles sociétés et quels champs.

## Modèles de données

### res.partner (Extension)

Le module étend le modèle `res.partner` pour ajouter les champs suivants :
- `portal_last_update` : Date de la dernière mise à jour effectuée par un utilisateur du portail.
- `portal_updated_by` : Utilisateur du portail qui a effectué la dernière mise à jour.
- `allow_portal_parent_edit` : Si coché, les utilisateurs du portail associés à des contacts de cette société peuvent modifier ses informations.

### portal.access

Ce modèle gère les configurations d'accès portail :
- `name` : Nom de la configuration.
- `partner_id` : Société pour laquelle configurer l'accès portail.
- `allow_edit` : Si coché, les utilisateurs du portail peuvent modifier les informations de cette société.
- `allow_add_contacts` : Si coché, les utilisateurs du portail peuvent ajouter de nouveaux contacts à cette société.
- `allowed_fields_ids` : Champs que les utilisateurs du portail sont autorisés à modifier.
- `portal_user_ids` : Utilisateurs du portail qui ont accès à cette configuration.
- `log_ids` : Journaux d'accès associés à cette configuration.

### portal.access.log

Ce modèle enregistre les actions effectuées par les utilisateurs du portail :
- `access_id` : Configuration d'accès associée.
- `user_id` : Utilisateur qui a effectué l'action.
- `action` : Type d'action (consultation, modification, ajout de contact).
- `details` : Détails de l'action.
- `create_date` : Date de l'action.
- `partner_id` : Société concernée par l'action.

## Développement technique

### Architecture

Le module suit une architecture MVC (Modèle-Vue-Contrôleur) :
- **Modèles** : Extension de `res.partner` et nouveaux modèles `portal.access` et `portal.access.log`.
- **Vues** : Vues backend pour la configuration et templates frontend pour le portail.
- **Contrôleurs** : Extension du contrôleur de portail pour ajouter de nouvelles routes.

### Surmonter les limitations du portail

Par défaut, les utilisateurs du portail n'ont que des droits de lecture. Pour surmonter cette limitation, le module utilise plusieurs approches :
1. Extension des contrôleurs de portail pour gérer les opérations d'écriture.
2. Utilisation de méthodes avec `sudo()` contrôlées par des règles de sécurité strictes.
3. Implémentation de règles d'enregistrement (record rules) spécifiques.

## Support et maintenance

Pour toute question ou problème concernant ce module, veuillez contacter l'équipe de support Odoo.

## Licence

Ce module est distribué sous licence LGPL-3.
