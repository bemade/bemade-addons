"""
Test script for UniFi UDM Pro API Client
This script demonstrates the basic usage of the UnifiClient class.
"""
import json
from unifi_client import UnifiClient

def format_response(data, max_items=5):
    """Format API response data to show only essential information
    
    Args:
        data (dict): API response data
        max_items (int): Maximum number of items to show
        
    Returns:
        dict: Formatted data
    """
    if not data or 'data' not in data:
        return data
        
    result = {'meta': data.get('meta', {}), 'data': []}
    
    # Take only the first max_items
    items = data['data'][:max_items]
    
    for item in items:
        # For devices, show only essential info
        if 'model' in item:
            result['data'].append({
                'name': item.get('name', 'N/A'),
                'model': item.get('model', 'N/A'),
                'ip': item.get('ip', 'N/A'),
                'status': item.get('state', 'N/A')
            })
        # For clients, show only essential info
        elif 'hostname' in item:
            result['data'].append({
                'name': item.get('hostname', 'N/A'),
                'ip': item.get('ip', 'N/A'),
                'mac': item.get('mac', 'N/A'),
                'network': item.get('network', 'N/A')
            })
        # For other types, keep all fields
        else:
            result['data'].append(item)
            
    if len(data['data']) > max_items:
        print(f"\nNote: Showing {max_items} of {len(data['data'])} items")
        
    return result

def main():
    """
    Main test function to demonstrate UnifiClient usage
    """
    # Using context manager for automatic login/logout
    with UnifiClient() as client:
        # Get system information
        system_info = client.get_system_info()
        
        if system_info:
            print("Successfully connected to UDM Pro!")
            print("\nSystem Information:")
            system_info = format_response(system_info)
            print(json.dumps(system_info, indent=2))
            
            # Get network health status
            health = client.get_health()
            if health:
                print("\nNetwork Health:")
                health = format_response(health)
                print(json.dumps(health, indent=2))
            
            # Get connected devices
            devices = client.get_devices()
            if devices:
                print("\nConnected Devices:")
                devices = format_response(devices)
                print(json.dumps(devices, indent=2))
            
            # Get active clients
            clients = client.get_clients()
            if clients:
                print("\nActive Clients:")
                clients = format_response(clients)
                print(json.dumps(clients, indent=2))
        else:
            print("Failed to retrieve system information")

if __name__ == "__main__":
    main()
