# Migration vers Odoo 18.0 - bemade_quotation_alternative

## Description
Module qui permet de créer des devis alternatifs à partir d'un devis existant, avec la possibilité de sélectionner les lignes à dupliquer.

## Analyse Technique

### Fonctionnalités Actuelles
1. **Assistant de Duplication**
   - Duplication sélective des lignes
   - Copie des notes et objectifs
   - Gestion des liens entre devis

2. **Modèles Modifiés**
   - `sale.order` : Ajout de l'action de duplication
   - Assistant de duplication transient
   - Gestion des messages dans le chatter

3. **Interface Utilisateur**
   - Assistant de sélection des lignes
   - Notification dans le chatter
   - Liens entre devis original et copie

### Changements dans Odoo 18.0

1. **Architecture Sale**
   - Le modèle sale.order reste stable
   - Le système de chatter est similaire
   - Les assistants transients fonctionnent de la même manière

2. **Modifications Nécessaires**
   - [ ] Adapter les vues pour les nouvelles conventions
   - [ ] Vérifier la compatibilité du chatter
   - [ ] Mettre à jour les attributs des vues

## Plan de Migration

### Phase 1 : Analyse et Préparation
1. **Révision du Code**
   - [ ] Vérifier les changements dans sale.order
   - [ ] Tester la duplication
   - [ ] Identifier les potentiels conflits

2. **Tests**
   - [ ] Créer des cas de test avec différents scénarios
   - [ ] Documenter le comportement attendu
   - [ ] Préparer des données de test

### Phase 2 : Migration
1. **Mise à Jour du Code**
   - [ ] Adapter les vues XML
   - [ ] Vérifier les dépendances
   - [ ] Optimiser la duplication si nécessaire

2. **Tests et Validation**
   - [ ] Tester avec différents types de devis
   - [ ] Vérifier les messages du chatter
   - [ ] Valider les liens entre devis

## État de la Migration
 En cours d'analyse - Migration simple requise

## Notes Importantes
- La fonctionnalité reste pertinente dans Odoo 18.0
- Les changements sont mineurs
- La logique de base reste la même
- Attention à la gestion des messages

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Adapter les vues pour Odoo 18.0
3. Mettre à jour les tests
4. Tester avec différents scénarios

## Notes de Version
- Version originale: 17.0.1.0.0
- Dernière analyse: 26/01/2025

## Points d'Attention Particuliers
1. **Performance**
   - Optimisation de la duplication
   - Gestion des grands devis
   - Impact sur la base de données

2. **Interface Utilisateur**
   - Clarté de l'assistant
   - Navigation intuitive
   - Messages informatifs

3. **Maintenance**
   - Documentation des cas spéciaux
   - Gestion des erreurs
   - Logs pour le débogage