# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo import Command


class TestSOFollowersToPicking(TransactionCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test partners
        cls.partner_1 = cls.env['res.partner'].create({
            'name': 'Test Partner 1',
            'email': 'partner1@test.com',
        })
        
        cls.partner_2 = cls.env['res.partner'].create({
            'name': 'Test Partner 2', 
            'email': 'partner2@test.com',
        })
        
        cls.customer = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'customer@test.com',
        })
        
        # Create a test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
            'list_price': 100.0,
        })
        
        # Get stock locations and picking types
        cls.warehouse = cls.env['stock.warehouse'].search([], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
        cls.picking_type_out = cls.warehouse.out_type_id
        
    def test_followers_copied_to_picking_on_create(self):
        """Test that followers from sale order are copied to stock picking when created"""
        
        # Create a sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        # Add followers to the sale order
        sale_order.message_subscribe(partner_ids=[self.partner_1.id, self.partner_2.id])
        
        # Verify followers are added to sale order
        follower_partner_ids = sale_order.message_follower_ids.mapped('partner_id.id')
        self.assertIn(self.partner_1.id, follower_partner_ids)
        self.assertIn(self.partner_2.id, follower_partner_ids)
        
        # Confirm the sale order to generate picking
        sale_order.action_confirm()
        
        # Get the generated picking
        picking = self.env['stock.picking'].search([('origin', '=', sale_order.name)], limit=1)
        
        # Verify that followers from sale order are copied to picking
        picking_follower_partner_ids = picking.message_follower_ids.mapped('partner_id.id')
        self.assertIn(self.partner_1.id, picking_follower_partner_ids)
        self.assertIn(self.partner_2.id, picking_follower_partner_ids)
        
    def test_followers_copied_when_picking_created_manually(self):
        """Test that followers are copied when picking is created manually with origin"""
        
        # Create a sale order
        sale_order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        # Add followers to the sale order
        sale_order.message_subscribe(partner_ids=[self.partner_1.id])
        
        # Create a picking manually with the sale order name as origin
        picking = self.env['stock.picking'].create({
            'partner_id': self.customer.id,
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'origin': sale_order.name,
        })
        
        # Verify that followers from sale order are copied to picking
        picking_follower_partner_ids = picking.message_follower_ids.mapped('partner_id.id')
        self.assertIn(self.partner_1.id, picking_follower_partner_ids)
        
    def test_no_followers_when_no_matching_sale_order(self):
        """Test that no followers are added when there's no matching sale order"""
        
        # Create a picking with a non-existent origin
        picking = self.env['stock.picking'].create({
            'partner_id': self.customer.id,
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'origin': 'NON_EXISTENT_SO',
        })
        
        # Verify that no additional followers are added (only the default ones)
        # The picking should only have system followers, not any from a sale order
        initial_follower_count = len(picking.message_follower_ids)
        
        # Create another picking with same origin to ensure consistent behavior
        picking2 = self.env['stock.picking'].create({
            'partner_id': self.customer.id,
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'origin': 'ANOTHER_NON_EXISTENT_SO',
        })
        
        # Both pickings should have the same number of followers (system defaults only)
        self.assertEqual(len(picking.message_follower_ids), len(picking2.message_follower_ids))
        
    def test_no_followers_when_no_origin(self):
        """Test that no followers are added when picking has no origin"""
        
        # Create a sale order with followers
        sale_order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        sale_order.message_subscribe(partner_ids=[self.partner_1.id])
        
        # Create a picking without origin
        picking = self.env['stock.picking'].create({
            'partner_id': self.customer.id,
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            # No origin specified
        })
        
        # Verify that the sale order follower is not copied to the picking
        picking_follower_partner_ids = picking.message_follower_ids.mapped('partner_id.id')
        self.assertNotIn(self.partner_1.id, picking_follower_partner_ids)
        
    def test_multiple_pickings_created_together(self):
        """Test that followers are copied correctly when multiple pickings are created together"""
        
        # Create two sale orders with different followers
        sale_order_1 = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        sale_order_2 = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'order_line': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        
        # Add different followers to each sale order
        sale_order_1.message_subscribe(partner_ids=[self.partner_1.id])
        sale_order_2.message_subscribe(partner_ids=[self.partner_2.id])
        
        # Create multiple pickings at once
        pickings = self.env['stock.picking'].create([
            {
                'partner_id': self.customer.id,
                'picking_type_id': self.picking_type_out.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'origin': sale_order_1.name,
            },
            {
                'partner_id': self.customer.id,
                'picking_type_id': self.picking_type_out.id,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'origin': sale_order_2.name,
            }
        ])
        
        # Verify that each picking has the correct followers
        picking_1_followers = pickings[0].message_follower_ids.mapped('partner_id.id')
        picking_2_followers = pickings[1].message_follower_ids.mapped('partner_id.id')
        
        self.assertIn(self.partner_1.id, picking_1_followers)
        self.assertNotIn(self.partner_2.id, picking_1_followers)
        
        self.assertIn(self.partner_2.id, picking_2_followers)
        self.assertNotIn(self.partner_1.id, picking_2_followers)
