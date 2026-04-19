import json
import logging
import uuid
from urllib.error import URLError
from urllib.request import urlopen

from odoo import _, fields, models
from odoo.exceptions import UserError

from .mycarrier_request import MyCarrierRequest, MyCarrierRequestError

_logger = logging.getLogger(__name__)


MYCARRIER_STATUS_CODE_TO_STATE = {
    0: "booked",
    1: "picked_up",
    2: "in_transit",
    3: "out_for_delivery",
    4: "delivered",
}


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
        "username against the MyCarrier Rating and Orders APIs.",
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
    mycarrier_ready_to_dispatch = fields.Boolean(
        string="Auto-Dispatch",
        default=False,
        help="When enabled, orders are submitted with readyToDispatch=Yes "
        "so MyCarrier auto-tenders the shipment. Otherwise the order is "
        "queued for manual dispatch inside MyCarrier.",
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
    mycarrier_webhook_token = fields.Char(
        string="Webhook Token",
        copy=False,
        help="Shared secret included in the MyCarrier webhook URL "
        "(/mycarrier/webhook/<token>). Provide this URL to MyCarrier "
        "support so they can register it for shipment.created, "
        "shipment.tracking.updated and shipment.canceled events.",
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

    def _mycarrier_build_order_entry(self, picking):
        self.ensure_one()
        self._mycarrier_validate_picking(picking)
        ship_from = (
            picking.picking_type_id.warehouse_id.partner_id
            or picking.company_id.partner_id
        )
        ship_to = picking.partner_id
        default_class = self.mycarrier_default_commodity_class or "70"
        commodities = []
        total_weight = 0.0
        for move in picking.move_ids:
            product = move.product_id
            qty = move.quantity or move.product_uom_qty
            weight = (product.weight or 0.0) * qty
            total_weight += weight
            commodities.append(
                {
                    "commodityDescription": product.display_name,
                    "commodityClass": product.mycarrier_commodity_class
                    or default_class,
                    "commodityWeight": weight,
                    "commodityPieces": int(qty) or 1,
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
        pickup_date = ""
        if picking.scheduled_date:
            pickup_date = picking.scheduled_date.strftime("%m-%d-%Y")
        return {
            "locationId": self.mycarrier_location_id,
            "paymentDirection": self.mycarrier_payment_direction,
            "readyToDispatch": "Yes" if self.mycarrier_ready_to_dispatch else "No",
            "quoteReferenceID": picking.name,
            "pickupDate": pickup_date,
            "serviceType": "LTL",
            "weightUnit": self.mycarrier_weight_unit,
            "measurementUnit": self.mycarrier_measurement_unit,
            "origin": self._mycarrier_address_dict(ship_from),
            "destination": self._mycarrier_address_dict(ship_to),
            "quoteUnits": quote_units,
            "totalWeight": total_weight,
        }

    def _mycarrier_validate_picking(self, picking):
        missing = []
        partner = picking.partner_id
        if not partner:
            raise UserError(
                _("Picking %s has no delivery partner.", picking.name)
            )
        if not partner.city:
            missing.append("city")
        if not partner.zip:
            missing.append("zip")
        if not partner.country_id:
            missing.append("country")
        if not partner.country_id or partner.country_id.code in ("US", "CA"):
            if not partner.state_id:
                missing.append("state")
        if missing:
            raise UserError(
                _(
                    "Cannot book MyCarrier shipment for %(name)s: missing "
                    "destination address fields: %(fields)s.",
                    name=picking.name,
                    fields=", ".join(missing),
                )
            )

    def mycarrier_send_shipping(self, pickings):
        self.ensure_one()
        orders = [self._mycarrier_build_order_entry(p) for p in pickings]
        payload = {"orders": orders}
        self._mycarrier_log("mycarrier.order.request", payload)
        try:
            response = self._mycarrier_client().create_order(payload)
        except MyCarrierRequestError as exc:
            raise UserError(
                _("MyCarrier rejected the shipment: %s", exc)
            ) from exc
        self._mycarrier_log("mycarrier.order.response", response)
        response_orders = {
            (o.get("quoteReferenceID") or ""): o
            for o in (response or {}).get("orders") or []
        }
        result = []
        for picking in pickings:
            match = response_orders.get(picking.name, {})
            picking.write(
                {
                    "mycarrier_order_id": match.get("orderId") or False,
                    "mycarrier_quote_id": match.get("quoteId") or False,
                    "mycarrier_status": "queued",
                }
            )
            result.append(
                {
                    "exact_price": picking.carrier_price or 0.0,
                    "tracking_number": f"MYCARRIER-PENDING-{picking.name}",
                }
            )
        return result

    # ----------------- #
    # Inbound webhook   #
    # ----------------- #

    def _mycarrier_handle_webhook(self, event_type, payload):
        """Entry point for the webhook controller.

        Returns a short status string ("ok" / "ignored").
        """
        self.ensure_one()
        picking = self._mycarrier_match_picking(payload)
        if not picking:
            _logger.warning(
                "MyCarrier webhook: no matching picking for event %s (ids=%s)",
                event_type,
                {
                    k: payload.get(k)
                    for k in ("QuoteId", "CustomerBOLNumber", "PONumber", "orderId")
                },
            )
            return "ignored"
        handler = {
            "shipment.created": self._mycarrier_on_created,
            "shipment.tracking.updated": self._mycarrier_on_tracking,
            "shipment.canceled": self._mycarrier_on_canceled,
        }.get(event_type)
        if not handler:
            _logger.info("MyCarrier webhook: ignoring event type %s", event_type)
            return "ignored"
        handler(picking, payload)
        return "ok"

    def _mycarrier_match_picking(self, payload):
        Picking = self.env["stock.picking"].sudo()
        quote_id = payload.get("QuoteId")
        if quote_id:
            match = Picking.search(
                [("mycarrier_quote_id", "=", str(quote_id))], limit=1
            )
            if match:
                return match
        for key in ("CustomerBOLNumber", "PONumber"):
            ref = payload.get(key)
            if ref:
                match = Picking.search([("name", "=", str(ref))], limit=1)
                if match:
                    return match
        order_id = payload.get("orderId") or payload.get("OrderId")
        if order_id:
            match = Picking.search(
                [("mycarrier_order_id", "=", str(order_id))], limit=1
            )
            if match:
                return match
        return Picking.browse()

    def _mycarrier_fetch_document(self, url):
        if not url:
            return b""
        try:
            with urlopen(url, timeout=30) as resp:
                return resp.read()
        except (URLError, ValueError) as exc:
            _logger.warning("MyCarrier webhook: failed to fetch %s: %s", url, exc)
            return b""

    def _mycarrier_attachment_exists(self, picking, filename):
        return bool(
            self.env["ir.attachment"].sudo().search_count(
                [
                    ("res_model", "=", "stock.picking"),
                    ("res_id", "=", picking.id),
                    ("name", "=", filename),
                ]
            )
        )

    def _mycarrier_on_created(self, picking, payload):
        pro = payload.get("CarrierPRONumber") or ""
        total_cost = payload.get("TotalCost")
        updates = {
            "carrier_tracking_ref": pro or picking.carrier_tracking_ref,
            "mycarrier_shipment_id": str(payload.get("ShipmentId") or "") or False,
            "mycarrier_bol_url": payload.get("BOLLink") or False,
            "mycarrier_label_url": payload.get("LabelLink") or False,
            "mycarrier_status": "booked",
        }
        if total_cost is not None:
            updates["carrier_price"] = float(total_cost)
        picking.write(updates)

        attachments = []
        ref = pro or picking.name
        if payload.get("BOLLink"):
            name = f"MyCarrier-BOL-{ref}.pdf"
            if not self._mycarrier_attachment_exists(picking, name):
                content = self._mycarrier_fetch_document(payload["BOLLink"])
                if content:
                    attachments.append((name, content))
        if payload.get("LabelLink"):
            name = f"MyCarrier-Label-{ref}.pdf"
            if not self._mycarrier_attachment_exists(picking, name):
                content = self._mycarrier_fetch_document(payload["LabelLink"])
                if content:
                    attachments.append((name, content))

        carrier_name = (
            payload.get("CarrierName") or payload.get("CarrierCode") or ""
        )
        body = (
            f"MyCarrier shipment created<br/>"
            f"Carrier: {carrier_name}<br/>"
            f"PRO #: {pro}<br/>"
            f"Total cost: {total_cost}"
        )
        picking.message_post(body=body, attachments=attachments, body_is_html=True)

    def _mycarrier_on_tracking(self, picking, payload):
        if payload.get("IsStatusException"):
            picking.mycarrier_status = "exception"
        else:
            state = MYCARRIER_STATUS_CODE_TO_STATE.get(payload.get("StatusCode"))
            if state:
                picking.mycarrier_status = state
        history = payload.get("TrackingHistory") or []
        if history:
            latest = history[-1]
            picking.message_post(
                body=(
                    f"MyCarrier tracking update: "
                    f"{latest.get('StatusDescription', '')} "
                    f"({latest.get('StatusDate', '')})"
                )
            )

    def _mycarrier_on_canceled(self, picking, payload):
        picking.mycarrier_status = "canceled"
        details = payload.get("ShipmentPriceDetails") or []
        lines = "".join(
            f"<li>{d.get('Description', '')}: {d.get('Amount', '')}</li>"
            for d in details
        )
        body = "MyCarrier shipment canceled."
        if lines:
            body += f"<ul>{lines}</ul>"
        picking.message_post(body=body, body_is_html=True)

    def mycarrier_get_tracking_link(self, picking):
        self.ensure_one()
        if not picking.carrier_tracking_ref:
            return ""
        return (
            "https://app.mycarrier.io/tracking/"
            f"{picking.carrier_tracking_ref}"
        )

    def mycarrier_cancel_shipment(self, picking):
        self.ensure_one()
        raise UserError(
            _(
                "MyCarrier does not expose a cancellation API. Please cancel "
                "shipment %(name)s (PRO %(pro)s) in the MyCarrier web "
                "application; Odoo will update when the shipment.canceled "
                "webhook arrives.",
                name=picking.name,
                pro=picking.carrier_tracking_ref or _("unknown"),
            )
        )
