# Objectifs du module d'intégration UniFi

Ce document décrit les objectifs et fonctionnalités prévus pour le module d'intégration UniFi dans Odoo.

## Objectifs :

Gérer la configuration et l'intégration des sites UniFi dans Odoo.  Utiliser le bonne API pour chaque type de contrôleur.  Simplifier la gestion des sites UniFi en utilisant Odoo comme interface pour certaines fonctionnalités mal établies dans l'UDM tel que la configuration des redirections de ports.

## Processus d'ajout d'un site UniFi

### 1. Assistant (Wizard) pour l'ajout d'un site

Le module doit fournir un assistant (wizard) convivial pour faciliter l'ajout d'un nouveau site UniFi. Cet assistant guidera l'utilisateur à travers les étapes nécessaires pour configurer correctement l'intégration.

### 2. Choix du type d'API

L'assistant doit permettre à l'utilisateur de choisir le type d'API à utiliser pour l'intégration :
- **Site Manager API** (distant) : Pour une connexion via l'API cloud de Ubiquiti (unifi.ui.com)
- **Controller API** (locale) : Pour une connexion directe à un contrôleur UniFi sur le réseau local

### 3a. Configuration pour l'API Controller (locale)

Si l'utilisateur choisit l'API Controller (locale), l'assistant doit demander :
- Type d'appareil : UDM Pro/UCG Max ou Contrôleur UniFi standard
- Informations de connexion :
  - Adresse IP ou nom d'hôte
  - Port
  - Identifiants (nom d'utilisateur et mot de passe)
  - Option SSL/TLS
  - Vérification du certificat SSL

### 3b. Configuration pour l'API Site Manager (distante)

Si l'utilisateur choisit l'API Site Manager (distante), l'assistant doit :
- Gérer l'authentification à deux facteurs si nécessaire
- Afficher la liste des sites disponibles associés au compte
- Permettre à l'utilisateur de sélectionner un ou plusieurs sites à intégrer
- Gérer l'obtention et le stockage sécurisé de la clé API

## Fonctionnalités supplémentaires à considérer

- Validation des connexions avant finalisation
- Journalisation des tentatives de connexion
- Options pour la synchronisation automatique des données
- Gestion des erreurs et notifications
- Interface pour visualiser les données synchronisées
- Possibilité de configurer des alertes basées sur les données UniFi
