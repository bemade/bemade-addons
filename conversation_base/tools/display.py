"""Sanitize an inbound email body for display inside the Odoo web client.

``mime.extract_body`` already runs every body through Odoo's
``html_sanitize``, but with its permissive defaults: every attribute and
every inline style survive. That is acceptable for a value that is only
ever stored through ``fields.Html`` (which sanitizes again), but not for a
string the inbox viewer injects straight into the live page. This module
is the display boundary: what ``conversation.transport.fetch_envelope``
returns to the browser always goes through ``sanitize_display_html``.

The profile is at least as strict as ``mail.message.body`` storage
(``fields.Html(sanitize_style=True)``: whitelisted attributes only, inline
styles reduced to Odoo's style whitelist), and additionally:

* drops ``class`` -- ``<style>`` blocks are removed anyway, so an email's
  classes could only ever match Odoo's own CSS (``fixed-top``, ``d-none``,
  ``o_main_navbar``...) and restyle or hide the surrounding UI;
* drops ``id``, ``name``, ``for``, ``tabindex``, ``accesskey`` and every
  ``data-*`` attribute -- they collide with the page's own ids, can
  clobber DOM globals, or trigger Bootstrap behaviour (``data-bs-toggle``
  is on Odoo's attribute whitelist);
* opens every link in a new browsing context with
  ``rel="noopener noreferrer"``, so a click never navigates the Odoo tab
  away and the opened page cannot reach ``window.opener``.

Never raises: a failure degrades to Odoo's standard sanitizer placeholder,
never to the unsanitized input.
"""

import logging

from markupsafe import Markup

from odoo.tools.mail import html_normalize, html_sanitize

_logger = logging.getLogger(__name__)

_DROPPED_ATTRIBUTES = frozenset({"id", "name", "for", "tabindex", "accesskey"})
_LINK_REL = "noopener noreferrer"
_PLACEHOLDER = Markup("<p>Unknown error when sanitizing</p>")


def _harden(doc):
    """lxml filter run on the already-sanitized tree (see module doc)."""
    for element in doc.iter():
        if not isinstance(element.tag, str):
            continue  # comments / processing instructions carry no attributes
        for attribute in list(element.attrib):
            if attribute in _DROPPED_ATTRIBUTES or attribute.startswith("data-"):
                del element.attrib[attribute]
        if element.tag == "a" and "href" in element.attrib:
            if element.get("href").strip():
                element.set("target", "_blank")
                element.set("rel", _LINK_REL)
            else:
                # The sanitizer blanks a javascript: URL rather than
                # dropping it, and an empty href reloads the Odoo tab.
                del element.attrib["href"]
    return doc


def sanitize_display_html(body):
    """An email body (HTML string or ``Markup``) -> ``Markup`` safe to
    render inside the Odoo web client. Falsy input -> ``""``."""
    if not body:
        return ""
    sanitized = html_sanitize(
        body,
        sanitize_attributes=True,
        sanitize_style=True,
        strip_classes=True,
    )
    if not sanitized:
        return ""
    try:
        return Markup(html_normalize(sanitized, filter_callback=_harden) or "")
    except Exception:  # noqa: BLE001 - never return unhardened markup
        _logger.warning("Could not harden an email body for display", exc_info=True)
        return _PLACEHOLDER
