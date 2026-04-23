import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class K8sStagingRefreshWebhook(http.Controller):
    """Receive staging-refresh status webhooks from the Kubernetes operator."""

    @http.route(
        "/k8s/staging_refresh/webhook/<int:refresh_id>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def staging_refresh_webhook(self, refresh_id, **kwargs):
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            _logger.warning(
                "Staging refresh webhook %s: missing or invalid Authorization header",
                refresh_id,
            )
            return Response(
                json.dumps({"error": "Unauthorized"}),
                status=401,
                content_type="application/json",
            )

        token = auth_header[7:]

        refresh = (
            request.env["k8s.odoo.staging.refresh"].sudo().browse(refresh_id)
        )
        if not refresh.exists():
            _logger.warning(
                "Staging refresh webhook: record %s not found", refresh_id
            )
            return Response(
                json.dumps({"error": "Refresh not found"}),
                status=404,
                content_type="application/json",
            )

        if not refresh.webhook_token or refresh.webhook_token != token:
            _logger.warning(
                "Staging refresh webhook %s: invalid token", refresh_id
            )
            return Response(
                json.dumps({"error": "Invalid token"}),
                status=403,
                content_type="application/json",
            )

        try:
            data = json.loads(request.httprequest.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.warning(
                "Staging refresh webhook %s: invalid JSON: %s", refresh_id, e
            )
            return Response(
                json.dumps({"error": "Invalid JSON payload"}),
                status=400,
                content_type="application/json",
            )

        phase = data.get("phase", "").lower()
        message = data.get("message")

        _logger.info(
            "Staging refresh webhook %s: received phase=%s",
            refresh.name,
            phase,
        )

        if phase == "running":
            refresh.mark_running(
                start_time=data.get("startTime"),
                status=data,
            )
        elif phase == "completed":
            refresh.mark_completed(
                completion_time=data.get("completionTime"),
                message=message,
                status=data,
            )
            self._notify_user(
                refresh,
                "Staging Refresh Completed",
                f"Refresh {refresh.name} of {refresh.target_instance_id.name} "
                f"from {refresh.source_instance_id.name} completed.",
                "success",
            )
        elif phase == "failed":
            refresh.mark_failed(
                message=message or "Staging refresh failed",
                completion_time=data.get("completionTime"),
                status=data,
            )
            self._notify_user(
                refresh,
                "Staging Refresh Failed",
                f"Refresh {refresh.name} of {refresh.target_instance_id.name} "
                f"failed: {message or 'Unknown error'}",
                "danger",
            )
        else:
            _logger.warning(
                "Staging refresh webhook %s: unknown phase %s", refresh_id, phase
            )

        return Response(
            json.dumps({"status": "ok"}),
            status=200,
            content_type="application/json",
        )

    def _notify_user(self, record, title, message, notification_type="info"):
        if not record.create_uid:
            return
        try:
            record.env["bus.bus"]._sendone(
                record.create_uid.partner_id,
                "simple_notification",
                {
                    "title": title,
                    "message": message,
                    "type": notification_type,
                    "sticky": notification_type == "danger",
                },
            )
        except Exception as e:
            _logger.warning("Failed to send user notification: %s", e)
