from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_procurement_values(self):
        """
        Override to include move_dest_ids for mts_else_mto rules.
        
        The standard Odoo code only includes move_dest_ids when:
            self.procure_method == "make_to_order"
        
        However, with mts_else_mto rules:
        1. _adjust_procure_method() sets move.procure_method = 'make_to_stock'
           (because mts_else_mto is not in ['make_to_stock', 'make_to_order'])
        2. _action_confirm() still creates procurement
           (because it checks rule.procure_method == 'mts_else_mto')
        3. But move_dest_ids is NOT included (because move.procure_method != 'make_to_order')
        4. Result: Child MOs created without parent link
        
        This fix checks BOTH the move's procure_method AND the rule's procure_method
        to determine if move_dest_ids should be included.
        """
        res = super()._prepare_procurement_values()
        
        # If move_dest_ids was already set by super(), we're done
        if res.get('move_dest_ids'):
            return res
        
        # Check if the rule has mts_else_mto and we should include move_dest_ids
        # This handles the case where:
        # - move.procure_method = 'make_to_stock' (set by _adjust_procure_method)
        # - rule.procure_method = 'mts_else_mto' (the actual rule setting)
        # - Procurement WILL be created (by _action_confirm logic)
        # - So we SHOULD include move_dest_ids for parent-child linking
        if self.rule_id and self.rule_id.procure_method == 'mts_else_mto':
            res['move_dest_ids'] = self
        
        return res
