# Spécifications du module Portal Planning

## Analyse des modules de planning Odoo Enterprise

### enterprise/planning

Le module `planning` est le module de base pour la gestion des plannings dans Odoo Enterprise. Il offre les fonctionnalités suivantes :

- Création et gestion des créneaux de planning (planning.slot)
- Affectation des employés aux créneaux
- Définition des rôles et des compétences requises
- Visualisation des plannings sous forme de calendrier ou de gantt
- Envoi de notifications par email aux employés
- Gestion des récurrences pour les créneaux réguliers
- Possibilité pour les employés de confirmer leur présence

Le modèle principal est `planning.slot` qui contient toutes les informations relatives à un créneau de planning (date de début, date de fin, employé affecté, rôle, etc.). Les employés sont représentés par le modèle `resource.resource` qui est lié au modèle `hr.employee`.

Le module inclut également un système de demandes de congés et d'échanges de créneaux entre employés, mais ces fonctionnalités ne sont accessibles qu'aux utilisateurs ayant les droits appropriés (pas aux utilisateurs du portail).

### enterprise/planning_contract

Le module `planning_contract` étend le module `planning` pour prendre en compte les contrats des employés lors de la planification. Il ajoute les fonctionnalités suivantes :

- Vérification des heures de travail contractuelles
- Alertes en cas de dépassement des heures contractuelles
- Prise en compte des jours de repos contractuels
- Intégration avec le module `hr_contract` pour récupérer les informations contractuelles

Ce module ajoute des contraintes supplémentaires lors de la création des créneaux de planning pour s'assurer que les employés ne travaillent pas plus que prévu dans leur contrat.

### enterprise/planning_holidays

Le module `planning_holidays` intègre les congés des employés dans le planning. Il offre les fonctionnalités suivantes :

- Prise en compte des congés validés lors de la création des créneaux
- Alertes en cas de conflit entre un créneau et un congé
- Visualisation des congés dans le planning
- Intégration avec le module `hr_holidays` pour récupérer les informations de congés

Ce module permet d'éviter les conflits entre les créneaux de planning et les congés des employés, en empêchant l'affectation d'un employé à un créneau pendant ses congés.

### enterprise/planning_hr_skills

Le module `planning_hr_skills` intègre les compétences des employés dans le planning. Il offre les fonctionnalités suivantes :

- Définition des compétences requises pour un créneau
- Filtrage des employés disponibles en fonction de leurs compétences
- Suggestions d'employés basées sur leurs compétences
- Intégration avec le module `hr_skills` pour récupérer les informations de compétences

Ce module permet d'optimiser l'affectation des employés aux créneaux en fonction de leurs compétences, en suggérant les employés les plus qualifiés pour chaque tâche.

## Alternatives pour l'accès au planning via le portail

### 1. Extension du contrôleur portal.CustomerPortal

Cette approche consiste à étendre le contrôleur `portal.CustomerPortal` pour ajouter des routes spécifiques au planning. Cela permet de réutiliser les fonctionnalités existantes du portail tout en ajoutant des pages dédiées au planning.

**Avantages :**
- Intégration transparente avec le portail existant
- Réutilisation des mécanismes d'authentification du portail
- Cohérence de l'interface utilisateur

**Inconvénients :**
- Nécessite de gérer manuellement les droits d'accès
- Peut nécessiter des modifications importantes en cas de mise à jour du module portal

**Implémentation :**
- Créer un contrôleur qui hérite de `portal.CustomerPortal`
- Ajouter des routes pour afficher et modifier les plannings
- Créer des templates QWeb pour l'affichage des plannings
- Définir des règles de sécurité pour limiter l'accès aux données

### 2. Utilisation de l'API REST d'Odoo

Cette approche consiste à créer une API REST dédiée au planning, accessible aux utilisateurs du portail. Cela permet une plus grande flexibilité dans l'interface utilisateur, notamment pour les applications mobiles.

**Avantages :**
- Séparation claire entre le backend et le frontend
- Possibilité de créer des interfaces utilisateur riches (SPA, applications mobiles)
- Facilité d'intégration avec des systèmes tiers

