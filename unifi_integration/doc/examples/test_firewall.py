"""
Test script for UniFi UDM Pro Firewall Management
This script demonstrates the firewall management capabilities of the UnifiClient class.
"""
import json
from unifi_client import UnifiClient

def format_firewall_rule(rule):
    """Format a firewall rule for display
    
    Args:
        rule (dict): Firewall rule data
        
    Returns:
        dict: Formatted rule data
    """
    return {
        'name': rule.get('name', 'N/A'),
        'ruleset': rule.get('ruleset', 'N/A'),
        'action': rule.get('action', 'N/A'),
        'protocol': rule.get('protocol', 'all'),
        'src_address': rule.get('src_address', 'any'),
        'dst_address': rule.get('dst_address', 'any'),
        'enabled': rule.get('enabled', True)
    }

def main():
    """
    Main test function to demonstrate firewall management
    """
    with UnifiClient() as client:
        print("Connexion à l'UDM Pro...")
        
        # Get existing firewall rules
        print("\nRègles de pare-feu existantes:")
        rules = client.get_firewall_rules()
        if rules and rules.get('data'):
            for rule in rules['data']:
                formatted_rule = format_firewall_rule(rule)
                print(json.dumps(formatted_rule, indent=2))
        
        # Get firewall groups
        print("\nGroupes de pare-feu:")
        groups = client.get_firewall_groups()
        if groups and groups.get('data'):
            for group in groups['data']:
                print(json.dumps({
                    'name': group.get('name', 'N/A'),
                    'type': group.get('group_type', 'N/A'),
                    'members': group.get('group_members', [])
                }, indent=2))
        
        # Example: Create a new firewall rule
        # Note: Commented out to prevent accidental rule creation
        """
        new_rule = {
            'name': 'Test SSH Access',
            'enabled': True,
            'action': 'accept',
            'ruleset': 'WAN_IN',
            'protocol': 'tcp',
            'dst_port': '22',
            'description': 'Allow SSH access from WAN'
        }
        
        print("\nCréation d'une nouvelle règle:")
        result = client.create_firewall_rule(new_rule)
        if result:
            print("Règle créée avec succès:")
            print(json.dumps(format_firewall_rule(result['data'][0]), indent=2))
        """

if __name__ == "__main__":
    main()
