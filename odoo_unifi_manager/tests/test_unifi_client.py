from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from .models.unifi_client import UnifiApiClient

class TestUnifiClient(TransactionCase):
    def setUp(self):
        super().setUp()
        self.test_host = "192.168.1.1"
        self.test_username = "admin"
        self.test_password = "password"

    def test_init_valid_params(self):
        """Test initialization with valid parameters"""
        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password
        )
        self.assertEqual(client.host, self.test_host)
        self.assertEqual(client.username, self.test_username)
        self.assertEqual(client.password, self.test_password)

    def test_init_invalid_host(self):
        """Test initialization with invalid host"""
        with self.assertRaises(ValidationError):
            UnifiApiClient(
                host="invalid host",
                username=self.test_username,
                password=self.test_password
            )

    def test_init_missing_credentials(self):
        """Test initialization with missing credentials"""
        with self.assertRaises(ValidationError):
            UnifiApiClient(
                host=self.test_host,
                username="",
                password=self.test_password
            )
        with self.assertRaises(ValidationError):
            UnifiApiClient(
                host=self.test_host,
                username=self.test_username,
                password=""
            )

    @patch('requests.Session')
    def test_login_success(self, mock_session):
        """Test successful login"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.headers = {}
        mock_session.return_value.post.return_value = mock_response

        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password
        )
        self.assertTrue(client.login())

    @patch('requests.Session')
    def test_login_failure(self, mock_session):
        """Test login failure"""
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.text = "Invalid credentials"
        mock_session.return_value.post.return_value = mock_response

        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password
        )
        with self.assertRaises(ValidationError):
            client.login()

    @patch('requests.Session')
    def test_get_networks(self, mock_session):
        """Test getting networks"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {
            'data': [{
                '_id': 'test_id',
                'name': 'Test Network',
                'subnet': '192.168.1.0/24',
                'vlan': 10
            }]
        }
        mock_session.return_value.get.return_value = mock_response

        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password
        )
        networks = client.get_networks()
        
        self.assertEqual(len(networks), 1)
        self.assertEqual(networks[0]['name'], 'Test Network')

    @patch('requests.Session')
    def test_rate_limits(self, mock_session):
        """Test rate limit handling"""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.headers = {
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': '60'
        }
        mock_session.return_value.get.return_value = mock_response

        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password
        )
        client.get_networks()
        
        self.assertEqual(client._rate_limit_remaining, 0)
        self.assertEqual(client._rate_limit_reset, 60)

    @patch('requests.Session')
    def test_ssl_verification(self, mock_session):
        """Test SSL verification settings"""
        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password,
            verify_ssl=True
        )
        self.assertTrue(client.verify_ssl)

        client = UnifiApiClient(
            host=self.test_host,
            username=self.test_username,
            password=self.test_password,
            verify_ssl=False
        )
        self.assertFalse(client.verify_ssl)
