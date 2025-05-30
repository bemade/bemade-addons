# Migration vers Odoo 18.0 - bemade_hide_decimal_on_unit

## Description
Module qui cache les décimales sur les quantités lorsqu'elles sont entières dans les rapports de vente et d'achat.

## Analyse Technique

### Fonctionnalités Actuelles
1. **Modification des Rapports**
   - Rapport de vente (`sale.report_saleorder_document`)
   - Rapport de devis d'achat (`purchase.report_purchasequotation_document`)
   - Rapport de commande d'achat (`purchase.report_purchaseorder_document`)

2. **Comportement**
   - Vérifie si la quantité est entière (`int(qty) == qty`)
   - Affiche sans décimale si entière (`'%.0f' % qty`)
   - Affiche avec décimales si non entière

### Changements dans Odoo 18.0

1. **Architecture des Rapports**
   - Les templates QWeb sont toujours utilisés
   - Les classes CSS `text-right` sont maintenant `text-end`
   - Les identifiants des rapports restent les mêmes

2. **Modifications Nécessaires**
   - [ ] Mettre à jour les classes CSS
   - [ ] Vérifier la compatibilité des expressions XPath
   - [ ] Valider les héritages de templates

## Plan de Migration

### Phase 1 : Analyse et Préparation
1. **Révision du Code**
   - [ ] Vérifier les templates de base dans Odoo 18.0
   - [ ] Identifier les changements dans les classes CSS
   - [ ] Tester les expressions XPath

2. **Tests**
   - [ ] Créer des cas de test avec différentes quantités
   - [ ] Documenter le comportement attendu
   - [ ] Préparer des exemples de rapports

### Phase 2 : Migration
1. **Mise à Jour des Vues**
   - [ ] Adapter les classes CSS (`text-right` → `text-end`)
   - [ ] Mettre à jour les expressions XPath si nécessaire
   - [ ] Vérifier les groupes de sécurité

2. **Tests et Validation**
   - [ ] Tester avec des quantités entières
   - [ ] Tester avec des quantités décimales
   - [ ] Vérifier l'affichage sur différents formats de rapport

## État de la Migration
 En cours d'analyse - Migration simple requise

## Notes Importantes
- La fonctionnalité reste pertinente dans Odoo 18.0
- Les changements sont principalement cosmétiques (CSS)
- La logique de base reste la même
- Les tests visuels seront importants

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Adapter les vues pour Odoo 18.0
3. Mettre à jour les tests
4. Tester avec différents formats de rapport

## Notes de Version
- Version originale: 17.0.0.1.1
- Dernière analyse: 26/01/2025