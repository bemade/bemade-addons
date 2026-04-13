import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class K8sRestoreWebhook(http.Controller):
    """Controller to receive restore status webhooks from the Kubernetes operator."""

    @http.route(
        "/k8s/restore/webhook/<int:restore_id>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def restore_webhook(self, restore_id, **kwargs):
        """Receive restore status update from the operator.

        Expected JSON payload:
        {
            "restoreJob": "instance-restore-xyz",
            "namespace": "default",
            "phase": "Completed" | "Failed" | "Running",
            "targetInstance": "my-instance",
            "message": "optional error message"
        }

        Authorization: Bearer <webhook_token>
        """
        # Validate Authorization header
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            _logger.warning(
                "Restore webhook %s: missing or invalid Authorization header",
                restore_id,
            )
            return Response(
                json.dumps({"error": "Unauthorized"}),
                status=401,
                content_type="application/json",
            )

        token = auth_header[7:]  # Strip "Bearer "

        # Find the restore record
        restore = request.env["k8s.odoo.restore"].sudo().browse(restore_id)
        if not restore.exists():
            _logger.warning("Restore webhook: restore %s not found", restore_id)
            return Response(
                json.dumps({"error": "Restore not found"}),
                status=404,
                content_type="application/json",
            )

        # Validate token
        if not restore.webhook_token or restore.webhook_token != token:
            _logger.warning("Restore webhook %s: invalid token", restore_id)
            return Response(
                json.dumps({"error": "Invalid token"}),
                status=403,
                content_type="application/json",
            )

        # Parse JSON payload
        try:
            data = json.loads(request.httprequest.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.warning("Restore webhook %s: invalid JSON: %s", restore_id, e)
            return Response(
                json.dumps({"error": "Invalid JSON payload"}),
                status=400,
                content_type="application/json",
            )

        phase = data.get("phase", "").lower()
        message = data.get("message")
        job_name = data.get("jobName")

        _logger.info(
            "Restore webhook %s: received phase=%s",
            restore.name,
            phase,
        )

        # Update restore record based on phase
        if phase == "running":
            restore.mark_running(job_name=job_name)
        elif phase == "completed":
            restore.mark_completed(
                completion_time=data.get("completionTime"),
                message=message,
            )
            self._notify_user(
                restore,
                "Restore Completed",
                f"Restore {restore.name} to {restore.target_instance_id.name} completed successfully.",
                "success",
            )
        elif phase == "failed":
            restore.mark_failed(
                message=message or "Restore failed",
                completion_time=data.get("completionTime"),
            )
            self._notify_user(
                restore,
                "Restore Failed",
                f"Restore {restore.name} to {restore.target_instance_id.name} failed: {message or 'Unknown error'}",
                "danger",
            )
        else:
            _logger.warning("Restore webhook %s: unknown phase %s", restore_id, phase)

        return Response(
            json.dumps({"status": "ok"}),
            status=200,
            content_type="application/json",
        )

    def _notify_user(self, record, title, message, notification_type="info"):
        """Send a bus notification to the user who created the record.

        Args:
            record: The backup/restore record
            title: Notification title
            message: Notification message
            notification_type: 'success', 'danger', 'warning', or 'info'
        """
        if not record.create_uid:
            return

        try:
            # Send notification via bus
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
