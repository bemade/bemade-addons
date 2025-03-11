# UniFi Integration for Odoo

Module d'intégration entre Odoo et les appareils UniFi Network (UDM Pro, UCG Max).

## API Integration Notes

### Authentication

The UniFi API requires specific endpoints and headers for authentication. Note that there are critical differences between UniFi controllers and the UDM Pro/UCG Max API:

```python
# Python Example
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}
data = {
    'username': 'your_username',
    'password': 'your_password',
    'rememberMe': True
}

session = requests.Session()
response = session.post(
    'https://udmp:443/api/auth/login',
    headers=headers,
    json=data,
    verify=False
)
```

### API Endpoints

All API endpoints (except authentication) must be prefixed with `/proxy/network`. Common endpoints include:

#### System and Status
- System Health: `/api/system/health`
- System Info: `/proxy/network/api/s/{site}/stat/sysinfo`
- Dashboard Health: `/proxy/network/api/s/{site}/stat/health`

#### Network Configuration
- Networks: `/proxy/network/api/s/{site}/rest/networkconf`
- Firewall Rules: `/proxy/network/api/s/{site}/rest/firewallrule`
- Port Forwards: `/proxy/network/api/s/{site}/stat/portforward`
- Routes: `/proxy/network/api/s/{site}/rest/routing`

#### Devices and Clients
- All Devices: `/proxy/network/api/s/{site}/stat/device`
- Basic Device Info: `/proxy/network/api/s/{site}/stat/device-basic`
- Active Clients: `/proxy/network/api/s/{site}/stat/sta`
- All Clients: `/proxy/network/api/s/{site}/stat/user`

### Headers Required

All API requests must include these headers:

```python
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Odoo UniFi Integration"
}

# Add CSRF token for authenticated requests
if csrf_token:
    headers["X-CSRF-Token"] = csrf_token
```

### SSL Verification

The UDM Pro uses self-signed certificates. SSL verification must be disabled:

```python
# Disable SSL verification warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Skip certificate validation in requests
verify=False
```

## Module Features

### Network Configuration
- Import and manage network settings
- Configure port forwarding rules
- Manage firewall rules and groups
- Handle routing configuration

### Device Management
- Monitor device status and health
- Track active and configured clients
- View detailed device statistics

### System Monitoring
- Dashboard with health metrics
- System performance statistics
- Network usage and throughput

### Multi-Site Support
- Manage multiple UniFi sites
- Site-specific configurations
- Independent metrics per site

## Installation

1. Install the module in your Odoo instance
2. Configure your UDM Pro credentials in the UniFi Integration settings
3. Import your network configuration

## Configuration

### Site Setup
1. Go to UniFi Integration > Sites
2. Create a new site with:
   - Name: Your site name
   - Site ID: Usually "default" unless configured otherwise
   - Description: Optional site description
   - Physical Address: Optional location information

### UDM Pro Configuration
1. Add your UDM Pro configuration:
   - Host: IP address or hostname
   - Port: Usually 443 (HTTPS)
   - Username: Your UDM Pro username
   - Password: Your UDM Pro password
   - MFA Token: If two-factor authentication is enabled

### API Access
1. Create a dedicated API user in UDM Pro
2. Assign minimum required permissions
3. Use secure network access (VPN or internal network)

## Security Considerations

### Authentication
- Use dedicated API credentials
- Enable two-factor authentication when possible
- Regularly rotate passwords

### Network Security
- Restrict API access to specific networks
- Use VPN for remote access
- Configure appropriate firewall rules

### Monitoring
- Monitor API access logs
- Track authentication failures
- Review system alerts and notifications

### Data Protection
- Store credentials securely
- Encrypt sensitive configuration data
- Regular security audits
