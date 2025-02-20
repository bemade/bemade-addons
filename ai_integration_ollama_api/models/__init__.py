"""Ollama AI Integration Models Package.

This package contains all the model definitions required for integrating
Ollama AI with Odoo's AI framework. The models are loaded in a specific
order to handle dependencies correctly.

Module Structure:
1. ollama_provider_mixin - Base configuration and parameter definitions
2. ollama_provider - Core Ollama API integration implementation
3. ollama_model_stats - Usage statistics and performance tracking
4. ai_provider_instance - Instance-specific configuration and management

Note: The import order is important to avoid circular dependencies.
"""

# Base Configuration
from . import ollama_provider_mixin

# Core Implementation
from . import ollama_provider
from . import ai_provider_instance

# Statistics and Monitoring
from . import ollama_model_stats

# Instance Management
from . import ai_provider_instance
