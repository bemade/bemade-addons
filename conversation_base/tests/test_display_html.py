# Acceptance criteria (inbox viewer: render sanitized HTML bodies):
#   - The body fetch_envelope returns for display is sanitized server-side,
#     at least as strictly as mail.message.body storage: no script/style/
#     iframe/object/embed/form/input/meta/link/base, no on* handlers, no
#     javascript: URLs, inline styles reduced to Odoo's style whitelist.
#   - Attributes that let an email restyle, hide or overlay Odoo's own UI
#     (class, id, name, data-*) are removed.
#   - Every link opens in a new browsing context with rel=noopener
#     noreferrer.
#   - Plaintext bodies stay escaped text (never interpolated as markup).
#   - Empty bodies stay empty; a hardening failure degrades to Odoo's
#     sanitizer placeholder, never to raw HTML.
#   - Only the body is touched: every other envelope key is returned as-is.

import email
import email.policy
import re
from unittest.mock import patch

from lxml import html as lxml_html

from odoo.tests import TransactionCase
from odoo.tools.mail import _Cleaner
from odoo.tools.misc import mute_logger

from odoo.addons.conversation_base.tools import display, mime

HOSTILE = (
    '<html><head><meta http-equiv="refresh" content="0;url=https://evil.example">'
    '<link rel="stylesheet" href="https://evil.example/x.css">'
    '<base href="https://evil.example/">'
    "<style>.o_main_navbar{display:none!important}</style></head>"
    '<body onload="window.hacked=1">'
    "<script>window.hacked=1</script>"
    '<div class="o_main_navbar fixed-top position-fixed d-none" id="o_main_navbar"'
    ' data-bs-toggle="modal" name="location">Navbar lookalike</div>'
    '<p style="position:fixed; top:0; left:0; z-index:99999; color:red">Overlay</p>'
    '<img src="x" onerror="window.hacked=1">'
    '<a href="javascript:window.hacked=1" onclick="window.hacked=1">bad link</a>'
    '<iframe src="https://evil.example"></iframe>'
    '<object data="https://evil.example/x.swf"></object>'
    '<embed src="https://evil.example/x.swf">'
    '<form action="https://evil.example"><input name="password" type="password">'
    "</form>"
    "</body></html>"
)

_DANGEROUS_TAGS = (
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "form",
    "input",
    "meta",
    "link",
    "base",
)


def _tree(markup):
    return lxml_html.fragment_fromstring(str(markup), create_parent="div")


def _style_properties(tree):
    props = set()
    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue
        for declaration in (element.get("style") or "").split(";"):
            if ":" in declaration:
                props.add(declaration.split(":", 1)[0].strip().lower())
    return props


def _attribute_names(tree):
    return {
        name
        for element in tree.iter()
        if isinstance(element.tag, str)
        for name in element.attrib
    }


