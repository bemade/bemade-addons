# Modules Odoo à Développer pour le Projet St-Laurent

Ce document présente les différents modules à développer pour chaque type d'installation Odoo dans le cadre du projet St-Laurent, une fédération e-commerce québécoise basée sur Odoo 18.0.

## Tableau des Modules par Type d'Installation

| Module | Odoo Enterprise Local | Odoo Enterprise Central | Odoo ERP Commerçant | Description |
|--------|:---------------------:|:-----------------------:|:-------------------:|-------------|
| **st_laurent_local_core** | ✅ | ❌ | ❌ | Fonctionnalités de base de la plateforme locale, personnalisation régionale, interface d'administration pour les organismes locaux, workflows de modération et approbation |
| **st_laurent_portal_vendor** | ✅ | ✅ | ❌ | Interface simplifiée pour utilisateurs portal, demande d'inscription et processus d'approbation, formulaires simplifiés d'ajout de produits avec soumission à modération |
| **st_laurent_ai_product** | ✅ | ✅ | ❌ | Assistant IA pour l'ajout de produits depuis le portail vendeur, génération de descriptions optimisées, extraction automatique d'attributs, suggestions de catégorisation, enrichissement des synonymes |
| **st_laurent_federation_client** | ✅ | ❌ | ❌ | Connecteur vers l'Odoo Central, fourniture des données produits au fédérateur, partage des index Elasticsearch et dictionnaires de synonymes, réception des documents Odoo |
| **st_laurent_central_core** | ❌ | ✅ | ❌ | Fonctionnalités de la plateforme centrale, gestion du modèle de commission (1% BEMADE, 1% organisme local), administration centralisée de la fédération |
| **st_laurent_federation_server** | ❌ | ✅ | ❌ | Gestion de la fédération, enregistrement des instances régionales autonomes, approvisionnement en données, transfert des documents Odoo aux instances locales |
| **st_laurent_marketplace** | ❌ | ✅ | ❌ | Gestion multi-vendeurs et multi-régions, ventilation des commandes, système de messagerie, portail vendeur provincial, moteur de recherche Elasticsearch, gestion des synonymes |
| **st_laurent_connector** | ❌ | ❌ | ✅ | Connecteur ERP vers les plateformes St-Laurent, synchronisation bidirectionnelle, choix du rayonnement (local ou provincial), intégration avec Elasticsearch |
| **st_laurent_vendor_dashboard** | ❌ | ❌ | ✅ | Tableau de bord vendeur, suivi des ventes, analyse des performances, analyse des termes de recherche et synonymes, suggestions d'optimisation |
| **st_laurent_logistics** | ❌ | ❌ | ✅ | Gestion logistique intégrée, expédition multi-commandes, étiquetage standardisé, intégration transporteurs québécois |
| **st_laurent_elasticsearch** | ✅ | ✅ | ✅ | Intégration avec Elasticsearch, dictionnaires de synonymes adaptés au français québécois et régionalismes, recherche prédictive |
| **st_laurent_payment** | ✅ | ✅ | ❌ | Intégration des méthodes de paiement québécoises, gestion des commissions (1% BEMADE, 1% organisme local), traitement sécurisé des transactions |
| **st_laurent_theme** | ✅ | ✅ | ❌ | Thèmes visuels adaptés à l'identité québécoise avec déclinaisons régionales, approche mobile-first, multilingue |

## Détails des Modules Transversaux

### Modules de Portail Vendeur

| Fonctionnalité | Odoo Enterprise Local | Odoo Enterprise Central | Odoo ERP Commerçant |
|----------------|:---------------------:|:-----------------------:|:-------------------:|
| Interface simplifiée portal | ✅ | ✅ | ❌ |
| Demande d'inscription vendeur | ✅ | ✅ | ❌ |
| Formulaires d'ajout de produits | ✅ | ✅ | ❌ |
| Assistant IA pour ajout de produits | ✅ | ✅ | ❌ |
| Génération de descriptions par IA | ✅ | ✅ | ❌ |
| Extraction automatique d'attributs | ✅ | ✅ | ❌ |
| Suggestions de catégorisation | ✅ | ✅ | ❌ |
| Enrichissement automatique de synonymes | ✅ | ✅ | ❌ |
| Gestion des commandes vendeur | ✅ | ✅ | ❌ |
| Soumission à modération | ✅ | ✅ | ❌ |
| Intégration avec ERP propre | ❌ | ✅ | ✅ |

