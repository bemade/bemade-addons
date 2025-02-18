# Spécifications du module OpenWebUI Integration

## Objectif
Ce module fournit une intégration complète entre Odoo et OpenWebUI, permettant l'utilisation de modèles d'IA avancés dans diverses fonctionnalités d'Odoo. Il sert de base pour tous les modules qui souhaitent utiliser les capacités d'IA d'OpenWebUI.

## Architecture du Module

### Structure des Répertoires
```
openwebui_integration/
├── controllers/     # Contrôleurs pour les endpoints web
├── models/          # Modèles de données
├── security/        # Fichiers de sécurité et accès
├── static/          # Ressources statiques
└── views/           # Vues XML Odoo
```

## Composants Principaux

### 1. OpenWebUI Bot Mixin (`openwebui.bot.mixin`)
Mixin permettant d'ajouter des fonctionnalités de bot à n'importe quel modèle Odoo.

#### Fonctionnalités clés:
- Gestion du contexte du bot
- Génération et traitement des messages
- Gestion des réponses
- Points de personnalisation spécifiques au modèle

#### Méthodes principales:
- `_get_bot_context()`: Récupère le contexte et les paramètres du bot
- `_apply_logic()`: Applique la logique du bot à un enregistrement
- `_generate_bot_message()`: Génère le message à envoyer (à surcharger)
- `_process_bot_response()`: Traite la réponse du bot (à surcharger)

### 2. Modèle OpenWebUI (`openwebui.model`)
Gère les modèles d'IA disponibles via OpenWebUI.

#### Caractéristiques:
- Modèles par défaut: GPT-3.5 Turbo, GPT-4, Claude 2
- Identifiant unique par entreprise
- Gestion de l'état actif/inactif
- Support des modèles temporaires pour les tests

#### Contraintes de sécurité:
- Création manuelle interdite (sauf modèles temporaires)
- Modifications limitées (activation/désactivation uniquement)
- Suppression contrôlée

### 3. Configuration par Entreprise
Extension du modèle `res.company` pour la configuration OpenWebUI.

#### Paramètres configurables:
- `openwebui_enabled`: Activation de l'intégration
- `openwebui_api_url`: URL de l'API
- `openwebui_api_key`: Clé d'API
- `openwebui_verify_ssl`: Vérification du certificat SSL
- `openwebui_timeout`: Délai d'attente des requêtes
- `openwebui_default_model_id`: Modèle d'IA par défaut à utiliser
  - Sélectionnable uniquement parmi les modèles actifs
  - Utilisé comme modèle par défaut pour toutes les requêtes IA
  - Peut être surchargé au niveau des modules spécifiques

#### Fonctionnalités de gestion:
- Test de connexion à l'API
- Synchronisation des modèles disponibles
- Gestion des modèles par entreprise

## Sécurité et Gestion des Erreurs

### Sécurité
- Authentification API via clé
- Vérification SSL configurable
- Contrôle d'accès par entreprise
- Protection contre la création/modification non autorisée

### Gestion des Erreurs
- Validation des paramètres de connexion
- Gestion des timeouts
- Traitement des erreurs API
- Validation des réponses

## Intégration et Utilisation

### Étapes d'installation
1. Installation du module via Odoo
2. Configuration des paramètres OpenWebUI dans la configuration de l'entreprise
3. Test de la connexion API
4. Synchronisation initiale des modèles

### Développement d'Extensions
1. Hériter du mixin `openwebui.bot.mixin`
2. Implémenter les méthodes de génération et traitement
3. Configurer les paramètres spécifiques au modèle
4. Gérer les réponses selon les besoins

### Maintenance
- Nettoyage périodique des modèles temporaires
- Surveillance des timeouts et erreurs
- Mise à jour des modèles disponibles

## Dépendances
- Module `mail` d'Odoo
- Accès à une instance OpenWebUI
- Python 3.x avec support SSL

## Notes Techniques
- Utilisation de requêtes HTTP asynchrones
- Cache des réponses API pour optimisation
- Support multi-entreprises
- Extensible pour différents cas d'usage