import json
import uuid
from datetime import datetime, timezone

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
        help="Email of the MyCarrier account admin. Sent as 'customerEmail' "
        "in the rating payload — MyCarrier's rating endpoint authenticates "
        "via this field alone (no API key required).",
    )
    mycarrier_api_key = fields.Char(
        string="MyCarrier API Key",
        groups="base.group_system",
        help="API key from MyCarrier Customer Settings → Order API Key. "
        "Only required to book orders (out of scope in this module).",
    )
    mycarrier_location_id = fields.Char(
        string="MyCarrier Location ID",
        help="The MyCarrier location this carrier books from. Create one "
        "delivery.carrier record per MyCarrier location.",
    )
    mycarrier_customer_name = fields.Char(
        string="MyCarrier Customer Name",
        help="customerName field sent on the rating request — typically the "
        "MyCarrier account/company name.",
    )
    mycarrier_preferred_carriers = fields.Char(
        string="Preferred Carriers (SCAC)",
        help="Comma-separated SCAC codes of carriers MyCarrier should quote, "
        "e.g. 'RDWY,RDFS,AVRT,PITD,XPOL,EXLA,EFWW'. Leave empty for all "
        "available carriers.",
    )
    mycarrier_payment_direction = fields.Selection(
        [
            ("Outbound Prepaid", "Outbound Prepaid"),
            ("Outbound Collect", "Outbound Collect"),
            ("Third Party", "Third Party"),
        ],
        string="Payment Direction",
        default="Outbound Prepaid",
    )
    mycarrier_weight_unit = fields.Selection(
        [("LB", "Pounds"), ("KG", "Kilograms")],
        string="Weight Unit",
        default="LB",
    )
    mycarrier_measurement_unit = fields.Selection(
        [("INCHES", "Inches"), ("CM", "Centimeters")],
        string="Measurement Unit",
        default="INCHES",
    )
    mycarrier_default_commodity_class = fields.Selection(
        NMFC_FREIGHT_CLASSES,
        string="Default NMFC Class",
        default="70",
        help="Fallback freight class used when a product has no "
        "MyCarrier NMFC class configured.",
    )
    mycarrier_source = fields.Char(
        string="MyCarrier Source",
        default="odoo",
        help="Value sent as the top-level 'source' field on the rating "
        "request. MyCarrier appears to whitelist this per account and "
        "rejects unknown values with HTTP 403; set it to whatever string "
        "MyCarrier has registered for your integration (often the domain "
        "of the system originating the quote, e.g. 'refwest.com').",
    )

    def _mycarrier_client(self):
        self.ensure_one()
        environment = "prod" if self.prod_environment else "sandbox"
        return MyCarrierRequest(environment=environment)

    def _mycarrier_stop(self, number, stop_type, partner):
        return {
            "stopNumber": number,
            "stopType": stop_type,
            "name": partner.name or "",
            "addressLine1": partner.street or "",
            "addressLine2": partner.street2 or "",
            "city": partner.city or "",
            "stateProvince": partner.state_id.code or "",
            "postalCode": (partner.zip or "").replace(" ", ""),
            "country": {
                "alpha2Code": partner.country_id.code or "",
                "name": partner.country_id.name or "",
            },
            "contactEmail": partner.email or "",
            "contactName": (
                partner.child_ids[:1].name if partner.child_ids else partner.name
            ) or "",
            "contactPhone": partner.phone or "",
            "isScheduledRequired": False,
            "schedule": {"start_time": "9a", "end_time": "5p", "date": "ASAP"},
            "note": "",
        }

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
        default_class = self.mycarrier_default_commodity_class or "70"
        weight_uom = self.mycarrier_weight_unit or "LB"
        length_uom = self.mycarrier_measurement_unit or "INCHES"

        line_items = []
        total_weight = 0.0
        total_pieces = 0
        for idx, line in enumerate(order.order_line, start=1):
            product = line.product_id
            if not product or product.type == "service" or line.is_delivery:
                continue
            qty = int(line.product_uom_qty or 1)
            weight = (product.weight or 0.0) * qty
            total_weight += weight
            total_pieces += qty
            line_items.append(
                {
                    "lineItemId": str(idx),
                    "commodityName": product.display_name,
                    "class": product.mycarrier_commodity_class or default_class,
                    "commodityDescription": product.display_name,
                    "countryOfManufacture": "United States",
                    "associatedPickupStopNumber": 1,
                    "associatedDropStopNumber": 2,
                    "nmfcItemCode": product.mycarrier_nmfc_code or "",
                    "nmfcSubCode": "",
                    "commodityType": "",
                    "harmonizedCode": "",
                    "isHazmat": False,
                    "unitValue": int(line.price_unit or 0),
                    "unitValueCurrency": (order.currency_id.name or "USD"),
                    "quantity": qty,
                    "dimensions": {
                        "length": 48,
                        "lengthUOM": length_uom,
                        "width": 40,
                        "widthUOM": length_uom,
                        "height": 48,
                        "heightUOM": length_uom,
                        "weight": weight,
                        "weightUOM": weight_uom,
                        "stackable": False,
                        "quantity": 1,
                        "packageType": "PLT",
                    },
                }
            )

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000")
        currency = order.currency_id.name or "USD"
        shipment = {
            "shipmentId": order.name or "",
            "shipmentType": "LTL",
            "schedulePickupStartDate": now_iso,
            "schedulePickupEndDate": now_iso,
            "scheduleDeliveryStartDate": now_iso,
            "scheduleDeliveryEndDate": now_iso,
            "currencyType": currency,
            "shipmentValue": int(order.amount_total or 0),
            "shipmentMode": "Dry Van",
            "perishableItem": False,
            "paymentType": self.mycarrier_payment_direction or "Outbound Prepaid",
            "totalWeight": total_weight,
            "totalWeightUOM": weight_uom,
            "totalPieces": max(total_pieces, 1),
            "totalPiecesUOM": "PLTS",
            "totalVolume": 0,
            "totalVolumeUOM": "CFT",
            "totalLinearFeet": 0,
            "preferredSystemOfMeasurement": (
                "METRIC" if length_uom == "CM" else "IMPERIAL"
            ),
            "stops": [
                self._mycarrier_stop(1, "PICKUP", ship_from),
                self._mycarrier_stop(2, "DROP", ship_to),
            ],
            "shipmentLineItems": line_items,
        }

        data = {"shipment": shipment}
        if self.mycarrier_preferred_carriers:
            data["preferredCarriers"] = self.mycarrier_preferred_carriers

        return {
            "specVersion": "1",
            "type": "com.mycarrier.carrier.integrations",
            "source": self.mycarrier_source or "odoo",
            "id": now_iso,
            "time": now_iso,
            "direction": "outbound",
            "customerName": self.mycarrier_customer_name or "",
            "customerEmail": self.sudo().mycarrier_account_email or "",
            "locationId": self.mycarrier_location_id or "",
            "data": data,
        }

    def _mycarrier_extract_error(self, response):
        """Return a human-readable error string if the MyCarrier response signals
        a failure, else None. MyCarrier wraps failures in
        ``data.error`` alongside ``data.failedTransaction``; the ``error`` object
        carries ``code``, ``message`` and ``description`` (any of which may be
        empty, so we fall back to the HTTP-style code alone).
        """
        data = (response or {}).get("data") or {}
        error = data.get("error") or (response or {}).get("error")
        if not error:
            return None
        if isinstance(error, str):
            return error
        if isinstance(error, dict):
            parts = [
                str(error.get(k)).strip()
                for k in ("code", "message", "description")
                if error.get(k)
            ]
            return " - ".join(parts) if parts else None
        return str(error)

    def _mycarrier_pick_best_rate(self, response):
        data = (response or {}).get("data") or {}
        rates = data.get("rates") or (response or {}).get("rates") or []
        priced = []
        for rate in rates:
            if (rate.get("quoteStatus") or "").lower() != "available":
                continue
            for price in rate.get("price") or []:
                amount = price.get("grossPrice") or price.get("netPrice")
                if amount in (None, ""):
                    continue
                try:
                    priced.append((float(amount), rate, price))
                except (TypeError, ValueError):
                    continue
        if not priced:
            return None
        return min(priced, key=lambda t: t[0])

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
        if not self.sudo().mycarrier_account_email:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _(
                    "MyCarrier account email is not configured on carrier %s.",
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
        api_error = self._mycarrier_extract_error(response)
        if api_error:
            return {
                "success": False,
                "price": 0.0,
                "error_message": _("MyCarrier API error: %s", api_error),
                "warning_message": False,
            }
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
            "price": best[0],
            "error_message": "",
            "warning_message": False,
        }
