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
- **Héritage**: `mail.thread`, `ai.base.mixin`
- **Champs principaux**:
  - `name`: Nom de l'instance (ex: "OpenWebUI Production", "Ollama Local")
  - `provider_id`: Fournisseur associé
  - `provider_type`: Type de fournisseur (extensible par modules)
  - `active`: État actif/inactif
- **Validation**:
  - Vérifie la présence d'au moins un module fournisseur installé

### 3. AI Model (`ai.model`)
- **Description**: Modèles d'IA disponibles
- **Champs principaux**:
  - `name`: Nom du modèle
  - `identifier`: Identifiant technique (ex: gpt-3.5-turbo, mistral-7b)
  - `provider_instance_id`: Instance du fournisseur (cascade)
  - `provider_type`: Type de fournisseur (relié à l'instance)
  - `active`: État actif/inactif
  - `sequence`: Ordre d'affichage
- **Validation**:
  - Vérifie la présence d'au moins un module fournisseur installé

### 4. AI Generation Parameters (`ai.generation.params`)
- **Description**: Paramètres de génération pour les modèles d'IA
- **Type**: Modèle abstrait
- **Champs principaux**:
  - `temperature`: Contrôle de l'aléatoire (défaut: 0.7)
  - `repeat_penalty`: Pénalité de répétition (défaut: 1.1)
  - `max_tokens`: Nombre maximum de tokens (défaut: 2048)
  - `stop_sequences`: Séquences d'arrêt
  - `frequency_penalty`: Pénalité de fréquence (défaut: 0.0)
  - `presence_penalty`: Pénalité de présence (défaut: 0.0)

## Configuration et Interfaces

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

### 3. AI Provider Interface (`ai.provider.interface`)
- **Description**: Interface abstraite pour les fournisseurs d'IA
- **Méthodes requises**:
  - `send_message`: Envoyer un message
  - `get_models`: Obtenir la liste des modèles
  - `test_connection`: Tester la connexion

## Notes d'Implémentation

1. **Architecture Modulaire**:
   - Modules fournisseurs disponibles: `ollama_ai_integration`, `chatgpt_ai_integration`
   - Vérification de la présence d'au moins un module fournisseur avant création d'instances

2. **Héritage et Extensions**:
   - Les instances de fournisseur héritent de `mail.thread` et `ai.base.mixin`
   - Les paramètres de génération sont définis dans le modèle abstrait `ai.generation.params`

3. **Configuration Hiérarchique**:
   - Configuration globale > Paramètres société > Instance
   - Paramètres de génération personnalisables à plusieurs niveaux

4. **Sécurité et Validation**:
   - Vérifications de sécurité intégrées
   - Validation des modules requis
   - Gestion des paramètres de génération avec valeurs par défaut
