import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class K8sBackupWebhook(http.Controller):
    """Controller to receive backup status webhooks from the Kubernetes operator."""

    @http.route(
        "/k8s/backup/webhook/<int:backup_id>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def backup_webhook(self, backup_id, **kwargs):
        """Receive backup status update from the operator.

        Expected JSON payload:
        {
            "backupJob": "instance-backup-xyz",
            "namespace": "default",
            "phase": "Completed" | "Failed" | "Running",
            "objectKey": "instance/20231201-120000.zip",
            "bucket": "backups",
            "message": "optional error message"
        }

        Authorization: Bearer <webhook_token>
        """
        # Validate Authorization header
        auth_header = request.httprequest.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            _logger.warning(
                "Backup webhook %s: missing or invalid Authorization header", backup_id
            )
            return Response(
                json.dumps({"error": "Unauthorized"}),
                status=401,
                content_type="application/json",
            )

        token = auth_header[7:]  # Strip "Bearer "

        # Find the backup record
        backup = request.env["k8s.odoo.backup"].sudo().browse(backup_id)
        if not backup.exists():
            _logger.warning("Backup webhook: backup %s not found", backup_id)
            return Response(
                json.dumps({"error": "Backup not found"}),
                status=404,
                content_type="application/json",
            )

        # Validate token
        if not backup.webhook_token or backup.webhook_token != token:
            _logger.warning("Backup webhook %s: invalid token", backup_id)
            return Response(
                json.dumps({"error": "Invalid token"}),
                status=403,
                content_type="application/json",
            )

        # Parse JSON payload
        try:
            data = json.loads(request.httprequest.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.warning("Backup webhook %s: invalid JSON: %s", backup_id, e)
            return Response(
                json.dumps({"error": "Invalid JSON payload"}),
                status=400,
                content_type="application/json",
            )

        phase = data.get("phase", "").lower()
        message = data.get("message")
        object_key = data.get("objectKey")
        job_name = data.get("jobName")

        _logger.info(
            "Backup webhook %s: received phase=%s, objectKey=%s",
            backup.name,
            phase,
            object_key,
        )

        # Update backup record based on phase
        if phase == "running":
            backup.mark_running(job_name=job_name)
        elif phase == "completed":
            backup.mark_completed(
                completion_time=data.get("completionTime"),
                message=message,
                object_key=object_key,
            )
        elif phase == "failed":
            backup.mark_failed(
                message=message or "Backup failed",
                completion_time=data.get("completionTime"),
            )
        else:
            _logger.warning("Backup webhook %s: unknown phase %s", backup_id, phase)

        return Response(
            json.dumps({"status": "ok"}),
            status=200,
            content_type="application/json",
        )
