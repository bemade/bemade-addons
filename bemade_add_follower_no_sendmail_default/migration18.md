# Migration vers Odoo 18.0 - bemade_add_follower_no_sendmail_default

## Description du module
Ce module modifie le comportement par défaut du wizard d'ajout de followers pour que l'option "Envoyer un email" soit désactivée par défaut.

## Analyse technique
- Dépendances : mail
- Modèles modifiés :
  - mail.wizard.invite : Modification de la valeur par défaut du champ send_mail à False
- Implémentation actuelle :
  - Hérite de mail.wizard.invite
  - Redéfinit uniquement le champ send_mail avec default=False

## Alternatives Natives

### Configuration Système
1. Vérifier dans Odoo 18.0 :
   - Paramètres de configuration du module mail
   - Paramètres système (ir.config_parameter)
   - Préférences utilisateur

### Approches Alternatives
1. Configuration par utilisateur :
   - Ajouter une préférence utilisateur dans res.users
   - Utiliser cette préférence comme valeur par défaut

2. Configuration par type de document :
   - Ajouter un paramètre dans les paramètres de notification par modèle
   - Permettre une configuration plus granulaire

## Recommandations pour la Migration

### Approche "Vanilla First"
1. Évaluer les alternatives natives :
   - [X] Vérifier si Odoo 18.0 a ajouté une configuration similaire
   - [ ] Explorer les nouvelles fonctionnalités de notification
   - [ ] Vérifier les paramètres de notification par défaut

2. Si aucune alternative native n'existe :
   - [ ] Considérer l'ajout d'une configuration système
   - [ ] Implémenter une solution plus flexible (par utilisateur ou par type de document)

### Modifications Techniques
1. Si le module est conservé :
   - [ ] Mettre à jour la version dans __manifest__.py
   - [ ] Vérifier la compatibilité de l'héritage du wizard
   - [ ] Vérifier si le champ send_mail existe toujours et a le même comportement
   - [ ] Adapter le code aux nouvelles conventions Odoo 18.0

2. Si migration vers une solution native :
   - [ ] Créer un module de migration pour la transition
   - [ ] Migrer les configurations existantes
   - [ ] Prévoir un plan de désactivation du module

## Fonctionnalité Native dans Odoo 18.0
✅ La fonctionnalité existe nativement dans Odoo 18.0 !

Dans le modèle `mail.wizard.invite` (`mail/wizard/mail_wizard_invite.py`), le champ `notify` est déjà défini avec `default=False` :
```python
notify = fields.Boolean('Notify Recipients', default=False)
```

## Plan de Migration

### Actions Requises
1. **Désactivation du Module** :
   - [ ] Désactiver le module avant la migration vers Odoo 18.0
   - [ ] Vérifier qu'aucun autre module ne dépend de celui-ci
   - [ ] Informer les utilisateurs que le comportement est maintenant natif

2. **Vérification** :
   - [ ] Tester le comportement natif dans Odoo 18.0
   - [ ] Confirmer que le comportement par défaut est identique
   - [ ] Documenter tout changement d'interface utilisateur

## État de la Migration
🟢 Pas de migration nécessaire - Utiliser la fonctionnalité native

## Notes Importantes
- Le comportement souhaité (notification désactivée par défaut) est maintenant le comportement standard d'Odoo 18.0
- L'interface utilisateur est similaire, utilisant un widget boolean_toggle
- Aucune personnalisation supplémentaire n'est nécessaire

## Prochaines Étapes
1. Planifier la désactivation du module
2. Informer les utilisateurs du changement
3. Retirer le module de la liste des dépendances des autres modules si nécessaire