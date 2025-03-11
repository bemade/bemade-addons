"""
Script to display UniFi UDM Pro VLANs in a clear format
"""
from unifi_client import UnifiClient

def get_vlan_purpose(network):
    """Get the purpose/usage of a VLAN"""
    purpose = network.get('purpose', 'corporate')
    if purpose == 'corporate':
        return 'Entreprise'
    elif purpose == 'guest':
        return 'Invité'
    elif purpose == 'vlan-only':
        return 'VLAN uniquement'
    return purpose

def main():
    """Main function to display VLANs"""
    with UnifiClient() as client:
        print("Récupération des VLANs configurés...")
        
        # Get networks
        networks = client.get_networks()
        if not networks or 'data' not in networks:
            print("Aucun VLAN trouvé ou erreur de connexion")
            return
            
        # Filter and sort networks with VLANs
        vlan_networks = [n for n in networks['data'] if n.get('vlan', None) is not None]
        vlan_networks.sort(key=lambda x: x.get('vlan', 0))
        
        # Display VLANs
        print("\n=== VLANs Configurés ===")
        print(f"{'VLAN ID':<8} {'Nom':<20} {'Type':<15} {'Plage DHCP':<35} {'État'}")
        print("-" * 85)
        
        for network in vlan_networks:
            vlan_id = network.get('vlan', 'N/A')
            name = network.get('name', 'N/A')
            purpose = get_vlan_purpose(network)
            
            # Format DHCP range
            dhcp_range = 'DHCP désactivé'
            if network.get('dhcpd_enabled', False):
                start = network.get('dhcpd_start', '')
                stop = network.get('dhcpd_stop', '')
                dhcp_range = f"{start} - {stop}"
            
            state = 'Actif' if network.get('enabled', True) else 'Inactif'
            
            print(f"{vlan_id:<8} {name[:20]:<20} {purpose[:15]:<15} {dhcp_range[:35]:<35} {state}")

if __name__ == "__main__":
    main()
