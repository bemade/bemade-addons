# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import _, api, models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _notified_preview_followers(self, exclude_partner_ids=(), subtype_id=None):
        """Followers that a message posted on this record will also notify.

        Display only. Reads the same data as the send path
        (``mail.followers._get_recipient_data``, see
        ``mail.thread._notify_get_recipients``): active followers subscribed to
        the subtype (Discussions by default), minus the current user (the
        author is not notified) and minus ``exclude_partner_ids`` (partners
        already in To/Cc/Bcc).

        :return: list of ``{id, name, notif: 'email'|'inbox', has_email}``,
          sorted by name.
        """
        self.ensure_one()
        self.check_access("read")
        if subtype_id is None:
            subtype_id = self.env["ir.model.data"]._xmlid_to_res_id("mail.mt_comment")
        recipients_data = self.env["mail.followers"]._get_recipient_data(
            self, "comment", subtype_id
        )[self.id]
        excluded = set(exclude_partner_ids or ()) | {self.env.user.partner_id.id}
        followers = []
        for pid, pdata in recipients_data.items():
            if not pid or pid in excluded:
                continue
            if not pdata["active"] or not pdata["is_follower"]:
                continue
            followers.append(
                {
                    "id": pid,
                    "name": pdata["name"] or "",
                    "notif": "inbox" if pdata["notif"] == "inbox" else "email",
                    "has_email": bool(pdata["email_normalized"]),
                }
            )
        followers.sort(key=lambda f: (f["name"].lower(), f["id"]))
        return followers

    @api.model
    def _notified_preview_line(self, followers):
        """Render the one-line summary of ``_notified_preview_followers``."""
        if not followers:
            return _("No followers will be notified")
        emailed = [
            f["name"] for f in followers if f["notif"] == "email" and f["has_email"]
        ]
        inbox = [f["name"] for f in followers if f["notif"] == "inbox"]
        lost = [
            f["name"] for f in followers if f["notif"] == "email" and not f["has_email"]
        ]
        groups = []
        if emailed:
            groups.append(_("%(names)s (email)", names=", ".join(emailed)))
        if inbox:
            groups.append(_("%(names)s (Odoo inbox)", names=", ".join(inbox)))
        if lost:
            groups.append(
                _("⚠ %(names)s (no email — won't receive)", names=", ".join(lost))
            )
        return _("Also sent to followers: %(groups)s", groups=" · ".join(groups))

    def get_notified_preview(self, exclude_partner_ids=None):
        """Public (RPC) entry point used by the chatter's Send message composer.

        :return: ``{followers, line, warn}``; ``warn`` is True when a follower
          to be emailed has no email address.
        """
        exclude = [pid for pid in exclude_partner_ids or () if isinstance(pid, int)]
        followers = self._notified_preview_followers(exclude_partner_ids=exclude)
        return {
            "followers": followers,
            "line": self._notified_preview_line(followers),
            "warn": any(
                f["notif"] == "email" and not f["has_email"] for f in followers
            ),
        }
