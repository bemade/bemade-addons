# Migration vers Odoo 18.0 - bemade_time_off_follower

## Description
Module qui permet d'ajouter un abonné alternatif qui recevra une copie des communications pendant les congés d'un employé.

## Analyse Technique

### Fonctionnalités Actuelles
1. **Gestion des Abonnés Alternatifs**
   - Champ pour définir l'abonné alternatif
   - Notification automatique pendant les congés
   - Gestion des destinataires des messages

2. **Modèles Modifiés**
   - `hr.leave` : Ajout du champ alternate_follower_id
   - `mail.thread` : Surcharge de _notify_get_recipients
   - Intégration avec le système de messagerie

3. **Logique de Notification**
   - Vérification des congés en cours
   - Ajout des abonnés alternatifs
   - Gestion des doublons

### Changements dans Odoo 18.0

1. **Architecture Mail/HR**
   - Le système de notification reste stable
   - Les congés fonctionnent de la même manière
   - L'API de messagerie est similaire

2. **Modifications Nécessaires**
   - [ ] Vérifier la compatibilité avec le nouveau système de messagerie
   - [ ] Valider la méthode _notify_get_recipients
   - [ ] Optimiser la recherche des congés

## Plan de Migration

### Phase 1 : Analyse et Préparation
1. **Révision du Code**
   - [ ] Vérifier les changements dans l'API de messagerie
   - [ ] Tester les notifications
   - [ ] Identifier les potentiels conflits

2. **Tests**
   - [ ] Créer des cas de test avec différents scénarios
   - [ ] Documenter le comportement attendu
   - [ ] Préparer des données de test

### Phase 2 : Migration
1. **Mise à Jour du Code**
   - [ ] Adapter le code Python
   - [ ] Vérifier les dépendances
   - [ ] Optimiser les requêtes si nécessaire

2. **Tests et Validation**
   - [ ] Tester avec différents types de congés
   - [ ] Vérifier les notifications
   - [ ] Valider la gestion des abonnés

## État de la Migration
 En cours d'analyse - Migration simple requise

## Notes Importantes
- La fonctionnalité reste pertinente dans Odoo 18.0
- Les changements sont mineurs
- La logique de base reste la même
- Attention à la performance des requêtes

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Vérifier les changements dans l'API de messagerie
3. Mettre à jour les tests
4. Tester avec différents scénarios

## Notes de Version
- Version originale: 17.0.0.0.3
- Dernière analyse: 26/01/2025

## Points d'Attention Particuliers
1. **Performance**
   - Optimisation des recherches
   - Gestion des notifications en masse
   - Impact sur les grands volumes

2. **Fiabilité**
   - Gestion des erreurs
   - Validation des abonnements
   - Cohérence des données

3. **Maintenance**
   - Documentation du comportement
   - Gestion des cas spéciaux
   - Logs pour le débogage