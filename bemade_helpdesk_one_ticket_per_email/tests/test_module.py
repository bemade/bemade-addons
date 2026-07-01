from unittest.mock import patch

from odoo.addons.mail.models.mail_thread import MailThread as CoreMailThread
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHelpdeskOneTicketPerEmail(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MailThread = cls.env["mail.thread"]
        cls.HelpdeskTicket = cls.env.get("helpdesk.ticket")

    def test_mail_thread_model_exists(self):
        """Test that mail.thread model exists"""
        self.assertIsNotNone(self.MailThread)

    def test_helpdesk_ticket_model(self):
        """Test that helpdesk.ticket model exists if installed"""
        if self.HelpdeskTicket:
            self.assertIsNotNone(self.HelpdeskTicket)

    def test_mail_thread_fields(self):
        """Test mail.thread has expected fields"""
        self.assertTrue(hasattr(self.MailThread, "message_ids"))

    # ------------------------------------------------------------------
    # _message_route_process override
    # ------------------------------------------------------------------
    # Minimal yet realistic message_dict: real dicts from message_parse()
    # always carry these keys, and other _message_route_process overrides in
    # the MRO rely on them (e.g. mass_mailing reads message_dict['references']
    # and crashes on an empty dict when installed alongside this module).
    MSG_DICT = {"references": "", "in_reply_to": ""}

    def _route(self, model, thread_id=False):
        """Build a route tuple as expected by _message_route_process:
        (model, thread_id, custom_values, user_id, alias)."""
        return (model, thread_id, {}, False, False)

    def test_no_helpdesk_routes_passthrough(self):
        """Without helpdesk routes, the override forwards routes unchanged.

        Passing an empty route list lets the core implementation loop zero
        times and return False, so no helpdesk model is required.
        """
        result = self.MailThread._message_route_process(None, dict(self.MSG_DICT), [])
        self.assertFalse(result)

    def test_non_helpdesk_routes_not_filtered(self):
        """Routes that are not helpdesk routes are forwarded untouched."""
        routes = [self._route("res.partner"), self._route("crm.lead")]
        with patch.object(
            CoreMailThread,
            "_message_route_process",
            return_value="forwarded",
        ) as mock_super:
            result = self.MailThread._message_route_process(None, dict(self.MSG_DICT), routes)
        self.assertEqual(result, "forwarded")
        mock_super.assert_called_once()
        # super() binds self, so positional args are (message, message_dict, routes)
        forwarded_routes = mock_super.call_args.args[2]
        self.assertEqual(forwarded_routes, routes)

    def test_multiple_helpdesk_routes_keep_first(self):
        """When several helpdesk routes are present, only the first is kept."""
        ticket_route = self._route("helpdesk.ticket", thread_id=1)
        team_route = self._route("helpdesk.team")
        routes = [ticket_route, team_route]
        with patch.object(
            CoreMailThread,
            "_message_route_process",
            return_value="done",
        ) as mock_super:
            result = self.MailThread._message_route_process(None, dict(self.MSG_DICT), routes)
        self.assertEqual(result, "done")
        mock_super.assert_called_once()
        forwarded_routes = mock_super.call_args.args[2]
        self.assertEqual(forwarded_routes, [ticket_route])

    def test_mixed_routes_keep_first_helpdesk(self):
        """Mixed routes are reduced to the first helpdesk route only."""
        non_helpdesk = self._route("res.partner")
        team_route = self._route("helpdesk.team")
        ticket_route = self._route("helpdesk.ticket")
        routes = [non_helpdesk, team_route, ticket_route]
        with patch.object(
            CoreMailThread,
            "_message_route_process",
            return_value=True,
        ) as mock_super:
            self.MailThread._message_route_process(None, dict(self.MSG_DICT), routes)
        forwarded_routes = mock_super.call_args.args[2]
        self.assertEqual(forwarded_routes, [team_route])

    def test_exception_wrapped_in_user_error(self):
        """Any error raised by the super call is wrapped into a UserError."""
        routes = [self._route("helpdesk.ticket")]
        with patch.object(
            CoreMailThread,
            "_message_route_process",
            side_effect=ValueError("boom"),
        ):
            with self.assertRaises(UserError):
                self.MailThread._message_route_process(None, dict(self.MSG_DICT), routes)
