"""Use case: find the user signatures a template printed in its rendered body.

Acceptance criteria
-------------------
* A signature printed inside inline markup with no separator (several paragraphs
  wrapped in ``<strong>`` inside a ``<p>``) is removed with its wrapper.
* A signature printed after ``--`` in its own block is removed with the ``--``.
* A signature printed as bare sibling paragraphs (no wrapper) is removed.
* A name-only signature is removed only after ``--``; the bare name elsewhere
  is kept.
* The rest of the body is kept; a body without signature is returned unchanged.
"""

from markupsafe import Markup

from odoo.tests import BaseCase, tagged

from ..tools import strip_printed_signatures

SIG = "<p>Sam Signer</p><p>Head of Widgets</p><p>Example Widgets Inc.</p>"
SIGS = [(SIG, "Sam Signer")]


@tagged("post_install", "-at_install")
class TestStripTools(BaseCase):
    def test_inline_wrapped_without_separator(self):
        body = Markup(
            "<div><p>Your order is confirmed.<br><br></p>"
            "<p><strong>%s</strong><br></p></div>" % SIG
        )
        result = strip_printed_signatures(body, SIGS)
        self.assertNotIn("Example Widgets Inc.", result)
        self.assertIn("Your order is confirmed.", result)

    def test_after_separator(self):
        body = Markup("<p>Hello</p><div>--<br>%s</div>" % SIG)
        result = strip_printed_signatures(body, SIGS)
        self.assertEqual(str(result).strip(), "<p>Hello</p>")

    def test_bare_sibling_run(self):
        body = Markup("<p>Hello</p>%s<p>PS: thanks</p>" % SIG)
        result = strip_printed_signatures(body, SIGS)
        self.assertNotIn("Head of Widgets", result)
        self.assertIn("<p>Hello</p>", result)
        self.assertIn("PS: thanks", result)

    def test_name_only_signature(self):
        sigs = [("<div>Sam Signer</div>", "Sam Signer")]
        body = Markup("<p>Your contact: <span>Sam Signer</span></p><div>--<br><div>Sam Signer</div></div>")
        result = strip_printed_signatures(body, sigs)
        self.assertEqual(str(result).count("Sam Signer"), 1)
        self.assertIn("Your contact: <span>Sam Signer</span>", result)

    def test_unsigned_body_unchanged(self):
        body = Markup("<p>Nothing to see</p>")
        self.assertIs(strip_printed_signatures(body, SIGS), body)
