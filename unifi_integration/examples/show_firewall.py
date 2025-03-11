"""
Script to display UniFi UDM Pro firewall rules in a clear format
"""
import json
from unifi_client import UnifiClient

def format_rule(rule):
    """Format a firewall rule for better readability"""
    direction = "IN" if rule.get('ruleset', '').endswith('_IN') else "OUT"
    src = rule.get('src_address', 'any')
    dst = rule.get('dst_address', 'any')
    
    if direction == "IN":
        from_to = f"FROM {src} TO {dst if dst != '' else 'any'}"
    else:
        from_to = f"FROM {src if src != '' else 'any'} TO {dst}"
    
    return {
        'name': rule.get('name', 'N/A'),
        'action': rule.get('action', 'N/A').upper(),
        'direction': direction,
        'protocol': rule.get('protocol', 'all').upper(),
        'ports': f"{rule.get('src_port', 'any')} -> {rule.get('dst_port', 'any')}",
        'addresses': from_to,
        'enabled': '✓' if rule.get('enabled', True) else '✗'
    }

def print_rules_by_type(rules, ruleset_type):
    """Print rules filtered by ruleset type"""
    filtered_rules = [r for r in rules if ruleset_type in r.get('ruleset', '')]
    if filtered_rules:
        print(f"\n=== Règles {ruleset_type} ===")
        for rule in filtered_rules:
            r = format_rule(rule)
            print(f"\n{r['name']}")
            print(f"  État     : {r['enabled']}")
            print(f"  Action   : {r['action']}")
            print(f"  Protocol : {r['protocol']}")
            print(f"  Ports    : {r['ports']}")
            print(f"  Adresses : {r['addresses']}")

def main():
    """Main function to display firewall rules"""
    with UnifiClient() as client:
        print("Récupération des règles de pare-feu...")
        
        # Get firewall rules
        rules = client.get_firewall_rules()
        if not rules or 'data' not in rules:
            print("Aucune règle trouvée ou erreur de connexion")
            return
            
        # Display rules by type
        print_rules_by_type(rules['data'], 'WAN_IN')
        print_rules_by_type(rules['data'], 'WAN_OUT')
        print_rules_by_type(rules['data'], 'LAN_IN')
        print_rules_by_type(rules['data'], 'LAN_OUT')
        
        # Get and display firewall groups
        groups = client.get_firewall_groups()
        if groups and 'data' in groups:
            print("\n=== Groupes de Pare-feu ===")
            for group in groups['data']:
                print(f"\n{group.get('name', 'N/A')} ({group.get('group_type', 'N/A')})")
                print(f"  Membres : {', '.join(group.get('group_members', []))}")

if __name__ == "__main__":
    main()
