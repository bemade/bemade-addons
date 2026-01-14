import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class K8sOdooInstanceBackupSchedule(models.Model):
    _name = "k8s.odoo.instance.backup.schedule"
    _description = "Kubernetes Odoo Instance Backup Schedule"
    _order = "instance_id"

    instance_id = fields.Many2one(
        "k8s.odoo.instance",
        string="Instance",
        required=True,
        ondelete="cascade",
        index=True,
    )
    cluster_id = fields.Many2one(
        "k8s.cluster",
        related="instance_id.cluster_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    interval_number = fields.Integer(
        string="Interval",
        default=24,
        required=True,
        help="Number of hours or days between backups",
    )
    interval_type = fields.Selection(
        [
            ("hours", "Hours"),
            ("days", "Days"),
        ],
        string="Interval Type",
        default="hours",
        required=True,
    )
    keep_count = fields.Integer(
        string="Backups to Keep",
        default=7,
        required=True,
        help="Number of successful backups to retain. Older backups will be deleted.",
    )
    format = fields.Selection(
        [
            ("zip", "ZIP (with filestore)"),
            ("dump", "PostgreSQL custom format"),
            ("sql", "Plain SQL"),
        ],
        default="zip",
        required=True,
    )
    with_filestore = fields.Boolean(
        string="Include Filestore",
        default=True,
    )

    last_backup_time = fields.Datetime(
        string="Last Backup",
        readonly=True,
        help="Time of the last scheduled backup",
    )
    next_backup_time = fields.Datetime(
        string="Next Backup",
        compute="_compute_next_backup_time",
        store=True,
        help="Scheduled time for the next backup",
    )

    backup_ids = fields.One2many(
        "k8s.odoo.backup",
        "schedule_id",
        string="Backups",
    )
    backup_count = fields.Integer(
        string="Backup Count",
        compute="_compute_backup_count",
    )

    _sql_constraints = [
        (
            "instance_unique",
            "UNIQUE(instance_id)",
            "A backup schedule already exists for this instance.",
        ),
        (
            "interval_positive",
            "CHECK(interval_number > 0)",
            "Interval must be a positive number.",
        ),
        (
            "keep_count_positive",
            "CHECK(keep_count > 0)",
            "Keep count must be at least 1.",
        ),
    ]

    @api.depends("last_backup_time", "interval_number", "interval_type", "active")
    def _compute_next_backup_time(self):
        for schedule in self:
            if not schedule.active:
                schedule.next_backup_time = False
                continue

            if schedule.interval_type == "hours":
                delta = timedelta(hours=schedule.interval_number)
            else:
                delta = timedelta(days=schedule.interval_number)

            if schedule.last_backup_time:
                schedule.next_backup_time = schedule.last_backup_time + delta
            else:
                schedule.next_backup_time = fields.Datetime.now()

    def _compute_backup_count(self):
        for schedule in self:
            schedule.backup_count = len(schedule.backup_ids)

    @api.constrains("interval_number", "interval_type")
    def _check_interval(self):
        for schedule in self:
            if schedule.interval_type == "hours" and schedule.interval_number < 1:
                raise ValidationError(_("Interval must be at least 1 hour."))
            if schedule.interval_type == "days" and schedule.interval_number < 1:
                raise ValidationError(_("Interval must be at least 1 day."))

    @api.depends("instance_id.name", "interval_number", "interval_type")
    def _compute_display_name(self):
        for schedule in self:
            schedule.display_name = f"{schedule.instance_id.name} - Every {schedule.interval_number} {schedule.interval_type}"

    def action_trigger_backup_now(self):
        """Manually trigger a backup for this schedule."""
        self.ensure_one()
        return self._create_scheduled_backup()

    def _create_scheduled_backup(self):
        """Create a backup record for this schedule."""
        self.ensure_one()

        if not self.instance_id:
            _logger.warning(
                "Cannot create backup: no instance associated with schedule %s", self.id
            )
            return False

        backup = self.env["k8s.odoo.backup"].create(
            {
                "instance_id": self.instance_id.id,
                "format": self.format,
                "with_filestore": self.with_filestore,
                "schedule_id": self.id,
            }
        )

        self.last_backup_time = fields.Datetime.now()
        _logger.info(
            "Created scheduled backup %s for instance %s",
            backup.name,
            self.instance_id.name,
        )
        return backup

    def action_view_backups(self):
        """View all backups for this schedule."""
        self.ensure_one()
        return {
            "name": _("Backups for %s") % self.instance_id.name,
            "type": "ir.actions.act_window",
            "res_model": "k8s.odoo.backup",
            "view_mode": "list,form",
            "domain": [("schedule_id", "=", self.id)],
            "context": {"default_instance_id": self.instance_id.id},
        }