**Inconvénients :**
- Complexité accrue du développement
- Nécessité de gérer l'authentification et les sessions
- Peut nécessiter des connaissances en développement frontend

**Implémentation :**
- Créer un contrôleur REST qui expose les fonctionnalités du planning
- Définir des endpoints pour les différentes opérations (GET, POST, PUT, DELETE)
- Implémenter l'authentification via des tokens
- Développer une interface utilisateur qui consomme cette API

### 3. Extension des modèles existants avec des champs et méthodes spécifiques

Cette approche consiste à étendre les modèles existants (`planning.slot`, `resource.resource`, etc.) pour ajouter des champs et des méthodes spécifiques aux utilisateurs du portail.

**Avantages :**
- Modification minimale de la structure existante
- Réutilisation des fonctionnalités existantes
- Facilité de maintenance

**Inconvénients :**
- Limitations dans les fonctionnalités disponibles
- Dépendance forte aux modèles existants
- Risque de conflits avec d'autres modules

**Implémentation :**
- Étendre les modèles `planning.slot` et `resource.resource`
- Ajouter des champs pour stocker les informations spécifiques au portail
- Créer des méthodes pour les opérations accessibles via le portail
- Définir des règles de sécurité pour limiter l'accès aux données

### 4. Création de modèles dédiés pour le portail

Cette approche consiste à créer des modèles dédiés pour le portail, qui servent d'interface entre les utilisateurs du portail et les modèles de planning existants.

**Avantages :**
- Séparation claire entre les fonctionnalités du portail et celles du backend
- Contrôle précis des données accessibles aux utilisateurs du portail
- Facilité d'ajout de fonctionnalités spécifiques au portail

**Inconvénients :**
- Duplication potentielle de données
- Nécessité de synchroniser les données entre les modèles
- Complexité accrue de l'architecture

**Implémentation :**
- Créer des modèles dédiés (`portal.planning.slot`, `portal.planning.request`, etc.)
- Implémenter des méthodes pour synchroniser les données avec les modèles existants
- Créer des vues et des actions spécifiques pour ces modèles
- Définir des règles de sécurité adaptées

### 5. Utilisation de modèles transitoires (wizards)

Cette approche consiste à utiliser des modèles transitoires (wizards) pour permettre aux utilisateurs du portail d'interagir avec leur planning sans avoir accès direct aux modèles principaux.

**Avantages :**
- Sécurité renforcée (pas d'accès direct aux données)
- Contrôle précis des actions possibles
- Facilité d'implémentation des workflows complexes

**Inconvénients :**
- Limitations dans la persistance des données
- Interface utilisateur potentiellement moins intuitive
- Complexité accrue pour certaines opérations

**Implémentation :**
- Créer des modèles transitoires pour les différentes actions (demande de congé, échange de créneau, etc.)
- Implémenter des méthodes pour valider et traiter ces actions
- Créer des vues et des actions spécifiques pour ces modèles
- Définir des règles de sécurité adaptées

## Recommandations

Pour l'implémentation du module `portal_planning`, nous recommandons une approche hybride combinant :

1. **Extension du contrôleur portal.CustomerPortal** pour l'interface utilisateur
2. **Extension des modèles existants** pour les fonctionnalités de base
3. **Création de modèles dédiés** pour les fonctionnalités spécifiques au portail

Cette approche permet de bénéficier des avantages de chaque méthode tout en minimisant leurs inconvénients. Elle offre une intégration transparente avec le portail existant, une réutilisation des fonctionnalités de planning, et une séparation claire des préoccupations.

Les principales fonctionnalités à implémenter sont :

- Visualisation du planning personnel
- Confirmation des créneaux affectés
- Demande d'échange de créneaux
- Notification des modifications de planning
- Visualisation des statistiques personnelles (heures travaillées, etc.)

Les règles de sécurité doivent être soigneusement définies pour s'assurer que les utilisateurs du portail n'ont accès qu'à leurs propres données et ne peuvent pas modifier les données critiques.