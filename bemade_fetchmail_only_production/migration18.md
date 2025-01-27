# Migration vers Odoo 18.0 - bemade_fetchmail_only_production

## Description
Module restreignant la récupération des emails uniquement en environnement de production

## Fonctionnalités Ajoutées
- Désactivation de fetchmail dans les environnements de test et de développement
- Configuration par base de données
- Journalisation des tentatives de récupération

## Modèles et Champs Modifiés
- fetchmail.server
  - Ajout du champ production_only (boolean)
  - Ajout du champ last_attempt (datetime)

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
- Ce module pourrait être remplacé par une configuration native dans Odoo 18.0