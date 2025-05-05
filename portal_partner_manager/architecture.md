# Architecture du Module Portal Partner Manager

## Vue d'ensemble

Le module Portal Partner Manager permettra aux utilisateurs du portail de modifier les informations de leur société parente et d'ajouter de nouveaux contacts à cette société. Cette fonctionnalité n'est pas disponible dans Odoo standard, car les utilisateurs du portail n'ont normalement que des droits de lecture.

## Structure du module

```
portal_partner_manager/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_partner.py
│   └── portal_access.py
├── controllers/
│   ├── __init__.py
│   └── portal.py
├── views/
│   ├── res_partner_views.xml
│   └── portal_templates.xml
├── security/
│   ├── ir.model.access.csv
│   └── portal_security.xml
└── static/
    ├── src/
    │   └── js/
    │       └── portal_partner.js
    └── src/
        └── scss/
            └── portal_partner.scss
```

## Composants principaux

### 1. Extension du modèle res.partner

Nous allons étendre le modèle `res.partner` pour ajouter des fonctionnalités spécifiques :

- Ajout d'un champ pour suivre les modifications effectuées par les utilisateurs du portail
- Surcharge des méthodes de contrôle d'accès pour permettre aux utilisateurs du portail de modifier certains champs
- Implémentation d'un mécanisme de validation si nécessaire

### 2. Modèle portal_access

Nous créerons un nouveau modèle `portal.access` pour gérer les droits d'accès spécifiques :

- Définition des champs que les utilisateurs du portail peuvent modifier
- Configuration des règles d'accès par utilisateur ou groupe d'utilisateurs
- Journalisation des modifications pour l'audit

### 3. Contrôleur de portail

Nous étendrons le contrôleur de portail existant pour ajouter de nouvelles routes :

- Route pour afficher et modifier les informations de la société parente
- Route pour afficher la liste des contacts existants
- Route pour ajouter de nouveaux contacts
- Gestion des formulaires et validation des données

### 4. Templates de portail

Nous créerons de nouveaux templates pour l'interface utilisateur :

- Template pour afficher et modifier les informations de la société
- Template pour afficher la liste des contacts
- Formulaire pour ajouter de nouveaux contacts
- Messages de confirmation et notifications

### 5. Règles de sécurité

Nous implémenterons des règles de sécurité strictes :

- Règles d'accès pour limiter les modifications aux seules sociétés parentes de l'utilisateur
- Validation des données pour éviter les modifications non autorisées
- Journalisation des modifications pour l'audit

## Flux utilisateur

1. L'utilisateur du portail se connecte à son compte
2. Il accède à une nouvelle section "Ma société" dans le portail
3. Il peut voir et modifier les informations générales de sa société parente
4. Il peut voir la liste des contacts existants de sa société
5. Il peut ajouter de nouveaux contacts à sa société, avec validation de l'email

## Considérations techniques

### Surmonter les limitations du portail

Par défaut, les utilisateurs du portail n'ont que des droits de lecture. Pour surmonter cette limitation, nous utiliserons plusieurs approches :

1. Extension des contrôleurs de portail pour gérer les opérations d'écriture
2. Utilisation de méthodes avec `sudo()` contrôlées par des règles de sécurité strictes
3. Implémentation de règles d'enregistrement (record rules) spécifiques

### Tracking des modifications

Tous les champs modifiables auront l'attribut `tracking=True` comme demandé, ce qui permettra de suivre toutes les modifications apportées par les utilisateurs du portail.

### Validation des données

Nous implémenterons une validation stricte des données, notamment :
- Validation de l'email pour les nouveaux contacts
- Vérification que l'utilisateur ne modifie que sa propre société parente
- Contrôle des champs autorisés à la modification
