# Migration vers Odoo 18.0 - bemade_margin_vendor_pricelist

## Description
Module qui permet le calcul des marges de vente basées sur les listes de prix des fournisseurs, avec prise en compte du stock disponible.

## Analyse Technique

### Fonctionnalités Actuelles
1. **Calcul des Marges**
   - Calcul du prix d'achat basé sur les listes de prix fournisseurs
   - Calcul du profit brut et du pourcentage de profit
   - Prise en compte du stock disponible

2. **Modèles Modifiés**
   - `sale.order` : Ajout des champs de marge
   - `sale.order.line` : Calcul détaillé des marges
   - Hérite de `sale_stock_margin`

3. **Logique de Calcul**
   - Utilise la valorisation du stock si disponible
   - Utilise le prix fournisseur si stock manquant
   - Calcul mixte pour les commandes partiellement en stock

### Changements dans Odoo 18.0

1. **Architecture des Marges**
   - Le module `sale_margin` reste stable
   - `sale_stock_margin` conserve sa structure
   - Les champs de marge sont toujours présents

2. **Modifications Nécessaires**
   - [ ] Vérifier la compatibilité avec `sale_stock_margin`
   - [ ] Adapter les vues pour les nouvelles conventions
   - [ ] Optimiser les calculs pour la performance

## Plan de Migration

### Phase 1 : Analyse et Préparation
1. **Révision du Code**
   - [ ] Vérifier les changements dans `sale_margin`
   - [ ] Tester les calculs de marge
   - [ ] Identifier les potentiels conflits

2. **Tests**
   - [ ] Créer des cas de test avec différents scénarios
   - [ ] Documenter le comportement attendu
   - [ ] Préparer des données de test

### Phase 2 : Migration
1. **Mise à Jour du Code**
   - [ ] Adapter les méthodes de calcul si nécessaire
   - [ ] Mettre à jour les vues XML
   - [ ] Optimiser les calculs non stockés

2. **Tests et Validation**
   - [ ] Tester avec stock disponible
   - [ ] Tester sans stock disponible
   - [ ] Vérifier les calculs mixtes

## État de la Migration
 En cours d'analyse - Migration modérée requise

## Notes Importantes
- La fonctionnalité reste pertinente dans Odoo 18.0
- Les calculs de marge sont complexes
- La performance est un point d'attention
- Dépendance avec `sale_stock_margin`

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Vérifier les changements dans les modules dépendants
3. Mettre à jour les tests
4. Tester avec différents scénarios

## Notes de Version
- Version originale: 17.0.0.0.5
- Dernière analyse: 26/01/2025

## Points d'Attention Particuliers
1. **Performance**
   - Optimiser les calculs non stockés
   - Évaluer l'impact sur les vues pivot/graph
   - Considérer le stockage de certains champs

2. **Précision**
   - Maintenir la précision des calculs
   - Gérer correctement les arrondis
   - Valider les conversions d'unités

3. **Compatibilité**
   - Vérifier la compatibilité avec d'autres modules de marge
   - Tester avec différentes configurations de stock
   - Valider les scénarios multi-devise