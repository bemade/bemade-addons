from odoo import models, fields, api


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    requisition_id = fields.Many2one(
        comodel_name="purchase.requisition",
        string="Agreement",
        store=True,
        index=True,
        compute="_compute_requisition_id",
        inverse="_inverse_requisition_id",
    )

    requisition_line_id = fields.Many2one(
        comodel_name="purchase.requisition.line",
        string="Requisition Line",
        compute="_compute_requisition_line_id",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create purchase order lines and set price from requisition if applicable.
        
        Args:
            vals_list (list): List of values to create purchase order lines
            
        Returns:
            recordset: Created purchase order lines
        """
        res = super().create(vals_list)
        for line in res.filtered("requisition_id"):
            line.price_unit = line.requisition_line_id.price_unit
        return res

    def _compute_price_unit_and_date_planned_and_name(self):
        """Compute the price unit, date planned and name for purchase order lines.
        
        This method extends the standard computation by:
        1. Setting prices from requisition lines when applicable
        2. Handling lines without requisition based on customer agreements
        3. Falling back to basic computation for lines without matching agreements
        """
        # Only process lines with products
        lines_with_product = self.filtered('product_id')
        if not lines_with_product:
            return
            
        super(PurchaseOrderLine, lines_with_product)._compute_price_unit_and_date_planned_and_name()
        
        # Process lines with requisition
        po_lines_with_requisition = lines_with_product.filtered("requisition_id")
        for line in po_lines_with_requisition:
            if line.requisition_line_id:
                line.price_unit = line.requisition_line_id.price_unit
                
        # Process lines without requisition
        po_lines_without_requisition = lines_with_product - po_lines_with_requisition
        to_compute_basic = self.env["purchase.order.line"]
        
        for line in po_lines_without_requisition:
            po_agreement_customers = line.order_id.requisition_id.customer_ids
            customer = line._get_customer()
            if po_agreement_customers and customer and customer not in po_agreement_customers:
                to_compute_basic |= line
                
        if to_compute_basic:
            # Call the base method directly on the filtered recordset
            super(PurchaseOrderLine, to_compute_basic)._compute_price_unit_and_date_planned_and_name()

    @api.depends("requisition_id", "product_id")
    def _compute_requisition_line_id(self):
        """Compute the requisition line associated with this purchase order line.
        
        For each purchase order line with a requisition, find the matching
        requisition line based on the product using a search domain for better
        performance. Takes the first matching line if multiple exist.
        """
        RequisitionLine = self.env['purchase.requisition.line']
        for line in self:
            if not line.requisition_id or not line.product_id:
                line.requisition_line_id = False
                continue
                
            domain = [
                ('requisition_id', '=', line.requisition_id.id),
                ('product_id', '=', line.product_id.id)
            ]
            candidates = RequisitionLine.search(domain, limit=1)
            line.requisition_line_id = candidates

    def _get_vendor_domain(self, line):
        """Get domain for vendor matching.
        
        Args:
            line: The purchase order line
            
        Returns:
            list: Domain list for vendor conditions
        """
        return [
            "|",
            ("requisition_id.vendor_id", "=", line.order_id.partner_id.id),
            (
                "requisition_id.vendor_id.commercial_partner_id",
                "=",
                line.order_id.partner_id.id,
            ),
        ]

    def _get_basic_domain(self, line, order_date):
        """Get basic domain for requisition search.
        
        Args:
            line: The purchase order line
            order_date: The order date
            
        Returns:
            list: Domain list for basic conditions
        """
        return [
            ("product_id", "=", line.product_id.id),
            ("requisition_id.state", "=", "confirmed"),
            ("requisition_id.date_start", "<=", order_date),
            ("requisition_id.date_end", ">=", order_date),
        ]

    def _get_customer_domain(self, customer):
        """Get domain for customer matching.
        
        Args:
            customer: The customer record
            
        Returns:
            list: Domain list for customer conditions
        """
        if customer:
            return [
                "|",
                ("requisition_id.customer_ids", "in", [customer.id]),
                ("requisition_id.customer_ids", "=", False),
            ]
        return [("requisition_id.customer_ids", "=", False)]

    @api.depends("product_id", "order_id.partner_id", "order_id.date_order")
    def _compute_requisition_id(self):
        """Compute the requisition_id field based on various conditions.
        This method finds the appropriate purchase requisition for the line by:
        1. Matching the vendor
        2. Matching the product
        3. Checking date validity
        4. Checking customer applicability
        """
        for line in self:
            customer = line._get_customer()
            order_date = line.order_id.date_order
            
            # Build complete domain from components
            domain = (
                self._get_vendor_domain(line)
                + self._get_basic_domain(line, order_date)
                + self._get_customer_domain(customer)
            )

            # Search for matching requisition lines
            requisition_lines = self.env["purchase.requisition.line"].search(
                domain, order="create_date desc"
            )
            line.requisition_id = requisition_lines[0].requisition_id if requisition_lines else False

    def _get_customer(self):
        """Get the customer associated with this purchase order line.
        
        Tries to find the customer in the following order:
        1. From the linked sale order (via sale_purchase module)
        2. From the destination moves' sale order line
        
        Returns:
            res.partner: The customer record or False if not found
        """
        self.ensure_one()
        # Try to get customer from linked sale order (requires sale_purchase module)
        if hasattr(self, 'sale_order_id') and self.sale_order_id:
            return self.sale_order_id.partner_id
        
        # Fallback: try to get from destination moves' sale line
        # (group_id field was removed in Odoo 19)
        if self.move_dest_ids:
            sale_orders = self.move_dest_ids.mapped('sale_line_id.order_id')
            if len(sale_orders) == 1:
                return sale_orders.partner_id
        
        return False

    def _inverse_requisition_id(self):
        """Inverse method for requisition_id field.
        
        When the requisition_id is manually changed, recompute the price unit
        and other related fields to ensure consistency.
        """
        self._compute_price_unit_and_date_planned_and_name()

    def _find_candidate(
        self,
        product_id,
        product_qty,
        product_uom,
        location_id,
        name,
        origin,
        company_id,
        values,
    ):
        return super(
            PurchaseOrderLine, self.filtered(lambda line: not line.requisition_id)
        )._find_candidate(
            product_id,
            product_qty,
            product_uom,
            location_id,
            name,
            origin,
            company_id,
            values,
        )
