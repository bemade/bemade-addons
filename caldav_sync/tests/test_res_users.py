from odoo.tests import TransactionCase
from unittest.mock import patch, MagicMock
from .common import CaldavTestCommon


class TestUsers(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_caldav_enabled_false_without_url(self):
        user = self._generate_user("test", "test")
        self.assertFalse(user.is_caldav_enabled)

    @patch("caldav.DAVClient")
    def test_caldav_connection_succeeds_but_not_calendar(self, MockDAVClient):
        user = self._generate_user("test", "test", "https://example.com/abc123")
        # Create a mock client and mock calendar
        mock_client = MockDAVClient.return_value
        mock_calendar = MagicMock()
        mock_client.calendar.return_value = mock_calendar

        # Mock the events method to raise an exception
        mock_calendar.events.side_effect = Exception("Failed to get events")

        # An exception should not be raised because we need to continue to sync other
        # users' calendars. Instead the exception message is simply logged to error.
        with self.assertLogs("odoo.addons.caldav_sync.models.res_users", "ERROR"):
            user._get_caldav_events()

        # Ensure the is_caldav_enabled is set to False
        self.assertFalse(user.is_caldav_enabled)
