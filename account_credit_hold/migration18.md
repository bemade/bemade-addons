# Migration vers Odoo 18.0 - Module account_credit_hold

## Fonctionnalités
- Ajoute un champ "Place on Credit Hold" sur les lignes de suivi de compte (account_followup.followup.line)
- Ajoute des champs et fonctionnalités sur les partenaires:
  - postpone_hold_until: Date de report du blocage
  - hold_bg: Champ technique pour le statut de blocage
  - on_hold: État calculé du blocage de crédit
- Bloque la confirmation des commandes de vente si le client est en blocage de crédit
- Ajoute des indicateurs visuels (ruban rouge) sur:
  - Commandes de vente
  - Fiches partenaires
  - Transferts de stock
- Ajoute des boutons pour mettre/lever le blocage de crédit dans la vue de suivi des comptes

## Analyse pour la Migration

### Dépendances
- sale
- account_followup
- stock

### Changements Techniques Requis
1. Mettre à jour la version dans __manifest__.py vers 18.0
2. Vérifier la compatibilité des vues XML avec Odoo 18.0
3. Vérifier si des changements dans l'API account_followup en 18.0

### Points d'Attention
1. Le module utilise l'héritage de vues et de modèles standard d'Odoo:
   - account_followup.followup.line
   - res.partner
   - sale.order
   - stock.picking
   - account.followup.report

2. Fonctionnalités critiques à tester après migration:
   - Calcul automatique du statut on_hold
   - Blocage de la confirmation des commandes
   - Nettoyage automatique des reports de blocage expirés (@api.autovacuum)
   - Affichage correct des rubans d'avertissement
   - Propagation du statut hold aux contacts liés (commercial_partner_id)

3. Implémentation Technique:
   - Utilisation de champs computed avec store=True et compute_sudo=True
   - Mécanisme de nettoyage automatique via @api.autovacuum
   - Héritage de _execute_followup_partner pour automatisation du hold
   - Messages de chatter automatiques lors des changements de statut

4. Points Spécifiques aux Vues:
   - Utilisation du widget web_ribbon pour les indicateurs visuels
   - Boutons conditionnels dans la vue de suivi des comptes
   - Champs invisibles pour la logique d'affichage (hold_bg, on_hold)
   - Groupes de sécurité sur le champ postpone_hold_until

## Questions et Considérations

1. Vérifier si Odoo 18.0 n'a pas introduit des fonctionnalités natives similaires dans account_followup:
   - Système de blocage automatique des clients
   - Gestion des périodes de grâce
   - Indicateurs visuels de blocage

2. Points à valider:
   - La structure des vues héritées est-elle identique en 18.0?
   - Les champs related et computed fonctionnent-ils de la même manière?
   - Le système de suivi des comptes (account_followup) a-t-il évolué?
   - Le décorateur @api.autovacuum est-il toujours supporté?
   - Le widget web_ribbon utilise-t-il toujours la même API?

3. Considérations d'Architecture:
   - Le mécanisme de propagation du statut hold via commercial_partner_id est-il optimal?
   - Possibilité de simplifier la logique de calcul du statut hold?
   - Pertinence de stocker le champ hold_bg vs calcul à la demande

4. Alternatives Potentielles:
   - Utiliser le système de credit limit natif d'Odoo avec des règles personnalisées?
   - Intégrer avec le système de blocage des partenaires d'Odoo?
   - Utiliser les étapes de facturation (invoice_status) plutôt qu'un champ séparé?

## Alternatives Natives Odoo 18.0

### Système de Crédit Natif
1. Odoo 18.0 inclut des fonctionnalités natives de gestion de crédit:
   - Champ `credit_limit` sur res.partner
   - Configuration du blocage au niveau de la société
   - Règles de blocage basées sur:
     - Montant de crédit maximum
     - Factures échues
     - Âge des factures

2. Possibilités d'utilisation des fonctionnalités natives:
   - Utiliser `credit_limit` au lieu de `on_hold`
   - Configurer les règles de blocage dans la configuration de la comptabilité
   - Utiliser les notifications natives de dépassement de crédit

### Améliorations Possibles
1. Intégration avec le système natif:
   - Synchroniser notre `on_hold` avec le système natif de blocage
   - Utiliser les API natives de vérification de crédit
   - Conserver uniquement les fonctionnalités non disponibles nativement

2. Simplification du code:
   - Remplacer les champs custom par des champs natifs quand possible
   - Utiliser le système d'alertes natif pour les rubans
   - Intégrer avec le système de workflow natif

## Recommandations pour la Migration

### Approche "Vanilla First"
1. Évaluer chaque fonctionnalité custom:
   - Est-elle disponible nativement dans Odoo 18.0?
   - Peut-elle être remplacée par une configuration native?
   - Le besoin business existe-t-il toujours?

2. Prioriser l'utilisation des fonctionnalités natives:
   - Système de crédit natif
   - Système de workflow natif
   - API de notification standard
   - Widgets standards de l'interface

