# Odoo Proxmox Manager

This module allows you to manage your Proxmox servers and virtual machines directly from Odoo 17.0.

## Features

- Manage multiple Proxmox servers and clusters
- Monitor server status and resources
- View and manage virtual machines
- Start, stop, restart, suspend, and resume VMs
- Group servers into clusters for better organization
- Multi-company support
- Role-based access control

## Installation

### Prerequisites

1. Odoo 17.0
2. Python package requirements:
   ```
   proxmoxer
   requests
   ```

### Steps

1. Clone this repository into your Odoo addons directory
2. Install the required Python packages:
   ```bash
   pip install proxmoxer requests
   ```
3. Update your Odoo addons list
4. Install the module through Odoo's Apps menu

## Configuration

1. Create an API Token in your Proxmox server:
   - Log in to your Proxmox web interface
   - Go to Datacenter -> Permissions -> API Tokens
   - Create a new token and note down the Token ID and Secret

2. In Odoo:
   - Go to the Proxmox menu
   - Create a new cluster (optional)
   - Create a new server:
     - Enter the server hostname
     - Enter your API token information
     - Test the connection

## Usage

### Managing Servers

1. Navigate to Proxmox -> Servers
2. Create or select a server
3. Click "Sync VMs" to synchronize virtual machines
4. View server status and resource information

### Managing Virtual Machines

1. Navigate to Proxmox -> Virtual Machines
2. View all VMs across your servers
3. Use the action buttons to:
   - Start VMs
   - Stop VMs
   - Restart VMs
   - Suspend VMs
   - Resume VMs

### Managing Clusters

1. Navigate to Proxmox -> Clusters
2. Create a new cluster
3. Add servers to the cluster
4. Use "Sync All Servers" to update all servers in the cluster

## Security

The module includes two user groups:
- Proxmox User: Can view servers and VMs
- Proxmox Manager: Can manage servers and VMs

## Support

For bugs or feature requests, please create an issue in the repository.

## License

LGPL-3
