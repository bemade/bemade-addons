import json
import uuid

from odoo import _, fields, models

from .mycarrier_request import MyCarrierRequest, MyCarrierRequestError


NMFC_FREIGHT_CLASSES = [
    ("50", "50"),
    ("55", "55"),
    ("60", "60"),
    ("65", "65"),
    ("70", "70"),
    ("77.5", "77.5"),
    ("85", "85"),
    ("92.5", "92.5"),
    ("100", "100"),
    ("110", "110"),
    ("125", "125"),
    ("150", "150"),
    ("175", "175"),
    ("200", "200"),
    ("250", "250"),
    ("300", "300"),
    ("400", "400"),
    ("500", "500"),
]


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("mycarrier", "MyCarrier")],
        ondelete={"mycarrier": "set default"},
    )

    mycarrier_account_email = fields.Char(
        string="MyCarrier Account Email",
        groups="base.group_system",
        help="Email of the MyCarrier account admin. Used as the Basic Auth "
        "username against the MyCarrier Rating API.",
    )
    mycarrier_api_key = fields.Char(
        string="MyCarrier API Key",
        groups="base.group_system",
        help="API key from MyCarrier Customer Settings → Order API Key. "
        "Used as the Basic Auth password.",
    )
    mycarrier_location_id = fields.Char(
        string="MyCarrier Location ID",
        help="The MyCarrier location this carrier books from. Create one "
        "delivery.carrier record per MyCarrier location.",
    )
    mycarrier_payment_direction = fields.Selection(
        [
            ("Prepaid", "Prepaid"),
            ("Collect", "Collect"),
            ("ThirdParty", "Third Party"),
        ],
        string="Payment Direction",
        default="Prepaid",
    )
    mycarrier_weight_unit = fields.Selection(
        [("LBS", "Pounds"), ("KGS", "Kilograms")],
        string="Weight Unit",
        default="LBS",
    )
    mycarrier_measurement_unit = fields.Selection(
        [("IN", "Inches"), ("CM", "Centimeters")],
        string="Measurement Unit",
        default="IN",
    )
    mycarrier_default_commodity_class = fields.Selection(
        NMFC_FREIGHT_CLASSES,
        string="Default NMFC Class",
        default="70",
        help="Fallback freight class used when a product has no "
        "MyCarrier NMFC class configured.",
    )

    def _mycarrier_client(self):
        self.ensure_one()
        environment = "prod" if self.prod_environment else "sandbox"
        return MyCarrierRequest(
            email=self.sudo().mycarrier_account_email,
            api_key=self.sudo().mycarrier_api_key,
            environment=environment,
        )

    def _mycarrier_log(self, label, document):
        self.ensure_one()
        if not self.debug_logging:
            return
        try:
            body = json.dumps(document, indent=2, default=str)
        except (TypeError, ValueError):
            body = str(document)
        self.log_xml(body, label)

    def _mycarrier_build_rate_payload(self, order):
        self.ensure_one()
        ship_from = order.warehouse_id.partner_id or self.env.company.partner_id
        ship_to = order.partner_shipping_id
        location_id = self.mycarrier_location_id
        default_class = self.mycarrier_default_commodity_class or "70"
        commodities = []
        total_weight = 0.0
        for line in order.order_line:
            product = line.product_id
            if not product or product.type == "service" or line.is_delivery:
                continue
            qty = line.product_uom_qty or 1.0
            weight = (product.weight or 0.0) * qty
            total_weight += weight
            commodities.append(
                {
                    "commodityDescription": product.display_name,
                    "commodityClass": product.mycarrier_commodity_class
                    or default_class,
                    "commodityWeight": weight,
                    "commodityPieces": int(qty),
                    "nmfcCode": product.mycarrier_nmfc_code or "",
                }
            )
        quote_units = [
            {
                "unitType": "Pallet",
                "unitCount": max(len(commodities), 1),
                "unitLength": 48,
                "unitWidth": 40,
                "unitHeight": 48,
                "unitStackable": "No",
                "quoteCommodities": commodities,
            }
        ]
        return {
            "specVersion": "0.5",
            "type": "rating",
            "source": "odoo",
            "id": str(uuid.uuid4()),
            "direction": "outbound",
            "locationId": location_id,
            "data": {
                "weightUnit": self.mycarrier_weight_unit,
                "measurementUnit": self.mycarrier_measurement_unit,
                "paymentDirection": self.mycarrier_payment_direction,
                "serviceType": "LTL",
                "origin": self._mycarrier_address_dict(ship_from),
                "destination": self._mycarrier_address_dict(ship_to),
                "quoteUnits": quote_units,
                "totalWeight": total_weight,
            },
        }

    def _mycarrier_address_dict(self, partner):
        return {
            "companyName": partner.name or "",
            "street": partner.street or "",
            "street2": partner.street2 or "",
            "city": partner.city or "",
            "state": partner.state_id.code or "",
            "zip": partner.zip or "",
            "country": partner.country_id.code or "",
            "phone": partner.phone or "",
            "email": partner.email or "",
        }

    def _mycarrier_pick_best_rate(self, response):
        rates = (response or {}).get("rates") or []
        if not rates:
            return None
        priced = [r for r in rates if r.get("totalCost") is not None]
        if not priced:
            return None
        return min(priced, key=lambda r: float(r["totalCost"]))

    def mycarrier_rate_shipment(self, order):
        self.ensure_one()
        if not self.mycarrier_location_id:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _(
                    "MyCarrier location ID is not configured on carrier %s.",
                    self.name,
                ),
                "warning_message": False,
            }
        payload = self._mycarrier_build_rate_payload(order)
        self._mycarrier_log("mycarrier.rate.request", payload)
        try:
            client = self._mycarrier_client()
            response = client.rate(payload)
        except MyCarrierRequestError as exc:
            return {
                "success": False,
                "price": 0.0,
                "error_message": str(exc),
                "warning_message": False,
            }
        self._mycarrier_log("mycarrier.rate.response", response)
        best = self._mycarrier_pick_best_rate(response)
        if not best:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _(
                    "MyCarrier returned no eligible carriers for this shipment."
                ),
                "warning_message": False,
            }
        return {
            "success": True,
            "price": float(best["totalCost"]),
            "error_message": "",
            "warning_message": False,
        }
