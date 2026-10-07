import re

import lxml.html
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools import is_html_empty

TOKEN_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
BLOCK_TAGS = frozenset(
    ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")
)
# Containers that are also removed when a line drop leaves them empty.
CASCADE_TAGS = BLOCK_TAGS | {"ul", "ol", "table", "tbody", "thead", "tfoot"}

DEFAULT_TEMPLATE = (
    "<p><strong>{{name}}</strong></p>"
    "<p>{{job_title}}</p>"
    "<p>{{company_name}}</p>"
    "<p>Tél. / Tel. : {{work_phone}}</p>"
    "<p>Cell : {{mobile_phone}}</p>"
    '<p><a href="mailto:{{work_email}}">{{work_email}}</a></p>'
    "<p>{{company_website}}</p>"
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
        tokens are left literal.
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

        # 3. substitute remaining tokens
        def sub(text):
            if not text:
                return text
            return TOKEN_RE.sub(
                lambda m: (
                    str(values[m.group(1)] or "")
                    if m.group(1) in values
                    else m.group(0)
                ),
                text,
            )

        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            el.text = sub(el.text)
            if el is not root:
                el.tail = sub(el.tail)
            for key, attr_value in list(el.attrib.items()):
                el.set(key, sub(attr_value))

        html = escape(root.text or "")
        for child in root:
            html += Markup(lxml.html.tostring(child, encoding="unicode", method="html"))
        return Markup(html)

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
