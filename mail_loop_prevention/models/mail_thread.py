# Copyright 2025 DurPro
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import hashlib
import logging
from datetime import timedelta

from odoo import api, models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def _get_loop_prevention_config(self):
        """
        Get loop prevention configuration from system parameters.
        Values are validated by ir.config_parameter model on write.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        Settings = self.env["res.config.settings"].sudo()
        return {
            "enabled": Settings._get_param_as_bool(
                "mail_loop_prevention.enabled", default=True
            ),
            "time_window_hours": int(
                ICP.get_param("mail_loop_prevention.time_window_hours", default="48")
            ),
            "max_identical_messages": int(
                ICP.get_param(
                    "mail_loop_prevention.max_identical_messages", default="3"
                )
            ),
        }

    def _compute_message_hash(self, body, subject=None):
        """
        Compute a hash of the message content for duplicate detection.
        Converts HTML to plaintext to ignore formatting differences.
        """
        import html

        # Unescape HTML entities (&lt; -> <, &gt; -> >, etc.)
        # This is needed because message_post escapes the body before passing to _message_create
        unescaped_body = html.unescape(body or "")

        # Convert HTML to plaintext (handles extra wrapper tags that Odoo adds)
        text_body = html2plaintext(unescaped_body).strip()
        text_subject = (subject or "").strip()

        # Combine subject and body for hash
        content = f"{text_subject}|{text_body}"

        # Debug logging to help troubleshoot loop detection
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "Loop prevention: Computing hash - plaintext=%r, hash=%s",
                text_body[:100] if text_body else "",
                hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
            )

        # Create hash
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _check_message_loop(self, body, subject=None, message_type="comment"):
        """
        Check if posting this message would create a loop.
        Returns True if the message should be blocked, False otherwise.
        """
        config = self._get_loop_prevention_config()

        if not config["enabled"]:
            return False

        # Only check for automated messages (notifications, auto_comment, etc.)
        # Don't block regular user comments
        if message_type not in ("notification", "auto_comment", "email"):
            return False

        # Compute hash of the new message
        message_hash = self._compute_message_hash(body, subject)

        # Calculate time threshold
        time_threshold = self.env.cr.now() - timedelta(
            hours=config["time_window_hours"]
        )

        # Search for identical messages in the time window
        identical_count = 0
        for record in self:
            if not record.message_ids:
                continue

            identical_count = 0
            for message in record.message_ids:
                # Skip messages outside time window
                if message.date < time_threshold:
                    continue

                # Check if message content matches
                msg_hash = self._compute_message_hash(message.body, message.subject)
                if msg_hash == message_hash:
                    identical_count += 1

                    # If we've hit the limit, block the message
                    if identical_count >= config["max_identical_messages"]:
                        _logger.warning(
                            "Loop prevention: Blocking duplicate message on %s (id=%s). "
                            "Found %d identical messages in the last %d hours.",
                            record._name,
                            record.id,
                            identical_count,
                            config["time_window_hours"],
                        )
                        return True

        return False

    def _message_create(self, values_list):
        """
        Override _message_create to check for message loops before creating messages.
        This is safer than overriding message_post as we can cleanly filter out
        messages that would create loops.
        """
        filtered_values_list = []

        for values in values_list:
            body = values.get("body", "")
            subject = values.get("subject", "")
            message_type = values.get("message_type", "notification")
            model = values.get("model")
            res_id = values.get("res_id")

            # Get the record to check its message history
            if model and res_id:
                try:
                    record = self.env[model].browse(res_id)
                    # All models with mail.thread mixin have _check_message_loop
                    if hasattr(record, "_check_message_loop"):
                        should_block = record._check_message_loop(
                            body, subject, message_type
                        )
                        if should_block:
                            _logger.warning(
                                "Loop prevention: Skipping message creation on %s (id=%s) "
                                "to prevent communication loop",
                                model,
                                res_id,
                            )
                            continue  # Skip this message
                except Exception as e:
                    # If we can't check, allow the message (fail open)
                    _logger.warning(
                        "Loop prevention: Error checking message loop, allowing message: %s",
                        e,
                    )

            filtered_values_list.append(values)

        # Create only the messages that passed the loop check
        if not filtered_values_list:
            return self.env["mail.message"]

        return super()._message_create(filtered_values_list)
