from odoo import models, fields, api
from datetime import datetime, timedelta

class OllamaModelStats(models.Model):
    """Tracks and stores daily usage statistics for Ollama AI models.
    
    This model maintains detailed daily statistics for each Ollama model,
    including request counts, token usage, response times, and error rates.
    It inherits from ai.model.stats for base statistics functionality.
    
    Key Features:
    - Daily usage tracking per model
    - Performance metrics collection
    - Error rate monitoring
    - Version tracking for model updates
    
    Technical Details:
    - One stat entry per model per day (enforced by SQL constraint)
    - Automatic version tracking from Ollama API
    - Aggregated statistics calculation
    - Ordered by date for easy historical analysis
    """
    _name = 'ollama.model.stats'
    _description = 'Ollama Model Usage Statistics'
    _inherit = ['ai.model.stats']
    _order = 'date desc'  # Most recent stats first

    model_id = fields.Many2one('ai.model', string='Model', required=True, ondelete='cascade')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    request_count = fields.Integer(string='Number of Requests', default=0)
    token_count = fields.Integer(string='Total Tokens', default=0)
    avg_response_time = fields.Float(string='Average Response Time (ms)', digits=(10, 2), default=0)
    error_count = fields.Integer(string='Number of Errors', default=0)
    version = fields.Char(string='Model Version', help='Version of the model when stats were recorded')

    _sql_constraints = [
        ('unique_model_date', 'unique(model_id, date)', 'Only one stat entry per model per day is allowed.')
    ]

    def _update_stats(self, model, tokens, response_time, error=False):
        """Update daily statistics for a specific model.
        
        This method handles the creation or update of daily statistics entries.
        It maintains running averages and cumulative counts for various metrics.
        
        Args:
            model (ai.model): The model record being tracked
            tokens (int): Number of tokens in the current request
            response_time (float): Response time in milliseconds
            error (bool): Whether this request resulted in an error
            
        Technical Notes:
            - Creates new stat entry if none exists for today
            - Updates running averages for response time
            - Fetches and stores model version from Ollama API
            - Maintains cumulative counts for requests and errors
        """
        today = fields.Date.context_today(self)
        stats = self.search([
            ('model_id', '=', model.id),
            ('date', '=', today)
        ])

        if not stats:
            # Get model version
            version = self.env['ai.provider.ollama']._get_model_info(
                model.provider_instance_id, 
                model.identifier
            ).get('details', {}).get('sha256', '')[:8]  # First 8 chars of SHA

            stats = self.create({
                'model_id': model.id,
                'date': today,
                'version': version
            })

        # Update statistics
        new_count = stats.request_count + 1
        new_tokens = stats.token_count + tokens
        new_time = ((stats.avg_response_time * stats.request_count) + response_time) / new_count
        new_errors = stats.error_count + (1 if error else 0)

        stats.write({
            'request_count': new_count,
            'token_count': new_tokens,
            'avg_response_time': new_time,
            'error_count': new_errors
        })

    @api.model
    def get_model_stats(self, model_id, days=30):
        """Get statistics for a model over the specified number of days."""
        start_date = fields.Date.today() - timedelta(days=days)
        stats = self.search([
            ('model_id', '=', model_id),
            ('date', '>=', start_date)
        ])
        
        return {
            'daily_stats': [{
                'date': stat.date,
                'requests': stat.request_count,
                'tokens': stat.token_count,
                'response_time': stat.avg_response_time,
                'errors': stat.error_count,
                'version': stat.version
            } for stat in stats],
            'summary': {
                'total_requests': sum(stat.request_count for stat in stats),
                'total_tokens': sum(stat.token_count for stat in stats),
                'avg_response_time': sum(stat.avg_response_time * stat.request_count for stat in stats) / 
                                   (sum(stat.request_count for stat in stats) if stats else 1),
                'total_errors': sum(stat.error_count for stat in stats),
                'versions_used': list(set(stat.version for stat in stats if stat.version))
            }
        }
