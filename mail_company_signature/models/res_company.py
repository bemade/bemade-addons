import re

import lxml.html
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools import html2plaintext, is_html_empty

TOKEN_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
BLOCK_TAGS = frozenset(
    ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")
)
# Containers that are also removed when a line drop leaves them empty.
CASCADE_TAGS = BLOCK_TAGS | {"ul", "ol", "table", "tbody", "thead", "tfoot"}
# Rich-text values (``Markup``) are inserted as HTML through this marker,
# which survives the lxml serialization untouched.
HTML_MARKER = "MCSHTML%sMCSEND"
HTML_MARKER_RE = re.compile(r"MCSHTML(\w+?)MCSEND")

DEFAULT_TEMPLATE = (
    "<p><strong>{{name}}</strong></p>"
    "<p>{{job_title}}</p>"
    "<p>{{company_name}}</p>"
    "<p>Tél. / Tel. : {{work_phone}}</p>"
    "<p>Cell : {{mobile_phone}}</p>"
    '<p><a href="mailto:{{work_email}}">{{work_email}}</a></p>'
    "<p>{{company_website}}</p>"
    "<div>{{company_notice}}</div>"
)


class ResCompany(models.Model):
    _inherit = "res.company"

    def _default_company_signature_template(self):
        return DEFAULT_TEMPLATE

    company_signature_enforced = fields.Boolean(
        string="Enforce company-standard signature",
        default=False,
        groups="base.group_system",
        help="When enabled, the email signature of every internal user of "
        "this company is generated from the template and cannot be edited.",
    )
    company_signature_template = fields.Html(
        string="Company signature template",
        default=_default_company_signature_template,
        sanitize=True,
        groups="base.group_system",
    )
    company_signature_notice = fields.Html(
        string="Company notice",
        sanitize=True,
        groups="base.group_system",
        help="Temporary notice (closure, holiday hours...) shown where the "
        "template has {{company_notice}}.",
    )
    company_signature_notice_until = fields.Date(
        string="Show until",
        groups="base.group_system",
        help="Last day the company notice is shown. A daily scheduled action "
        "removes it afterwards. Leave empty to show it until it is cleared.",
    )

    def _company_signature_notice_value(self):
        """The notice as ``Markup`` while it is shown, else an empty string."""
        self.ensure_one()
        company = self.sudo()
        notice = company.company_signature_notice
        until = company.company_signature_notice_until
        if is_html_empty(notice) or (
            until and until < fields.Date.context_today(company)
        ):
            return ""
        return Markup(notice)

    @api.model
    def _cron_expire_company_signature_notice(self):
        """Clear the notices whose last day has passed (signatures follow)."""
        expired = self.sudo().search(
            [
                ("company_signature_notice_until", "!=", False),
                (
                    "company_signature_notice_until",
                    "<",
                    fields.Date.context_today(self),
                ),
            ]
        )
        if expired:
            expired.write(
                {
                    "company_signature_notice": False,
                    "company_signature_notice_until": False,
                }
            )

    # ------------------------------------------------------------------
    # Policy transitions
    # ------------------------------------------------------------------
    def write(self, vals):
        if "company_signature_enforced" in vals:
            Users = self.env["res.users"].sudo().with_context(active_test=False)
            new = bool(vals["company_signature_enforced"])
            changing = self.sudo().filtered(
                lambda c: bool(c.company_signature_enforced) != new
            )
            users = Users.search(
                [("share", "=", False), ("company_id", "in", changing.ids)]
            )
            if new:
                # Users flagged as generated still hold the signature produced
                # last time: keep their older (real) backup untouched.
                for user in users.filtered(lambda u: not u.signature_is_generated):
                    user.personal_signature_backup = user.signature
            else:
                users.signature_is_generated = True
        return super().write(vals)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _company_signature_render(self, values):
        """Render the template with ``values`` (dict token -> str).

        A block element is dropped (with its static text) when every token it
        directly owns is a known placeholder with an empty value. Unknown
        tokens are left literal. A ``Markup`` value is inserted as HTML (as
        plain text inside an attribute); a ``<p>`` holding only such a token
        becomes a ``<div>`` so the value's own paragraphs are not nested.
        """
        self.ensure_one()
        template = self.sudo().company_signature_template
        if is_html_empty(template):
            return Markup("")
        # The sanitizer may percent-encode braces inside href attributes.
        template = re.sub(r"%7B%7B", "{{", template, flags=re.I)
        template = re.sub(r"%7D%7D", "}}", template, flags=re.I)
        root = lxml.html.fragment_fromstring(template, create_parent="div")

        def tokens_of(text):
            return TOKEN_RE.findall(text) if text else []

        def block_of(el):
            block = None
            while el is not None and el is not root:
                if el.tag in BLOCK_TAGS:
                    block = el
                    break
                el = el.getparent()
            return block

        # 1. assign tokens to lines
        owned = {}
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            found = tokens_of(el.text)
            for attr_value in el.attrib.values():
                found += tokens_of(attr_value)
            if el is not root and found:
                owned.setdefault(block_of(el), []).extend(found)
            elif el is root and found:
                owned.setdefault(None, []).extend(found)
            parent = el.getparent()
            tail_tokens = tokens_of(el.tail)
            if tail_tokens and parent is not None:
                owned.setdefault(
                    block_of(parent) if parent is not root else None, []
                ).extend(tail_tokens)

        def is_blank(name):
            return name in values and not (values[name] or "").strip()

        def depth(el):
            return len(list(el.iterancestors()))

        # 2. line-drop rule, deepest block first
        blocks = [b for b in owned if b is not None]
        blocks.sort(key=depth, reverse=True)
        for block in blocks:
            if block.getparent() is None:  # already removed with a parent
                continue
            if all(is_blank(name) for name in owned[block]):
                self._company_signature_drop(block, root)

        def is_html(name):
            return isinstance(values.get(name), Markup)

        # 3. a paragraph holding only a rich-text token must not nest blocks
        for el in root.iter("p"):
            name = TOKEN_RE.fullmatch((el.text or "").strip())
            if name and is_html(name.group(1)) and not len(el):
                el.tag = "div"

        # 4. substitute remaining tokens
        def replace(match, attribute=False):
            name = match.group(1)
            if name not in values:
                return match.group(0)
            if is_html(name):
                if attribute:
                    return html2plaintext(values[name]).strip()
                return HTML_MARKER % name
            return str(values[name] or "")

        def sub(text, attribute=False):
            if not text:
                return text
            return TOKEN_RE.sub(lambda m: replace(m, attribute), text)

        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            el.text = sub(el.text)
            if el is not root:
                el.tail = sub(el.tail)
            for key, attr_value in list(el.attrib.items()):
                el.set(key, sub(attr_value, attribute=True))

        html = escape(root.text or "")
        for child in root:
            html += Markup(lxml.html.tostring(child, encoding="unicode", method="html"))
        return Markup(
            HTML_MARKER_RE.sub(
                lambda m: str(values[m.group(1)]) if is_html(m.group(1)) else m.group(0),
                html,
            )
        )

    @api.model
    def _company_signature_drop(self, element, root):
        """Remove ``element`` keeping its tail, then cascade to empty parents."""
        while True:
            parent = element.getparent()
            tail = element.tail
            previous = element.getprevious()
            if tail:
                if previous is not None:
                    previous.tail = (previous.tail or "") + tail
                else:
                    parent.text = (parent.text or "") + tail
            parent.remove(element)
            if parent is root or parent.tag not in CASCADE_TAGS:
                return
            empty = (
                not (parent.text or "").strip()
                and all(
                    child.tag == "br" and not (child.tail or "").strip()
                    for child in parent
                )
                and not any(
                    isinstance(c.tag, str) and c.tag != "br" for c in parent
                )
            )
            if not empty:
                return
            element = parent
