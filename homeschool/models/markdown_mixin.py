# -*- coding: utf-8 -*-
"""Markdown stored as text, rendered to sanitized HTML on demand.

Models declare ``_markdown_fields = ("intention", "steps")`` and get a computed
``<name>_html`` companion for each, provided they declare those Html fields with
``compute="_compute_markdown_html"`` (see :func:`markdown_html_field`).
"""
import markdown as _markdown

from odoo import api, fields, models
from odoo.tools import html_sanitize

_MD_EXTENSIONS = ["tables", "sane_lists", "nl2br"]


def render_markdown(text):
    """Render Markdown text to sanitized HTML (empty string for empty input)."""
    if not text:
        return ""
    html = _markdown.markdown(text, extensions=_MD_EXTENSIONS, output_format="html")
    return html_sanitize(html, sanitize_tags=True, sanitize_attributes=True, strip_style=True)


def markdown_html_field(source, **kwargs):
    """An Html field rendered from the Markdown text field ``source``."""
    return fields.Html(
        compute="_compute_markdown_html",
        sanitize=False,
        readonly=True,
        store=False,
        help="Rendered from the Markdown field %r." % source,
        **kwargs,
    )


class MarkdownMixin(models.AbstractModel):
    _name = "homeschool.markdown.mixin"
    _description = "Markdown rendering mixin"

    _markdown_fields = ()

    @api.depends(lambda self: self._markdown_fields)
    def _compute_markdown_html(self):
        for rec in self:
            for name in rec._markdown_fields:
                rec[name + "_html"] = render_markdown(rec[name])
