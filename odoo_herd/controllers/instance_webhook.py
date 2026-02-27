import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class K8sInstanceWebhook(http.Controller):
    """Controller to receive instance status webhooks from the Kubernetes operator."""

    @http.route(
        "/k8s/instance/webhook/<int:cluster_id>/<string:namespace>/<string:name>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def instance_webhook(self, cluster_id, namespace, name, **kwargs):
        """Receive instance status update from the operator.

        Expected JSON payload:
        {
            "phase": "Running" | "Restoring" | "Upgrading",
            "message": "optional message"
        }

        Query params:
            db: database name
            token: webhook token for authentication
        """
        # Get token from query params
        token = kwargs.get("token", "")
        db_name = kwargs.get("db", "")

        if not token:
            _logger.warning("Instance webhook %s/%s: missing token", namespace, name)
            return Response(
                json.dumps({"error": "Unauthorized"}),
                status=401,
                content_type="application/json",
            )

        # Find the cluster
        cluster = request.env["k8s.cluster"].sudo().browse(cluster_id)
        if not cluster.exists():
            _logger.warning("Instance webhook: cluster %s not found", cluster_id)
            return Response(
                json.dumps({"error": "Cluster not found"}),
                status=404,
                content_type="application/json",
            )

        # Validate token against cluster's webhook token
        if (
            not cluster.instance_webhook_token
            or cluster.instance_webhook_token != token
        ):
            _logger.warning("Instance webhook %s/%s: invalid token", namespace, name)
            return Response(
                json.dumps({"error": "Invalid token"}),
                status=401,
                content_type="application/json",
            )

        # Parse the payload
        try:
            payload = json.loads(request.httprequest.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _logger.warning("Instance webhook: invalid JSON payload: %s", e)
            return Response(
                json.dumps({"error": "Invalid JSON payload"}),
                status=400,
                content_type="application/json",
            )

        phase = payload.get("phase")
        message = payload.get("message", "")

        _logger.info(
            "Instance webhook received for %s/%s: phase=%s", namespace, name, phase
        )

        # Find the instance
        instance = (
            request.env["k8s.odoo.instance"]
            .sudo()
            .search(
                [
                    ("cluster_id", "=", cluster_id),
                    ("namespace", "=", namespace),
                    ("name", "=", name),
                ],
                limit=1,
            )
        )

        if instance:
            # Update the instance status
            instance.write(
                {
                    "phase": phase,
                }
            )
            _logger.info("Updated instance %s/%s phase to %s", namespace, name, phase)
        else:
            # Instance not synced yet - trigger a sync
            _logger.info(
                "Instance %s/%s not found locally, triggering sync", namespace, name
            )
            try:
                cluster.sync_odoo_instances()
            except Exception as e:
                _logger.warning("Failed to sync instances: %s", e)

        return Response(
            json.dumps({"status": "ok"}),
            status=200,
            content_type="application/json",
        )
