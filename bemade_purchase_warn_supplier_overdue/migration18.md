# Migration vers Odoo 18.0 - bemade_purchase_warn_supplier_overdue

## Description
Module qui ajoute des avertissements lors de la confirmation des bons de commande pour les fournisseurs ayant des factures en retard.

## Analyse Technique

### Fonctionnalités Actuelles
1. **Avertissements Automatiques**
   - Vérification des factures en retard
   - Création d'activités mail.activity
   - Configuration par entreprise

2. **Modèles Modifiés**
   - `purchase.order` : Ajout de la logique d'avertissement
   - `res.company` : Configuration des avertissements
   - `res.config.settings` : Interface de configuration

3. **Configuration Flexible**
   - Choix des utilisateurs à notifier
   - Sélection des fournisseurs concernés
   - Paramètres par entreprise

### Changements dans Odoo 18.0

1. **Architecture Purchase/Mail**
   - Le système d'activités reste stable
   - Les bons de commande fonctionnent de la même manière
   - Les paramètres de configuration sont similaires

2. **Modifications Nécessaires**
   - [ ] Adapter les vues pour les nouvelles conventions
   - [ ] Vérifier la compatibilité des activités
   - [ ] Mettre à jour les attributs des vues

## Plan de Migration

### Phase 1 : Analyse et Préparation
1. **Révision du Code**
   - [ ] Vérifier les changements dans mail.activity
   - [ ] Tester la création d'activités
   - [ ] Identifier les potentiels conflits

2. **Tests**
   - [ ] Créer des cas de test avec différents scénarios
   - [ ] Documenter le comportement attendu
   - [ ] Préparer des données de test

### Phase 2 : Migration
1. **Mise à Jour du Code**
   - [ ] Adapter les vues XML
   - [ ] Vérifier les dépendances
   - [ ] Optimiser les requêtes si nécessaire

2. **Tests et Validation**
   - [ ] Tester avec différents types de factures
   - [ ] Vérifier les notifications
   - [ ] Valider les configurations

## État de la Migration
 En cours d'analyse - Migration simple requise

## Notes Importantes
- La fonctionnalité reste pertinente dans Odoo 18.0
- Les changements sont mineurs
- La logique de base reste la même
- Attention à la performance des requêtes

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Adapter les vues pour Odoo 18.0
3. Mettre à jour les tests
4. Tester avec différents scénarios

## Notes de Version
- Version originale: 17.0.1.0
- Dernière analyse: 26/01/2025

## Points d'Attention Particuliers
1. **Performance**
   - Optimisation des requêtes de factures
   - Gestion du cache
   - Impact sur les grands volumes

2. **Interface Utilisateur**
   - Clarté des avertissements
   - Configuration intuitive
   - Visibilité des notifications

3. **Maintenance**
   - Documentation des configurations
   - Gestion des cas spéciaux
   - Logs pour le débogage