from odoo import fields, models


MYCARRIER_STATUS_SELECTION = [
    ("queued", "Queued"),
    ("booked", "Booked"),
    ("picked_up", "Picked Up"),
    ("in_transit", "In Transit"),
    ("out_for_delivery", "Out for Delivery"),
    ("delivered", "Delivered"),
    ("canceled", "Canceled"),
    ("exception", "Exception"),
]


class StockPicking(models.Model):
    _inherit = "stock.picking"

    mycarrier_quote_id = fields.Char(string="MyCarrier Quote ID", readonly=True, copy=False)
    mycarrier_order_id = fields.Char(string="MyCarrier Order ID", readonly=True, copy=False)
    mycarrier_shipment_id = fields.Char(string="MyCarrier Shipment ID", readonly=True, copy=False)
    mycarrier_bol_url = fields.Char(string="MyCarrier BOL Link", readonly=True, copy=False)
    mycarrier_label_url = fields.Char(string="MyCarrier Label Link", readonly=True, copy=False)
    mycarrier_status = fields.Selection(
        MYCARRIER_STATUS_SELECTION,
        string="MyCarrier Status",
        readonly=True,
        copy=False,
    )
