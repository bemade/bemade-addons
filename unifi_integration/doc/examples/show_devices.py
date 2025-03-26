"""
Script to display UniFi UDM Pro devices in a clear format
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

def get_device_type(device):
    """Get device type in French"""
    model = device.get('model', '').lower()
    if 'udm' in model:
        return 'Routeur'
    elif 'usw' in model:
        return 'Switch'
    elif 'uap' in model:
        return 'Point d\'accès'
    return 'Autre'

def get_device_status(device):
    """Get device status in French"""
    if device.get('state', 0) == 1:
        return '✓ En ligne'
    return '✗ Hors ligne'

def format_device(device):
    """Format device information"""
    return {
        'name': device.get('name', 'N/A'),
        'model': device.get('model', 'N/A'),
        'type': get_device_type(device),
        'ip': device.get('ip', 'N/A'),
        'mac': device.get('mac', 'N/A'),
        'version': device.get('version', 'N/A'),
        'status': get_device_status(device),
        'uptime': format_uptime(device.get('uptime', 0))
    }

def main():
    """Main function to display devices"""
    with UnifiClient() as client:
        print("Récupération des appareils UniFi...")
        
        # Get devices
        devices = client.get_devices()
        if not devices or 'data' not in devices:
            print("Aucun appareil trouvé ou erreur de connexion")
            return
            
        # Group devices by type
        devices_by_type = {}
        for device in devices['data']:
            device_type = get_device_type(device)
            if device_type not in devices_by_type:
                devices_by_type[device_type] = []
            devices_by_type[device_type].append(device)
            
        # Display devices by type
        for device_type, device_list in devices_by_type.items():
            print(f"\n=== {device_type}s ===")
            print(f"{'Nom':<20} {'Modèle':<15} {'IP':<15} {'Version':<10} {'État':<15} {'Uptime'}")
            print("-" * 90)
            
            for device in sorted(device_list, key=lambda x: x.get('name', '')):
                d = format_device(device)
                print(f"{d['name'][:20]:<20} {d['model'][:15]:<15} {d['ip']:<15} "
                      f"{d['version'][:10]:<10} {d['status']:<15} {d['uptime']}")
        
        print(f"\nTotal: {len(devices['data'])} appareils UniFi")

if __name__ == "__main__":
    main()
