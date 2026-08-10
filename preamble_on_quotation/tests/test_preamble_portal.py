from odoo.fields import Command
from odoo.tests import HttpCase, tagged

MARKER = "PreambleMarkerForPortalTest"


@tagged("post_install", "-at_install")
class TestPreambleOnPortal(HttpCase):
    """The preamble is the scope of work the customer reads and agrees to, so it has
    to reach them on the portal too -- not only in the PDF. These tests also guard the
    inherit xpath: a template that no longer matches the core portal view fails at
    module load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Portal Preamble Customer"})
        cls.product = cls.env["product.product"].create(
            {"name": "Preamble Test Service", "type": "service"}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "preamble": f"<p>{MARKER}</p>",
                "order_line": [Command.create({"product_id": cls.product.id})],
            }
        )

    def _portal_body(self):
        """Fetch the customer-facing portal page the way a customer would: logged
        out, with the access token from the quotation e-mail link."""
        token = self.order._portal_ensure_token()
        response = self.url_open(f"/my/orders/{self.order.id}?access_token={token}")
        response.raise_for_status()
        return response.text

    def test_preamble_shown_on_sent_quotation(self):
        self.order.action_quotation_sent()
        self.assertEqual(self.order.state, "sent")
        self.assertIn(MARKER, self._portal_body())

    def test_preamble_shown_on_confirmed_order(self):
        """A confirmed order must keep showing the preamble: it is the agreement the
        customer accepted, and the portal is the only copy they can pull up
        themselves."""
        self.order.action_confirm()
        self.assertEqual(self.order.state, "sale")
        self.assertIn(MARKER, self._portal_body())

    def test_preamble_precedes_document_header(self):
        """The preamble carries its own title block, so it must come before the
        standard header rather than after it -- same order as the PDF cover page."""
        self.order.action_quotation_sent()
        body = self._portal_body()
        self.assertLess(
            body.index(MARKER),
            body.index('id="introduction"'),
            "the preamble must be rendered above the order's title/information block",
        )

    def test_no_empty_section_without_preamble(self):
        """An order with no preamble must not render a stray empty block."""
        self.order.preamble = False
        self.order.action_quotation_sent()
        self.assertNotIn('id="preamble"', self._portal_body())