### Modifications Techniques Recommandées
1. Remplacer les attributs obsolètes:
   - Supprimer les `attrs` dans les vues (Odoo 16.0+)
   - Utiliser `list` au lieu de `tree` (Odoo 17.0+)
   - Adapter les widgets aux nouvelles conventions

2. Optimisation des performances:
   - Utiliser les indexes de base de données appropriés
   - Optimiser les recherches et calculs
   - Implémenter le lazy loading quand possible

### Plan de Test Approfondi
1. Tests fonctionnels:
   - Validation du comportement avec le système natif
   - Tests de régression sur les fonctionnalités custom
   - Vérification des performances

2. Tests d'intégration:
   - Interaction avec le workflow de vente
   - Synchronisation avec la comptabilité
   - Comportement avec les autres modules

## État de la Migration
⚪ En analyse préliminaire

## Plan de Migration

### Étape 1: Analyse des Changements Odoo 18.0
- [ ] Examiner les changements dans account_followup
- [ ] Vérifier les nouvelles fonctionnalités de gestion de crédit
- [ ] Analyser les modifications des vues héritées

### Étape 2: Adaptation Technique
- [ ] Mise à jour du manifeste
- [ ] Vérification de la compatibilité des décorateurs
- [ ] Adaptation des vues XML si nécessaire
- [ ] Test des champs computed et related

### Étape 3: Tests Fonctionnels
- [ ] Validation du mécanisme de hold
- [ ] Test de la propagation aux contacts
- [ ] Vérification des nettoyages automatiques
- [ ] Test des indicateurs visuels

### Étape 4: Optimisation
- [ ] Évaluation des alternatives natives
- [ ] Simplification potentielle du code
- [ ] Amélioration des performances

## Notes de Version
- Version originale: 17.0.1.1.1
- Dernière analyse: 26/01/2025

## Fonctionnalités Natives dans Odoo 18.0

Odoo 18.0 inclut nativement plusieurs fonctionnalités de gestion du crédit :

1. **Gestion des Limites de Crédit**
   - Champ `credit_limit` sur les partenaires
   - Champ `use_partner_credit_limit` pour activer/désactiver par partenaire
   - Configuration globale `account_use_credit_limit` au niveau de la société
   - Champ `credit` pour le total des créances
   - Champ `trust` pour le niveau de confiance du débiteur

2. **Visibilité et Contrôle**
   - Champ `show_credit_limit` basé sur la configuration de la société
   - Groupes de sécurité pour la gestion des limites de crédit

### Différences avec Notre Module

1. **Fonctionnalités à Migrer**
   - [ ] Indicateurs visuels spécifiques pour les clients en dépassement
   - [ ] Blocage automatique des commandes en dépassement
   - [ ] Workflow d'approbation personnalisé

2. **Fonctionnalités à Adapter**
   - [ ] Utiliser les champs natifs plutôt que nos champs customs
   - [ ] Intégrer nos règles de blocage avec le système natif
   - [ ] Adapter les rapports et vues pour utiliser les champs natifs

## Plan de Migration

### Phase 1 : Préparation
1. **Analyse des Données**
   - [ ] Identifier les clients avec des limites de crédit
   - [ ] Mapper les champs actuels vers les champs natifs
   - [ ] Lister les règles de blocage personnalisées

2. **Configuration**
   - [ ] Activer la gestion du crédit dans la configuration de la société
   - [ ] Configurer les groupes de sécurité appropriés
   - [ ] Préparer les scripts de migration des données

### Phase 2 : Migration
1. **Migration des Données**
   - [ ] Transférer les limites de crédit vers le champ natif
   - [ ] Migrer les configurations de blocage
   - [ ] Mettre à jour les vues et rapports

2. **Développement**
   - [ ] Adapter le code de blocage des commandes
   - [ ] Implémenter les indicateurs visuels manquants
   - [ ] Ajouter les fonctionnalités spécifiques non disponibles nativement

### Phase 3 : Tests
1. **Validation Fonctionnelle**
   - [ ] Tester les limites de crédit
   - [ ] Vérifier le blocage des commandes
   - [ ] Valider les workflows d'approbation

2. **Tests d'Intégration**
   - [ ] Tester avec les autres modules
   - [ ] Vérifier la compatibilité avec les processus existants

## État de la Migration
🟡 En cours d'analyse - Utilisation partielle des fonctionnalités natives

## Notes Importantes
- La gestion du crédit est maintenant une fonctionnalité native d'Odoo
- Certaines fonctionnalités spécifiques devront être maintenues
- L'approche recommandée est d'utiliser au maximum les fonctionnalités natives et de ne conserver que les extensions nécessaires

## Prochaines Étapes
1. Valider l'approche avec l'équipe
2. Créer les scripts de migration des données
3. Développer les fonctionnalités manquantes
4. Planifier la formation des utilisateurs