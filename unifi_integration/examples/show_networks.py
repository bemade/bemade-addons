"""
Script to display UniFi UDM Pro networks in a clear format
"""
import json
from unifi_client import UnifiClient

def format_network(network):
    """Format network information for better readability"""
    purpose = network.get('purpose', 'corporate')
    if purpose == 'corporate':
        purpose = 'Entreprise'
    elif purpose == 'guest':
        purpose = 'Invité'
    elif purpose == 'vlan-only':
        purpose = 'VLAN uniquement'
        
    dhcp_enabled = network.get('dhcpd_enabled', False)
    dhcp_info = ""
    if dhcp_enabled:
        start = network.get('dhcpd_start', 'N/A')
        stop = network.get('dhcpd_stop', 'N/A')
        dhcp_info = f"({start} - {stop})"
    
    return {
        'nom': network.get('name', 'N/A'),
        'vlan': network.get('vlan', 'Non'),
        'purpose': purpose,
        'subnet': network.get('subnet', 'N/A'),
        'dhcp': 'Activé ' + dhcp_info if dhcp_enabled else 'Désactivé',
        'dns': network.get('dns_nameservers', ['N/A']),
        'enabled': network.get('enabled', True)
    }

def main():
    """Main function to display networks"""
    with UnifiClient() as client:
        print("Récupération des réseaux configurés...")
        
        # Get networks
        networks = client.get_networks()
        if not networks or 'data' not in networks:
            print("Aucun réseau trouvé ou erreur de connexion")
            return
            
        # Display networks
        print("\n=== Réseaux Configurés ===")
        for network in networks['data']:
            net = format_network(network)
            print(f"\n{net['nom']}")
            print(f"  État    : {'Actif' if net['enabled'] else 'Inactif'}")
            print(f"  Type    : {net['purpose']}")
            print(f"  VLAN    : {net['vlan']}")
            print(f"  Subnet  : {net['subnet']}")
            print(f"  DHCP    : {net['dhcp']}")
            print(f"  DNS     : {', '.join(net['dns'])}")

if __name__ == "__main__":
    main()
