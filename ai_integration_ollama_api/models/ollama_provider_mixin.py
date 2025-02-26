from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import logging
import json

_logger = logging.getLogger(__name__)

class OllamaProviderMixin(models.AbstractModel):
    """Mixin model that provides Ollama-specific configuration parameters.
    
    This mixin is designed to be inherited by models that need to interact with
    the Ollama AI provider. It provides all the necessary fields and methods
    for configuring and interacting with Ollama's API.
    
    Key Features:
    - Provider type selection and validation
    - Context window configuration
    - Advanced sampling parameters (temperature, top-k, top-p)
    - Token generation controls
    
    Technical Details:
    - Inherits from ai.generation.params for base AI generation parameters
    - Implements Ollama-specific API parameters
    - Provides default values optimized for general use cases
    """
    _name = 'ollama.provider.mixin'
    _description = 'Ollama Provider Configuration Mixin'
    _inherit = ['ai.generation.params']

    # Model Parameters
    model_name = fields.Char(
        string='Model Name',
        help='Name of the Ollama model to use (e.g. llama2, mistral, codellama)',
        required=True,
        default='deepseek-r1:32b')
        
    # Context Window Configuration
    num_ctx = fields.Integer(
        string='Context Length',
        help='Maximum number of tokens to consider for context. A larger context window allows '
             'the model to access more historical information but requires more memory. '
             'Range: [0 - 32768].',
        default=8192)
        
    # Generation Parameters
    temperature = fields.Float(
        string='Temperature',
        help='Controls randomness in the output. Higher values make the output more random, '
             'while lower values make it more focused and deterministic. '
             'Range: [0.0 - 2.0]',
        default=0.7)
        
    top_p = fields.Float(
        string='Top P (Nucleus Sampling)',
        help='Limits the cumulative probability of tokens to sample from. Only the most likely '
             'tokens with total probability mass of top_p are considered. '
             'Range: [0.0 - 1.0].',
        default=0.9)
    
    top_k = fields.Integer(
        string='Top K',
        help='Limits the cumulative probability of tokens to sample from. Only the top K '
             'most likely tokens are considered for sampling at each step. '
             'Range: [1 - 100].',
        default=40)
    
    min_p = fields.Float(
        string='Min P',
        help='Sets a minimum probability threshold for token selection. Range: [0.0 - 1.0].',
        default=0.05,
        digits=(3, 2))
    
    repeat_penalty = fields.Float(
        string='Repeat Penalty',
        help='Penalty for repeating tokens. Range: [1.0 - 2.0]. Higher values make repetition less likely.',
        default=1.1,
        digits=(3, 2))
    
    # Advanced Configuration
    stop_sequences = fields.Char(
        string='Stop Sequences',
        help='Comma-separated list of sequences where the model should stop generating further tokens.')
    
    num_predict = fields.Integer(
        string='Maximum Tokens',
        help='Maximum number of tokens to predict. Set to -1 for unlimited.',
        default=2048)
    
    repeat_last_n = fields.Integer(
        string='Repeat Last N',
        help='Sets the context window for repeat penalty. Range: [0 - 4096]. Default is 64, 0 disables.',
        default=64
    )
    
    def generate_text(self, prompt, **kwargs):
        """Generate text using the Ollama API.
        
        Args:
            prompt (str): The prompt to generate text from
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            str: The generated text
        """
        self.ensure_one()
        
        # Prepare the request
        url = f"{self.host}/api/generate"
        
        # Build the request data
        data = {
            'model': self.model_name,
            'prompt': prompt,
            'stream': False,
            'num_ctx': self.num_ctx,
            'temperature': self.temperature,
            'top_k': self.top_k,
            'top_p': self.top_p,
            'repeat_penalty': self.repeat_penalty,
            'repeat_last_n': self.repeat_last_n,
            'num_predict': self.num_predict,
            'min_p': self.min_p,
            'seed': self.seed,
            'num_gpu': self.num_gpu,
            'num_thread': self.num_thread,
            'mirostat': int(self.mirostat),
            'mirostat_tau': self.mirostat_tau,
            'mirostat_eta': self.mirostat_eta,
            'num_batch': self.num_batch,
            'num_keep': self.num_keep,
            'tfs_z': self.tfs_z,
            'skip_special_tokens': self.skip_special_tokens
        }
        
        # Add any additional parameters
        if kwargs:
            data.update(kwargs)
            
        # Make the request
        try:
            _logger = logging.getLogger(__name__)
            _logger.info("Sending request to Ollama API with data: %s", data)
            
            response = requests.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            
            # Log the raw response
            _logger.info("Raw API response: %s", response.text)
            
            # Parse the response
            result = response.json()
            response_text = result.get('response', '')
            
            # Si la réponse est une chaîne JSON, la parser
            try:
                if isinstance(response_text, str):
                    parsed_response = json.loads(response_text)
                    _logger.info("Parsed nested JSON response: %s", parsed_response)
                    return parsed_response
                else:
                    _logger.info("Direct response: %s", response_text)
                    return response_text
            except json.JSONDecodeError:
                # Si ce n'est pas du JSON valide, retourner le texte tel quel
                _logger.info("Non-JSON response: %s", response_text)
                return response_text
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to generate text: %s') % str(e))
    
    # Advanced Generation Parameters
    seed = fields.Integer(
        string='Random Seed',
        help='Sets the random seed for generation. Range: [0 - 2147483647]. Use 0 for random.',
        default=0)
    
    num_gpu = fields.Integer(
        string='Number of GPUs',
        help='Number of GPUs to use for generation. Range: [0 - 8]. 0 means CPU only.',
        default=1)
    
    num_thread = fields.Integer(
        string='Number of Threads',
        help='Number of CPU threads to use for generation. Range: [1 - 32].',
        default=8)
    
    mirostat = fields.Selection([
        ('0', 'Disabled'),
        ('1', 'Mirostat'),
        ('2', 'Mirostat 2.0')],
        string='Mirostat Mode',
        help='Enable Mirostat sampling for controlling perplexity',
        default='0')
    
    mirostat_tau = fields.Float(
        string='Mirostat Tau',
        help='Mirostat target entropy. Range: [0.0 - 10.0].',
        default=5.0,
        digits=(3, 2))
    
    mirostat_eta = fields.Float(
        string='Mirostat Eta',
        help='Mirostat learning rate. Range: [0.0 - 1.0].',
        default=0.1,
        digits=(3, 2))
    
    # Ollama-specific Response Control
    
    tfs_z = fields.Float(
        string='Tail Free Sampling Z',
        help='Tail free sampling parameter. Range: [0.0 - 2.0]. Higher value = more focused.',
        default=1.0,
        digits=(3, 2))
    
    # System Settings
    num_batch = fields.Integer(
        string='Batch Size',
        help='Number of prompts to batch together',
        default=8)
    
    num_keep = fields.Integer(
        string='Keep Last N Tokens',
        help='Number of tokens to keep from initial prompt',
        default=0)
    
    skip_special_tokens = fields.Boolean(
        string='Skip Special Tokens',
        help='Skip special tokens in generation',
        default=True)
    
    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'provider_type' in fields_list:
            defaults['provider_type'] = 'ollama'
        if 'host' in fields_list and not defaults.get('host'):
            defaults['host'] = 'http://localhost:11434'
        return defaults
    
    def _get_provider_options(self):
        """Get Ollama-specific options for API calls."""
        self.ensure_one()
        options = {
            'model': self.model_name,
            'temperature': self.temperature,
            'num_ctx': self.num_ctx,
            'num_predict': self.num_predict,
            'top_k': self.top_k,
            'top_p': self.top_p,
            'min_p': self.min_p,
            'repeat_penalty': self.repeat_penalty,
            'repeat_last_n': self.repeat_last_n,
            'seed': self.seed,
            'num_gpu': self.num_gpu,
            'num_thread': self.num_thread,
            'mirostat': int(self.mirostat),
            'mirostat_tau': self.mirostat_tau,
            'mirostat_eta': self.mirostat_eta,
            'num_batch': self.num_batch,
            'num_keep': self.num_keep,
            'tfs_z': self.tfs_z,
            'skip_special_tokens': self.skip_special_tokens,
            'stream': False
        }
        
        if self.stop_sequences:
            options['stop'] = [
                seq.strip()
                for seq in self.stop_sequences.split(',')
                if seq.strip()
            ]
            
        return options
