# -*- coding: utf-8 -*-

# Import module files
from . import udm_site
from . import udm_config
from . import udm_network
from . import udm_device
from . import udm_user
from . import udm_settings
from . import udm_firewall
from . import udm_port_forward
from . import udm_dns
from . import udm_routing

# Import all models to ensure they are registered with Odoo
from .udm_site import UdmSite
from .udm_config import UdmConfiguration
from .udm_network import UdmNetwork, UdmVlan
from .udm_device import UdmDevice
from .udm_user import UdmUser
from .udm_settings import UdmSettings
from .udm_firewall import UdmFirewallRule
from .udm_port_forward import UdmPortForward
from .udm_dns import UdmDnsConfig
from .udm_routing import UdmRoutingConfig
