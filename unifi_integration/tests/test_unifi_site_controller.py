# -*- coding: utf-8 -*-

from odoo.tests import common
from odoo.exceptions import ValidationError
import unittest.mock as mock
import json
import tempfile
import base64
import os

class TestUnifiSiteController(common.TransactionCase):
    """Tests pour le modèle unifi.site.controller
    
    Cette classe de test vérifie le bon fonctionnement des méthodes API
    du modèle unifi.site.controller, y compris la gestion des certificats auto-signés.
    """
    
    def setUp(self):
        """Configuration initiale pour les tests
        
        Crée un site de test avec une configuration de contrôleur.
        """
        super(TestUnifiSiteController, self).setUp()
        
        # Créer un site de test
        self.test_site = self.env['unifi.site'].create({
            'name': 'Site de Test',
            'description': 'Site de test pour les tests unitaires',
            'api_type': 'controller'
        })
        
        # Créer une configuration de contrôleur pour le site
        self.test_controller = self.env['unifi.site.controller'].create({
            'site_id': self.test_site.id,
            'host': 'test.example.com',
            'port': 443,
            'username': 'testuser',
            'password': 'testpassword',
            'verify_ssl': True,
            'controller_type': 'udm'
        })
    
    def test_check_required_fields(self):
        """Teste la validation des champs requis
        
        Vérifie que la méthode _check_required_fields lève une exception
        si les champs requis ne sont pas renseignés.
        """
        # Créer un site sans les champs requis
        site_without_fields = self.env['unifi.site'].create({
            'name': 'Site sans champs',
            'description': 'Site sans les champs requis',
            'api_type': 'controller'
        })
        
        # Vérifier que la méthode lève une exception
        with self.assertRaises(ValidationError):
            self.env['unifi.site.controller']._check_required_fields(site_without_fields)
    
    @mock.patch('odoo.addons.unifi_integration.models.unifi_site_controller.requests.Session')
    def test_authenticate_success(self, mock_session):
        """Teste l'authentification réussie
        
        Vérifie que la méthode _authenticate fonctionne correctement
        lorsque l'authentification réussit.
        """
        # Configurer le mock pour simuler une réponse réussie
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'X-CSRF-Token': 'test-csrf-token'}
        mock_response.text = json.dumps({'meta': {'rc': 'ok'}})
        
        mock_session_instance = mock_session.return_value
        mock_session_instance.post.return_value = mock_response
        mock_session_instance.cookies.items.return_value = [('cookie1', 'value1')]
        
        # Appeler la méthode _authenticate
        result = self.test_controller._authenticate()
        
        # Vérifier que l'authentification a réussi
        self.assertTrue(result)
        self.assertEqual(self.test_controller.csrf_token, 'test-csrf-token')
        self.assertEqual(json.loads(self.test_controller.session_cookies), {'cookie1': 'value1'})
    
    @mock.patch('odoo.addons.unifi_integration.models.unifi_site_controller.requests.Session')
    def test_authenticate_failure(self, mock_session):
        """Teste l'échec d'authentification
        
        Vérifie que la méthode _authenticate gère correctement
        les échecs d'authentification.
        """
        # Configurer le mock pour simuler une réponse d'échec
        mock_response = mock.MagicMock()
        mock_response.status_code = 401
        mock_response.text = json.dumps({'meta': {'rc': 'error', 'msg': 'Invalid credentials'}})
        
        mock_session_instance = mock_session.return_value
        mock_session_instance.post.return_value = mock_response
        
        # Appeler la méthode _authenticate
        result = self.test_controller._authenticate()
        
        # Vérifier que l'authentification a échoué
        self.assertFalse(result)
    
    @mock.patch('odoo.addons.unifi_integration.models.unifi_site_controller.requests.Session')
    def test_make_request_success(self, mock_session):
        """Teste une requête API réussie
        
        Vérifie que la méthode _make_request fonctionne correctement
        lorsque la requête réussit.
        """
        # Configurer le test_controller avec des cookies de session
        self.test_controller.session_cookies = json.dumps({'cookie1': 'value1'})
        self.test_controller.csrf_token = 'test-csrf-token'
        
        # Configurer le mock pour simuler une réponse réussie
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({'data': [{'id': 1, 'name': 'test'}]})
        mock_response.json.return_value = {'data': [{'id': 1, 'name': 'test'}]}
        
        mock_session_instance = mock_session.return_value
        mock_session_instance.get.return_value = mock_response
        
        # Appeler la méthode _make_request
        success, data, status_code = self.test_controller._make_request('GET', 'devices', 'default')
        
        # Vérifier que la requête a réussi
        self.assertTrue(success)
        self.assertEqual(status_code, 200)
        self.assertEqual(data, {'data': [{'id': 1, 'name': 'test'}]})
    
    @mock.patch('odoo.addons.unifi_integration.models.unifi_site_controller.requests.Session')
    def test_make_request_with_custom_cert(self, mock_session):
        """Teste une requête API avec un certificat personnalisé
        
        Vérifie que la méthode _make_request utilise correctement
        un certificat SSL personnalisé lorsqu'il est fourni.
        """
        # Créer un certificat de test
        cert_content = b"-----BEGIN CERTIFICATE-----\nMIIDazCCAlOgAwIBAgIUJlq+zz4DP9fxg3LB9BQl0haIFr4wDQYJKoZIhvcNAQEL\nBQAwRTELMAkGA1UEBhMCQVUxEzARBgNVBAgMClNvbWUtU3RhdGUxITAfBgNVBAoM\nGEludGVybmV0IFdpZGdpdHMgUHR5IEx0ZDAeFw0yMzAzMjMxODUwMzJaFw0yNDAz\nMjIxODUwMzJaMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEw\nHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwggEiMA0GCSqGSIb3DQEB\nAQUAA4IBDwAwggEKAoIBAQDK4+VKWLJ5Qhytr5GE7XNd4YQlpbgpyFjxfOiLYWdY\ntZNptYfs1VSQgDlzqJsgLDEAeRBDJSPO5xiwURKPezCCfCjMgr9MWOGgP/OLiW9j\nLJQVYdJnw+HhTMFmcOmzSi0OjCHkZhBjHuUwgXhCbV/1sCQV1BiDmGYo5rYRnxPW\nVxgp2Pc+ABwCzTz3jLxozfeY3C9c0qiPgbYG+qFzidkBUqTpFIDi+iYMR3WfvCJt\nV/gYYKzQUi+tmjVtRIpIm5UIxYGK3xMwDVYCPKKQYHDvN9SXt+hopVzQhHkIEL4a\nXMKiBaCTjBQnY3rAJbwVjh9nVdCCIL3JMzwGn+7rAgMBAAGjUzBRMB0GA1UdDgQW\nBBRXLpff0CDtLkoBFyVWyZGJ5HBsNjAfBgNVHSMEGDAWgBRXLpff0CDtLkoBFyVW\nyZGJ5HBsNjAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQC6p0Ay\nTNfJXoKlZ8KQHj9/j8ZJnMZ5LXxU6TzZeHNGJFrCCKZYh+iUWLkV5x9JxQo6npzH\nHJ94JI6HoJb8IWVe1xwNfv8D6mYky0WFcBsAVV3Bq2JZpGsXHT5lUv3/1+8qdEFP\nNWR9QUL+UhpK4p9bHKX3h8qEQGIO1t5EJVTNiZEVWQrJY9zLG6MjBwL0TBQ3nFvv\n4C5Ctw+8jnrTp6qdGFHlKLbBV5KXQtgbQx9nPgLlHVEYjSKQoWsJLfD9MaHAIUKW\nGGRGY3iUzQs8yiHBRDX9xyf+Jg75KnCi9FVkrF/JOxzZKGGV8Qn3/Yja+uLMnwKE\nRs8XuQwXQFYkKLvL\n-----END CERTIFICATE-----"
        cert_filename = "test_cert.pem"
        
        # Configurer le test_controller avec un certificat personnalisé
        self.test_controller.ssl_cert_file = base64.b64encode(cert_content)
        self.test_controller.ssl_cert_filename = cert_filename
        
        # Créer un fichier temporaire pour le certificat
        fd, cert_path = tempfile.mkstemp(suffix='.pem')
        try:
            os.write(fd, cert_content)
            os.close(fd)
            
            # Définir le chemin du certificat
            self.test_controller.ssl_cert_path = cert_path
            
            # Configurer le test_controller avec des cookies de session
            self.test_controller.session_cookies = json.dumps({'cookie1': 'value1'})
            self.test_controller.csrf_token = 'test-csrf-token'
            
            # Configurer le mock pour simuler une réponse réussie
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_response.text = json.dumps({'data': [{'id': 1, 'name': 'test'}]})
            mock_response.json.return_value = {'data': [{'id': 1, 'name': 'test'}]}
            
            mock_session_instance = mock_session.return_value
            mock_session_instance.get.return_value = mock_response
            
            # Appeler la méthode _make_request
            success, data, status_code = self.test_controller._make_request('GET', 'devices', 'default')
            
            # Vérifier que la requête a réussi
            self.assertTrue(success)
            self.assertEqual(status_code, 200)
            
            # Vérifier que le certificat personnalisé a été utilisé
            mock_session_instance.get.assert_called_with(
                mock.ANY,  # URL
                params=mock.ANY,  # Params
                headers=mock.ANY,  # Headers
                verify=cert_path,  # Verify avec le certificat personnalisé
                timeout=10
            )
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(cert_path):
                os.unlink(cert_path)
    
    @mock.patch('odoo.addons.unifi_integration.models.unifi_site_controller.requests.Session')
    def test_make_request_session_expired(self, mock_session):
        """Teste le renouvellement de session
        
        Vérifie que la méthode _make_request gère correctement
        l'expiration de la session et tente une nouvelle authentification.
        """
        # Configurer le test_controller avec des cookies de session
        self.test_controller.session_cookies = json.dumps({'cookie1': 'value1'})
        
        # Configurer le mock pour simuler une réponse d'expiration de session
        mock_response_expired = mock.MagicMock()
        mock_response_expired.status_code = 401
        mock_response_expired.text = json.dumps({'meta': {'rc': 'error', 'msg': 'Session expired'}})
        
        # Configurer le mock pour simuler une réponse réussie après réauthentification
        mock_response_success = mock.MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = json.dumps({'data': [{'id': 1, 'name': 'test'}]})
        mock_response_success.json.return_value = {'data': [{'id': 1, 'name': 'test'}]}
        
        mock_session_instance = mock_session.return_value
        mock_session_instance.get.side_effect = [mock_response_expired, mock_response_success]
        
        # Configurer le mock pour simuler une authentification réussie
        mock_auth_response = mock.MagicMock()
        mock_auth_response.status_code = 200
        mock_auth_response.headers = {'X-CSRF-Token': 'new-csrf-token'}
        mock_auth_response.text = json.dumps({'meta': {'rc': 'ok'}})
        
        mock_session_instance.post.return_value = mock_auth_response
        mock_session_instance.cookies.items.return_value = [('cookie2', 'value2')]
        
        # Remplacer la méthode _authenticate par un mock
        original_authenticate = self.test_controller._authenticate
        self.test_controller._authenticate = mock.MagicMock(return_value=True)
        
        try:
            # Appeler la méthode _make_request
            success, data, status_code = self.test_controller._make_request('GET', 'devices', 'default')
            
            # Vérifier que la méthode _authenticate a été appelée
            self.test_controller._authenticate.assert_called_once()
            
            # Vérifier que la requête a réussi après réauthentification
            self.assertTrue(success)
            self.assertEqual(status_code, 200)
        finally:
            # Restaurer la méthode _authenticate
            self.test_controller._authenticate = original_authenticate
