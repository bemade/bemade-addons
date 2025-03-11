"""
Script to display UniFi UDM Pro clients in a clear format
"""
from datetime import datetime
from unifi_client import UnifiClient

def format_uptime(uptime_seconds):
    """Format uptime in a readable format"""
    if not uptime_seconds:
        return "N/A"
    
    days = uptime_seconds // (24 * 3600)
    hours = (uptime_seconds % (24 * 3600)) // 3600
    minutes = (uptime_seconds % 3600) // 60
    
    if days > 0:
        return f"{days}j {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def format_bytes(bytes_value):
    """Format bytes in human readable format"""
    if not bytes_value:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"

def get_client_type(client):
    """Determine client type based on various fields"""
    if client.get('is_wired', False):
        return 'Filaire'
    elif client.get('is_wireless', False):
        return 'WiFi'
    return 'Inconnu'

def main():
    """Main function to display clients"""
    with UnifiClient() as client:
        print("Récupération des clients connectés...")
        
        # Get clients
        clients = client.get_clients()
        if not clients or 'data' not in clients:
            print("Aucun client trouvé ou erreur de connexion")
            return
            
        # Get networks for VLAN mapping
        networks = client.get_networks()
        vlan_names = {
            str(net.get('vlan', '')): net.get('name', 'N/A') 
            for net in networks.get('data', []) 
            if net.get('vlan') is not None
        }
        
        # Group clients by connection type
        wired_clients = []
        wireless_clients = []
        
        for c in clients['data']:
            if c.get('is_wired', False):
                wired_clients.append(c)
            elif c.get('is_wireless', False):
                wireless_clients.append(c)
        
        # Display clients
        def print_client_list(client_list, title):
            if not client_list:
                return
                
            print(f"\n=== Clients {title} ===")
            print(f"{'Nom':<25} {'IP':<15} {'MAC':<18} {'VLAN':<15} {'Uptime':<15} {'Trafic TX/RX'}")
            print("-" * 100)
            
            for c in sorted(client_list, key=lambda x: x.get('name', '')):
                name = c.get('name', c.get('hostname', 'N/A'))
                ip = c.get('ip', 'N/A')
                mac = c.get('mac', 'N/A')
                vlan_id = str(c.get('vlan', ''))
                vlan = f"{vlan_id} ({vlan_names.get(vlan_id, 'N/A')})"
                uptime = format_uptime(c.get('uptime', 0))
                tx = format_bytes(c.get('tx_bytes', 0))
                rx = format_bytes(c.get('rx_bytes', 0))
                
                print(f"{name[:25]:<25} {ip:<15} {mac:<18} {vlan[:15]:<15} {uptime:<15} {tx}/{rx}")
        
        print_client_list(wired_clients, "Filaires")
        print_client_list(wireless_clients, "WiFi")
        
        print(f"\nTotal: {len(wired_clients)} clients filaires, {len(wireless_clients)} clients WiFi")

if __name__ == "__main__":
    main()
