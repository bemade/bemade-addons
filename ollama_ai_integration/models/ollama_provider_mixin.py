from odoo import models, fields, api, _

class OllamaProviderMixin(models.AbstractModel):
    _name = 'ollama.provider.mixin'
    _description = 'Ollama Provider Configuration Mixin'
    _inherit = ['ai.generation.params']

    provider_type = fields.Selection(
        selection_add=[('ollama', 'Ollama')],
        ondelete={'ollama': 'cascade'})
    
    # Ollama-specific Parameters
    num_ctx = fields.Integer(
        string='Context Length',
        help='Maximum number of tokens to consider for context. Range: [0 - 32768].',
        default=4096)
    
    # Advanced Sampling Parameters
    top_k = fields.Integer(
        string='Top K',
        help='Limits the number of tokens to sample from. Range: [1 - 100].',
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
    
    repeat_last_n = fields.Integer(
        string='Repeat Last N',
        help='Sets the context window for repeat penalty. Range: [0 - 4096]. Default is 64, 0 disables.',
        default=64)
    
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
        }
        
        if self.stop_sequences:
            options['stop'] = [
                seq.strip()
                for seq in self.stop_sequences.split(',')
                if seq.strip()
            ]
            
        return options
