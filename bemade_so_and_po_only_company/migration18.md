# Migration vers Odoo 18.0 - bemade_so_and_po_only_company

## Description
Module de restriction des commandes clients et fournisseurs à la société actuelle

## Fonctionnalités Ajoutées
- Restriction des commandes à la société actuelle
- Gestion des exceptions
- Historique des modifications

## Modèles et Champs Modifiés
- sale.order
  - Ajout du champ restrict_to_company (boolean)
- purchase.order
  - Ajout du champ restrict_to_company (boolean)

## Statut Migration
- [ ] A migrer
- [ ] En cours
- [ ] Migré

## Détails Migration
- Vérifier si la fonctionnalité existe déjà dans Odoo 18.0
- Analyser les impacts sur les workflows existants

## Actions Requises
- [ ] Vérifier la compatibilité avec Odoo 18.0
- [ ] Tester les fonctionnalités
- [ ] Mettre à jour la documentation

## Notes
- Ce module pourrait nécessiter des adaptations pour Odoo 18.0