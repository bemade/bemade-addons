#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

import logging

from markupsafe import Markup

from odoo import _, models

_logger = logging.getLogger(__name__)

try:
    import vobject
except ImportError:
    # Same posture as odoo/addons/calendar: without vobject there is no ICS to
    # enrich, and core already logs the missing dependency.
    vobject = None

# Outlook draws a native join button off these two; it ignores URL and
# CONFERENCE entirely.
MICROSOFT_URL_PROPERTIES = (
    "X-MICROSOFT-SKYPETEAMSMEETINGURL",
    "X-MICROSOFT-ONLINEMEETINGCONFLINK",
)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    def _get_customer_description(self):
        """Append the video call URL to the description used by calendar exports.

        DESCRIPTION is the only property every calendar client renders in the
        meeting body, so it is what actually makes the link reachable in
        Outlook and Apple Calendar.
        """
        description = super()._get_customer_description() or ""
        url = self.videocall_location
        if not url or url in description:
            return description
        # The leading <br/> is load-bearing: without it html2plaintext folds the
        # join line onto the end of the contact-details block in the ICS
        # DESCRIPTION, which is where most clients show it.
        return description + (
            Markup("<p><br/>%s</p>") % _("Join the video call: %s", url)
        )

    def _get_ics_file(self):
        """Add the video call URL to the generated ICS.

        Core builds and serializes the calendar in one pass with no hook, so we
        re-read its output and add the properties it never writes. Events
        without a video call URL are returned exactly as core produced them.
        """
        result = super()._get_ics_file()
        if not vobject:
            return result

        for meeting in self:
            url = meeting.videocall_location
            content = result.get(meeting.id)
            if not url or not content:
                continue
            try:
                cal = vobject.readOne(content.decode("utf-8"))
            except Exception:  # noqa: BLE001 - never break the invitation email
                _logger.warning(
                    "Could not parse the ICS of calendar.event %s to add the "
                    "video call URL; sending it unmodified.",
                    meeting.id,
                    exc_info=True,
                )
                continue
            self._add_videocall_ics_properties(cal.vevent, url)
            result[meeting.id] = cal.serialize().encode("utf-8")

        return result

    def _add_videocall_ics_properties(self, vevent, url):
        """Write the video call URL onto ``vevent``, never overwriting core."""
        # An explicit location is authoritative: only fill in the blank.
        if "location" not in vevent.contents:
            vevent.add("location").value = url

        if "url" not in vevent.contents:
            vevent.add("url").value = url

        if "conference" not in vevent.contents:
            # RFC 7986: a CONFERENCE without VALUE/FEATURE is ignored by
            # conforming clients.
            conference = vevent.add("conference")
            conference.value = url
            conference.params["VALUE"] = ["URI"]
            conference.params["FEATURE"] = ["VIDEO"]
            conference.params["LABEL"] = [
                _("Odoo Discuss")
                if self.videocall_source == "discuss"
                else _("Video call")
            ]

        for name in MICROSOFT_URL_PROPERTIES:
            if name.lower() not in vevent.contents:
                vevent.add(name).value = url
