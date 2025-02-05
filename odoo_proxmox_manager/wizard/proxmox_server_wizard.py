from odoo import api, fields, models
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ProxmoxServerWizard(models.TransientModel):
    _name = 'proxmox.server.wizard'
    _description = 'Assistant de configuration serveur Proxmox'

    name = fields.Char(string='Nom', required=True)
    hostname = fields.Char(string='Nom d\'hôte/IP', required=True)
    port = fields.Integer(string='Port', default=443)
    username = fields.Char(string='Nom d\'utilisateur', required=True)
    password = fields.Char(string='Mot de passe', required=True)
    verify_ssl = fields.Boolean(string='Vérifier SSL', default=False)

    def _get_proxmox_connection(self):
        """Établit une connexion à l'API Proxmox"""
        base_url = f"https://{self.hostname}:{self.port}/api2/json"
        try:
            auth_response = requests.post(
                f"{base_url}/access/ticket",
                verify=self.verify_ssl,
                data={
                    "username": self.username,
                    "password": self.password
                }
            )
            auth_response.raise_for_status()
            auth_data = auth_response.json()['data']
            
            headers = {
                'CSRFPreventionToken': auth_data['CSRFPreventionToken'],
                'Cookie': f"PVEAuthCookie={auth_data['ticket']}"
            }
            return base_url, headers
        except Exception as e:
            raise ValueError(f"Erreur de connexion: {str(e)}")

    def action_test_connection(self):
        """Teste la connexion et crée le serveur et le cluster si la connexion réussit"""
        try:
            base_url, headers = self._get_proxmox_connection()
            
            # Vérifier si c'est un cluster
            cluster_response = requests.get(
                f"{base_url}/cluster/status",
                headers=headers,
                verify=self.verify_ssl
            )
            cluster_response.raise_for_status()
            cluster_data = cluster_response.json()['data']
            
            is_cluster = any(node['type'] == 'cluster' for node in cluster_data)
            cluster = False
            
            if is_cluster:
                cluster_name = next((node['name'] for node in cluster_data if node['type'] == 'cluster'), 'Cluster Proxmox')
                cluster = self.env['proxmox.cluster'].create({
                    'name': cluster_name,
                })

            # Créer le serveur principal
            main_server = self.env['proxmox.server'].create({
                'name': self.name,
                'hostname': self.hostname,
                'port': self.port,
                'username': self.username,
                'password': self.password,
                'cluster_id': cluster.id if cluster else False,
            })

            # Créer les autres nœuds si c'est un cluster
            if is_cluster:
                nodes = [node for node in cluster_data if node['type'] == 'node' and node['name'] != self.hostname]
                for node in nodes:
                    self.env['proxmox.server'].create({
                        'name': node['name'],
                        'hostname': node['name'],
                        'port': self.port,
                        'username': self.username,
                        'password': self.password,
                        'cluster_id': cluster.id,
                    })

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'proxmox.server',
                'res_id': main_server.id,
                'view_mode': 'form',
                'view_type': 'form',
                'views': [(False, 'form')],
                'target': 'current',
                'flags': {'mode': 'readonly'},
            }
            
        except Exception as e:
            raise ValueError(f"Erreur lors du test de connexion: {str(e)}")
