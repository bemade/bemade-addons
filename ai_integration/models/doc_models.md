# Documentation des Modèles AI Integration

## Vue d'ensemble

Le module AI Integration fournit une infrastructure flexible pour intégrer différents fournisseurs d'IA dans Odoo. Il est conçu pour être extensible et permettre l'ajout facile de nouveaux fournisseurs.

## Modèles Principaux

### 1. AI Provider (`ai.provider`)
- **Description**: Configuration de base des fournisseurs d'IA
- **Champs principaux**:
  - `name`: Nom du fournisseur
  - `code`: Code technique unique
  - `description`: Description détaillée
  - `default_host`: Hôte par défaut
  - `active`: État actif/inactif

### 2. AI Provider Instance (`ai.provider.instance`)
- **Description**: Instance spécifique d'un fournisseur d'IA
- **Champs principaux**:
  - `name`: Nom de l'instance
  - `provider_id`: Fournisseur associé
  - `provider_type`: Type de fournisseur
  - `host`: Adresse de l'hôte
  - `api_key`: Clé API (si nécessaire)
  - `active`: État actif/inactif

### 3. AI Model (`ai.model`)
- **Description**: Modèles d'IA disponibles
- **Champs principaux**:
  - `name`: Nom du modèle
  - `identifier`: Identifiant technique
  - `provider_instance_id`: Instance du fournisseur
  - `active`: État actif/inactif

### 4. AI Model Stats (`ai.model.stats`)
- **Description**: Statistiques d'utilisation des modèles
- **Champs principaux**:
  - `model_id`: Modèle associé
  - `total_tokens`: Nombre total de tokens
  - `total_requests`: Nombre total de requêtes
  - `average_latency`: Latence moyenne

## Mixin de Base

### AI Base Mixin (`ai.base.mixin`)
- **Description**: Mixin unifié pour l'intégration IA et les paramètres de génération
- **Champs principaux**:
  - `temperature`: Contrôle de la créativité (0.0 - 2.0)
  - `top_p`: Sampling nucleus (0.0 - 1.0)
  - `max_tokens`: Limite de tokens (1 - 32768)
  - `stop_sequences`: Séquences d'arrêt
  - `timeout`: Délai d'attente (1 - 300s)
  - `retry_count`: Nombre de tentatives (0 - 5)
  - `stream_response`: Activation du streaming
- **Méthodes principales**:
  - `_get_ai_provider_instance`: Obtenir l'instance du fournisseur
  - `_get_ai_model`: Obtenir le modèle à utiliser
  - `send_ai_message`: Envoyer un message à l'IA
  - `_get_base_generation_params`: Obtenir les paramètres de génération

## Configuration

### 1. Res Config Settings
- **Description**: Paramètres de configuration globaux
- **Champs principaux**:
  - `default_provider_instance_id`: Instance de fournisseur par défaut
  - `default_model_id`: Modèle par défaut
  - `ai_batch_size`: Taille du lot pour le traitement

### 2. Res Company
- **Description**: Extensions des paramètres de société
- **Méthodes principales**:
  - `_get_default_provider_instance`: Obtenir l'instance par défaut

## Interfaces

### AI Provider Interface (`ai.provider.interface`)
- **Description**: Interface abstraite pour les fournisseurs d'IA
- **Méthodes requises**:
  - `send_message`: Envoyer un message
  - `get_models`: Obtenir la liste des modèles
  - `test_connection`: Tester la connexion

## Notes d'Implémentation

1. Tous les fournisseurs d'IA doivent implémenter `ai.provider.interface`
2. Les instances de fournisseur héritent des paramètres de génération via `ai.generation.params`
3. La configuration est hiérarchique : Global > Société > Instance
4. Les statistiques sont collectées automatiquement pour chaque modèle
