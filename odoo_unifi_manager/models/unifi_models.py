"""Data models for UniFi Controller API responses."""
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime

@dataclass
class NetworkConfig:
    """Network configuration data model."""
    _id: str
    name: str
    purpose: str
    subnet: str
    vlan_enabled: bool
    vlan_id: Optional[int] = None
    dhcp_enabled: bool = True
    dhcp_start: Optional[str] = None
    dhcp_stop: Optional[str] = None

@dataclass
class WifiConfig:
    """WiFi configuration data model."""
    _id: str
    name: str
    security: str
    wpa_mode: str
    wpa_enc: str
    enabled: bool
    is_guest: bool = False
    hide_ssid: bool = False
    vlan_enabled: bool = False
    vlan_id: Optional[int] = None

@dataclass
class ClientDevice:
    """Connected client device data model."""
    _id: str
    mac: str
    hostname: Optional[str]
    ip: Optional[str]
    network_id: str
    last_seen: datetime
    is_guest: bool = False
    blocked: bool = False
    data_usage: Optional[Dict] = None

@dataclass
class SystemHealth:
    """System health statistics data model."""
    subsystem: str
    status: str
    num_user: int
    num_guest: int
    lan_throughput: float
    wlan_throughput: float
    wan_throughput: float
    cpu_usage: float
    mem_usage: float
    
@dataclass
class FirewallRule:
    """Firewall rule data model."""
    _id: str
    name: str
    enabled: bool
    action: str
    protocol: str
    src_address: Optional[str] = None
    dst_address: Optional[str] = None
    src_port: Optional[str] = None
    dst_port: Optional[str] = None
    ruleset: str = "LAN_IN"
    rule_index: int = 2000
