from datetime import timedelta
from typing import TYPE_CHECKING, Optional, cast

from odoo import fields, models

if TYPE_CHECKING:
    from odoo.addons.mail.models.mail_activity_mixin import MailActivityMixin


class BaseLateNotificationMixin(models.AbstractModel):
    """Abstract model for late order notifications"""

    _name = "base.late.notification.mixin"
    _description = "Base Late Notification Mixin"

    # Subclasses must override these class attributes or related helpers
    _late_config_prefix: Optional[str] = None  # e.g., "sale" or "purchase"
    _late_activity_note = ""
    _late_activity_summary_default = "Vérifier commande en retard"
    _late_notification_days_default = 5

    late_notification_date = fields.Datetime(
        string="Late Notification Date",
        help="Date when a late notification was last sent for this order.",
        copy=False,
    )

    # -------------------------------------------------------------------------
    # Configuration helpers
    # -------------------------------------------------------------------------

    def _get_config_prefix(self):
        if not self._late_config_prefix:
            raise ValueError(
                "Late notification mixin requires '_late_config_prefix' to be set"
            )
        return self._late_config_prefix

    def _get_config_param_key(self, suffix):
        return f"sale_purchase_late_notification.{self._get_config_prefix()}_{suffix}"

    def _get_config_param(self, suffix, default):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._get_config_param_key(suffix), default)
        )

    def _is_late_notification_enabled(self):
        """Check if late notifications are enabled for this model."""
        enabled = self._get_config_param("enabled", "False")
        if isinstance(enabled, bool):
            return enabled
        return str(enabled).lower() in ("true", "1", "yes")

    def _get_late_activity_summary(self):
        return self._get_config_param(
            "activity_summary", self._late_activity_summary_default
        )

    def _get_late_activity_user_id(self):
        return int(
            self._get_config_param("default_user_id", str(self.env.user.id))
            or self.env.user.id
        )

    def _get_late_days_threshold(self):
        """Get the number of days an order must be late before notification."""
        return int(
            self._get_config_param(
                "late_days_threshold", str(self._late_notification_days_default)
            )
        )

    def _get_activity_type(self):
        """Get the activity type for late order notifications"""
        return self.env.ref("mail.mail_activity_data_todo")

    def _get_late_orders_domain(self):
        """Get the domain to find late orders that haven't been notified yet.

        Relies on the model's is_late field and its _search_is_late method to handle
        the actual late detection logic using stored/searchable fields.
        """
        return [
            ("is_late", "=", True),
            ("late_notification_date", "=", False),
        ]

    def _get_late_orders(self):
        """Find orders that are late and haven't been notified yet.

        Subclasses should override _get_late_order_ids() to use efficient SQL
        that incorporates the threshold check.
        """
        order_ids = self._get_late_order_ids()
        if not order_ids:
            return self.browse()
        return self.browse(order_ids)

    def _get_late_order_ids(self):
        """Get IDs of late orders past threshold. Subclasses should override with SQL."""
        # Fallback: use domain search (less efficient)
        return self.search(self._get_late_orders_domain()).ids

    def create_late_activities(self):
        """Create activities for late orders"""
        late_orders = self._get_late_orders()
        if not late_orders:
            return

        activity_vals = {
            "activity_type_id": self._get_activity_type().id,
            "summary": self._get_late_activity_summary(),
            "note": self._get_activity_note(),
            "user_id": self._get_late_activity_user_id(),
            "date_deadline": fields.Date.today() + timedelta(days=1),
        }

        for order in late_orders:
            cast("MailActivityMixin", order).activity_schedule(**activity_vals)
            order.late_notification_date = fields.Datetime.now()

    def _get_activity_note(self):
        """Get the note to include in the activity"""
        return self._late_activity_note

    # -------------------------------------------------------------------------
    # Cron helper
    # -------------------------------------------------------------------------

    def _cron_create_late_activities(self):
        """Cron job entry point - only runs if notifications are enabled."""
        if not self._is_late_notification_enabled():
            return
        self.create_late_activities()
