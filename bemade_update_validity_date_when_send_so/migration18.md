# Migration vers Odoo 18.0 - bemade_update_validity_date_when_send_so

## Description
Module de mise à jour de la date de validité lors de l'envoi des commandes clients

## Fonctionnalités Ajoutées
- Mise à jour automatique de la date de validité
- Gestion des exceptions
- Historique des modifications

## Modèles et Champs Modifiés
- sale.order
  - Ajout du champ auto_update_validity (boolean)
  - Ajout du champ last_validity_update (datetime)

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