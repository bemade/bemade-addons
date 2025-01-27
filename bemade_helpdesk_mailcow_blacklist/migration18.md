# Migration vers Odoo 18.0 - bemade_helpdesk_mailcow_blacklist

## Description
Module d'intégration entre Helpdesk et Mailcow pour la gestion des blacklists

## Fonctionnalités Ajoutées
- Synchronisation des emails blacklistés avec Mailcow
- Gestion des règles de blocage
- Historique des actions de blacklist

## Modèles et Champs Modifiés
- helpdesk.ticket
  - Ajout du champ mailcow_blacklisted (boolean)
  - Ajout du champ mailcow_blacklist_reason (text)

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
- Ce module nécessite une configuration spécifique de Mailcow