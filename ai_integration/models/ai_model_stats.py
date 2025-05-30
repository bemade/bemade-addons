from odoo import models, fields, api
from datetime import datetime, timedelta

class AIModelStats(models.Model):
    _name = 'ai.model.stats'
    _description = 'AI Model Usage Statistics'
    _order = 'date desc'

    @api.model
    def _has_provider_modules(self):
        """Check if any AI provider modules are installed."""
        modules = ['ollama_ai_integration', 'chatgpt_ai_integration']
        return any(self.env['ir.module.module'].search([('name', 'in', modules), ('state', '=', 'installed')]))

    @api.model
    def default_get(self, fields_list):
        """Override default_get to prevent creation if no provider modules are installed."""
        if not self._has_provider_modules():
            raise UserError(_('No AI provider modules are installed. Please install at least one provider module (e.g., Ollama or ChatGPT) before creating model statistics.'))
        return super().default_get(fields_list)

    model_id = fields.Many2one('ai.model', string='Model', required=True, ondelete='cascade')
    provider_instance_id = fields.Many2one(
        related='model_id.provider_instance_id', 
        string='Provider Instance',
        store=True)
        
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    request_count = fields.Integer(string='Number of Requests', default=0)
    token_count = fields.Integer(string='Total Tokens', default=0)
    avg_response_time = fields.Float(string='Average Response Time (ms)', digits=(10, 2), default=0)
    error_count = fields.Integer(string='Number of Errors', default=0)
    version = fields.Char(string='Model Version', help='Version of the model when stats were recorded')

    _sql_constraints = [
        ('unique_model_date', 'unique(model_id, date)', 'Only one stat entry per model per day is allowed.')
    ]

    def _update_stats(self, model, tokens, response_time, error=False, version=None):
        """Update statistics for a model."""
        today = fields.Date.context_today(self)
        stats = self.search([
            ('model_id', '=', model.id),
            ('date', '=', today)
        ])

        if not stats:
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
            'error_count': new_errors,
            'version': version or stats.version  # Update version if provided
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