### Modules de Modération et Approbation

| Fonctionnalité | Odoo Enterprise Local | Odoo Enterprise Central | Odoo ERP Commerçant |
|----------------|:---------------------:|:-----------------------:|:-------------------:|
| Approbation des vendeurs | ✅ | ✅ | ❌ |
| Modération des produits | ✅ | ✅ | ❌ |
| Tableau de bord de modération | ✅ | ✅ | ❌ |
| Workflows configurables | ✅ | ✅ | ❌ |
| Historique des modérations | ✅ | ✅ | ❌ |

### Modules de Recherche et Indexation

| Fonctionnalité | Odoo Enterprise Local | Odoo Enterprise Central | Odoo ERP Commerçant |
|----------------|:---------------------:|:-----------------------:|:-------------------:|
| Intégration Elasticsearch | ✅ | ✅ | ✅ |
| Dictionnaire de synonymes | ✅ | ✅ | ✅ |
| Gestion des régionalismes | ✅ | ✅ | ✅ |
| Recherche prédictive | ✅ | ✅ | ✅ |
| Facettes de recherche | ✅ | ✅ | ❌ |
| Correction orthographique | ❌ | ✅ | ❌ |
| Analyse des termes de recherche | ❌ | ✅ | ✅ |

### Modules de Synchronisation et Fédération

| Fonctionnalité | Odoo Enterprise Local | Odoo Enterprise Central | Odoo ERP Commerçant |
|----------------|:---------------------:|:-----------------------:|:-------------------:|
| Fourniture de données au fédérateur | ✅ | ❌ | ✅ |
| Réception des documents Odoo | ✅ | ❌ | ✅ |
| Gestion des conflits | ✅ | ✅ | ✅ |
| Monitoring de santé | ✅ | ✅ | ✅ |
| Routage des commandes | ❌ | ✅ | ❌ |
| Choix du rayonnement | ❌ | ❌ | ✅ |

### Modules Financiers

| Fonctionnalité | Odoo Enterprise Local | Odoo Enterprise Central | Odoo ERP Commerçant |
|----------------|:---------------------:|:-----------------------:|:-------------------:|
| Gestion des commissions (2%) | ✅ | ✅ | ❌ |
| Répartition (1% BEMADE, 1% organisme) | ✅ | ✅ | ❌ |
| Rapports de revenus | ✅ | ✅ | ✅ |
| Paiement centralisé | ❌ | ✅ | ❌ |
| Facturation automatisée | ❌ | ✅ | ✅ |
| Conformité fiscale québécoise | ✅ | ✅ | ✅ |

## Priorités de Développement

1. **Phase 1 : Modules fondamentaux**
   - st_laurent_local_core
   - st_laurent_central_core
   - st_laurent_federation_client/server
   - st_laurent_portal_vendor (local et central)
   - st_laurent_ai_product (assistant IA pour produits)
   - st_laurent_elasticsearch
   - st_laurent_payment

2. **Phase 2 : Modules d'expérience utilisateur**
   - st_laurent_portal_vendor
   - st_laurent_marketplace
   - st_laurent_theme
   - st_laurent_connector (version de base)

3. **Phase 3 : Modules avancés**
   - st_laurent_vendor_dashboard
   - st_laurent_logistics
   - st_laurent_connector (fonctionnalités avancées)

## Notes d'Implémentation

- Tous les modules doivent être développés pour Odoo 18.0
- Les modules doivent respecter les standards de développement Odoo
- La documentation technique complète doit être fournie pour chaque module
- Les tests unitaires et d'intégration sont obligatoires
- L'approche de développement doit être modulaire pour faciliter la maintenance
- Les modules doivent supporter le multilingue (français et anglais)
- La sécurité et la protection des données doivent être prioritaires