class TestDisplayHtml(TransactionCase):
    def test_dangerous_markup_removed(self):
        body = display.sanitize_display_html(HOSTILE)
        tree = _tree(body)
        for tag in _DANGEROUS_TAGS:
            self.assertFalse(tree.findall(".//" + tag), f"<{tag}> survived: {body}")
        for name in _attribute_names(tree):
            self.assertFalse(name.startswith("on"), f"{name} survived: {body}")
        self.assertNotIn("javascript:", body)
        # The blanked javascript: link is inert, not a link to "" (which
        # would reload the Odoo tab).
        self.assertFalse(tree.findall(".//a[@href]"), body)
        self.assertIn("bad link", body)
        self.assertNotIn("hacked", body)
        props = _style_properties(tree)
        for prop in ("position", "z-index", "top", "left"):
            self.assertNotIn(prop, props)
        # Style is sanitized, not blanket-stripped: whitelisted ones stay.
        self.assertIn("color", props)
        self.assertLessEqual(props, set(_Cleaner._style_whitelist))
        # The readable text is still there.
        self.assertIn("Overlay", body)
        self.assertIn("Navbar lookalike", body)

    def test_layout_hijack_attributes_removed(self):
        body = display.sanitize_display_html(HOSTILE)
        names = _attribute_names(_tree(body))
        for name in ("class", "id", "name"):
            self.assertNotIn(name, names, body)
        self.assertFalse([n for n in names if n.startswith("data-")], body)

    def test_formatting_kept_and_links_hardened(self):
        body = display.sanitize_display_html(
            "<p>Hello <strong>world</strong></p><ul><li>a</li></ul>"
            "<table><tr><td>cell</td></tr></table>"
            '<a href="https://example.com/one">one</a>'
            '<a href="https://example.com/two" target="_self" rel="opener">two</a>'
            "<a>no href</a>"
            '<a href=" ">blank href</a>'
        )
        tree = _tree(body)
        for tag in ("p", "strong", "ul", "li", "table", "td"):
            self.assertTrue(tree.findall(".//" + tag), f"<{tag}> lost: {body}")
        links = tree.findall(".//a[@href]")
        self.assertEqual(len(links), 2)
        for link in links:
            self.assertEqual(link.get("target"), "_blank")
            rel = link.get("rel").split()
            self.assertIn("noopener", rel)
            self.assertIn("noreferrer", rel)
            self.assertNotIn("opener", rel)

    def test_at_least_as_strict_as_mail_message(self):
        """Parity floor: nothing the display keeps is something core
        mail.message body storage would have dropped."""
        stored = self.env["mail.message"].create(
            {"body": HOSTILE, "model": False, "res_id": False}
        ).body
        stored_tree = _tree(stored)
        display_tree = _tree(display.sanitize_display_html(HOSTILE))
        self.assertLessEqual(
            _attribute_names(display_tree) - {"target", "rel"},
            _attribute_names(stored_tree),
        )
        self.assertLessEqual(
            _style_properties(display_tree), _style_properties(stored_tree)
        )
        self.assertLessEqual(
            {el.tag for el in display_tree.iter() if isinstance(el.tag, str)},
            {el.tag for el in stored_tree.iter() if isinstance(el.tag, str)},
        )

    def test_plaintext_stays_text(self):
        message = email.message_from_string(
            "Content-Type: text/plain; charset=UTF-8\n\n"
            "First line\nSecond line\n<b>not markup</b>\n",
            policy=email.policy.default,
        )
        body = display.sanitize_display_html(mime.extract_body(message))
        tree = _tree(body)
        self.assertFalse(tree.findall(".//b"), body)
        self.assertTrue(tree.findall(".//br"), body)
        self.assertIn("&lt;b&gt;not markup&lt;/b&gt;", body)
        self.assertIn("<b>not markup</b>", tree.text_content())

    def test_empty_and_failure(self):
        self.assertEqual(display.sanitize_display_html(""), "")
        self.assertEqual(display.sanitize_display_html(False), "")
        self.assertEqual(display.sanitize_display_html(None), "")
        with patch.object(
            display, "html_normalize", side_effect=RuntimeError("boom")
        ), mute_logger("odoo.addons.conversation_base.tools.display"):
            body = display.sanitize_display_html(HOSTILE)
        self.assertEqual(body, display._PLACEHOLDER)
        self.assertNotIn("hacked", body)

    def test_fetch_envelope_sanitizes_body_only(self):
        transport = self.env["conversation.transport"].create(
            {"name": "Display Transport", "browsable": True}
        )
        stub = {
            "external_id": "ext-1",
            "subject": "<b>Quote</b> request",
            "email_from": "<script>@example.com",
            "attachments": [{"filename": "<i>a</i>.pdf"}],
            "body": HOSTILE,
        }
        transport_model = type(transport)
        with patch.object(
            transport_model, "_fetch", return_value={"raw": True}, autospec=True
        ), patch.object(
            transport_model, "_normalize", return_value=dict(stub), autospec=True
        ):
            envelope = transport.fetch_envelope(transport.id, "ext-1")
        self.assertEqual(envelope["body"], display.sanitize_display_html(HOSTILE))
        self.assertNotIn("<script", envelope["body"])
        self.assertTrue(re.search(r"<p[^>]*>Overlay</p>", envelope["body"]))
        for key in ("external_id", "subject", "email_from", "attachments"):
            self.assertEqual(envelope[key], stub[key])
