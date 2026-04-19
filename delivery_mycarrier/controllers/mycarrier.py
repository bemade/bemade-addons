"""MyCarrier inbound webhook controller.

Thin dispatcher: authenticates the per-carrier token, parses the JSON
body, and hands off to
``delivery.carrier._mycarrier_handle_webhook(event_type, payload)``.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MyCarrierWebhookController(http.Controller):

    @http.route(
        "/mycarrier/webhook/<string:token>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def webhook(self, token, **kwargs):
        carrier = (
            request.env["delivery.carrier"]
            .sudo()
            .search(
                [
                    ("delivery_type", "=", "mycarrier"),
                    ("mycarrier_webhook_token", "=", token),
                ],
                limit=1,
            )
        )
        if not carrier:
            _logger.warning("MyCarrier webhook: unknown token")
            return request.make_json_response({"error": "unknown token"}, status=403)
        try:
            body = request.httprequest.get_data() or b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return request.make_json_response({"error": "invalid json"}, status=400)
        event_type = payload.get("type") or payload.get("event") or ""
        status = carrier._mycarrier_handle_webhook(event_type, payload)
        return request.make_json_response({"status": status}, status=200)
