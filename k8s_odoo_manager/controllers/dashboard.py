import logging
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class K8sDashboardController(http.Controller):
    @http.route("/k8s/dashboard/data", type="json", auth="user")
    def get_dashboard_data(self):
        """Fetch all data needed for the K8s dashboard."""
        Cluster = request.env["k8s.cluster"]
        Instance = request.env["k8s.odoo.instance"]
        Backup = request.env["k8s.odoo.backup"]
        Restore = request.env["k8s.odoo.restore"]

        clusters = Cluster.search([])
        cluster_data = []

        for cluster in clusters:
            instances = Instance.search([("cluster_id", "=", cluster.id)])
            backups_24h = Backup.search(
                [
                    ("cluster_id", "=", cluster.id),
                    ("create_date", ">=", datetime.now() - timedelta(hours=24)),
                ]
            )
            last_backup = Backup.search(
                [
                    ("cluster_id", "=", cluster.id),
                    ("state", "=", "completed"),
                    ("completion_time", "!=", False),
                ],
                order="completion_time desc",
                limit=1,
            )

            # Count instances by phase
            phase_counts = {
                "Running": 0,
                "Upgrading": 0,
                "Restoring": 0,
                "Failed": 0,
                "Unknown": 0,
            }
            for inst in instances:
                phase = inst.phase or "Unknown"
                if phase in phase_counts:
                    phase_counts[phase] += 1
                else:
                    phase_counts["Unknown"] += 1

            cluster_data.append(
                {
                    "id": cluster.id,
                    "name": cluster.name,
                    "connected": cluster.connection_status == "connected",
                    "instance_count": len(instances),
                    "phase_counts": phase_counts,
                    "backups_24h": len(backups_24h),
                    "last_backup": (
                        last_backup.completion_time.isoformat() + "Z"
                        if last_backup and last_backup.completion_time
                        else None
                    ),
                    "last_backup_name": last_backup.name if last_backup else None,
                }
            )

        # Get running instances for the list
        running_instances = Instance.search(
            [("phase", "=", "Running")], order="cluster_id, name"
        )
        instances_data = [
            {
                "id": inst.id,
                "name": inst.name,
                "cluster_id": inst.cluster_id.id,
                "cluster_name": inst.cluster_id.name,
                "namespace": inst.namespace,
                "url": inst.ingress_url or inst.url,
                "image": inst.current_image,
                "replicas": f"{inst.ready_replicas or 0}/{inst.current_replicas or 0}",
            }
            for inst in running_instances
        ]

        # Get alerts
        alerts = []

        # Failed/non-running instances
        problem_instances = Instance.search(
            [("phase", "not in", ["Running", "Unknown"])]
        )
        for inst in problem_instances:
            alerts.append(
                {
                    "type": "warning",
                    "icon": "fa-exclamation-triangle",
                    "message": f"Instance {inst.name} is {inst.phase}",
                    "instance_id": inst.id,
                }
            )

        # Disconnected clusters
        disconnected = Cluster.search([("connection_status", "!=", "connected")])
        for cluster in disconnected:
            alerts.append(
                {
                    "type": "danger",
                    "icon": "fa-plug",
                    "message": f"Cluster {cluster.name} is disconnected",
                    "cluster_id": cluster.id,
                }
            )

        # Clusters with no recent backups (>7 days)
        for cluster in clusters:
            last_backup = Backup.search(
                [
                    ("cluster_id", "=", cluster.id),
                    ("state", "=", "completed"),
                ],
                order="completion_time desc",
                limit=1,
            )
            if last_backup and last_backup.completion_time:
                if last_backup.completion_time < datetime.now() - timedelta(days=7):
                    alerts.append(
                        {
                            "type": "warning",
                            "icon": "fa-clock-o",
                            "message": f"No backups for {cluster.name} in 7+ days",
                            "cluster_id": cluster.id,
                        }
                    )
            elif not last_backup:
                alerts.append(
                    {
                        "type": "info",
                        "icon": "fa-info-circle",
                        "message": f"No backups found for {cluster.name}",
                        "cluster_id": cluster.id,
                    }
                )

        # Failed backups in last 24h
        failed_backups = Backup.search(
            [
                ("state", "=", "failed"),
                ("create_date", ">=", datetime.now() - timedelta(hours=24)),
            ]
        )
        for backup in failed_backups:
            alerts.append(
                {
                    "type": "danger",
                    "icon": "fa-times-circle",
                    "message": f"Backup {backup.name} failed",
                    "backup_id": backup.id,
                }
            )

        # Pending/running restores
        active_restores = Restore.search([("state", "in", ["pending", "running"])])
        for restore in active_restores:
            alerts.append(
                {
                    "type": "info",
                    "icon": "fa-refresh fa-spin",
                    "message": f"Restore {restore.name} is {restore.state}",
                    "restore_id": restore.id,
                }
            )

        return {
            "clusters": cluster_data,
            "instances": instances_data,
            "alerts": alerts,
        }
