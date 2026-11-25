"""The chatter's "Send message" composer shows the followers line.

Acceptance criteria:

1.  Opening "Send message" on a record shows, under the To row, the
    followers that will also be notified.
2.  Adding one of them as a recipient updates the line (debounced RPC); once
    nobody else is reached it reads "No followers will be notified".
3.  "Log note" shows no such line.
"""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestChatterPreviewTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"].with_context(tracking_disable=True)
        cls.contact = Partner.create(
            {"name": "Carol Tourcontact", "email": "carol.tour@example.com"}
        )
        # No email on the record itself, so the chatter suggests no recipient.
        cls.record = Partner.create({"name": "Preview Tour Company"})
        cls.record.message_unsubscribe(partner_ids=cls.record.message_partner_ids.ids)
        cls.record.message_subscribe(partner_ids=cls.contact.ids)

    def test_chatter_preview_tour(self):
        self.start_tour(
            "/odoo/res.partner/%s" % self.record.id,
            "bemade_mail_notified_preview_tour",
            login="admin",
        )
