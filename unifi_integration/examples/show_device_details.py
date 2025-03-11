"""
Script to display detailed information about a UniFi device
"""
from datetime import datetime
from unifi_client import UnifiClient

def format_bytes(bytes_value):
    """Format bytes in human readable format"""
    if not bytes_value:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"

def format_temperature(temp_celsius):
    """Format temperature in Celsius"""
    if not temp_celsius:
        return "N/A"
    return f"{temp_celsius}°C"

def format_radio_stats(radio):
    """Format radio statistics"""
    channel = radio.get('channel', 'N/A')
    width = radio.get('channel_width', 'N/A')
    tx_power = radio.get('tx_power', 'N/A')
    tx_power_str = f"{tx_power}dBm" if tx_power != 'N/A' else 'N/A'
    utilization = radio.get('utilization', 'N/A')
    util_str = f"{utilization}%" if utilization != 'N/A' else 'N/A'
    
    return f"Canal {channel} ({width}MHz), Puissance: {tx_power_str}, Utilisation: {util_str}"

def format_client_info(client):
    """Format client information"""
    name = client.get('name', client.get('hostname', 'Inconnu'))
    ip = client.get('ip', 'N/A')
    signal = client.get('signal', 0)
    uptime = client.get('uptime', 0)
    uptime_str = f"{uptime//3600}h {(uptime%3600)//60}m" if uptime else 'N/A'
    tx_rate = client.get('tx_rate', 0)
    rx_rate = client.get('rx_rate', 0)
    
    return f"{name:<20} IP: {ip:<15} Signal: {signal}dBm, Up: {uptime_str}, Vitesse: ↓{rx_rate}Mbps ↑{tx_rate}Mbps"

def format_port_status(port):
    """Format port status information"""
    if not port:
        return "N/A"
        
    speed = port.get('speed', 0)
    if speed == 0:
        return "Déconnecté"
    return f"{speed}Mbps {'(PoE)' if port.get('poe_enable', False) else ''}"

def show_device_details(device):
    """Display detailed information about a device"""
    print(f"\n=== Détails de l'appareil : {device.get('name', 'N/A')} ===")
    
    # Informations de base
    print("\nInformations de base:")
    print(f"  Modèle      : {device.get('model', 'N/A')}")
    print(f"  Version     : {device.get('version', 'N/A')}")
    print(f"  IP          : {device.get('ip', 'N/A')}")
    print(f"  MAC         : {device.get('mac', 'N/A')}")
    print(f"  État        : {'En ligne' if device.get('state', 0) == 1 else 'Hors ligne'}")
    
    # Statistiques système
    print("\nStatistiques système:")
    print(f"  CPU         : {device.get('system_stats', {}).get('cpu', 'N/A')}%")
    print(f"  Mémoire     : {device.get('system_stats', {}).get('mem', 'N/A')}%")
    print(f"  Température : {format_temperature(device.get('general_temperature', 0))}")
    
    # Statistiques réseau
    stats = device.get('stat', {})
    print("\nStatistiques réseau:")
    print(f"  Bytes reçus    : {format_bytes(stats.get('rx_bytes', 0))}")
    print(f"  Bytes envoyés  : {format_bytes(stats.get('tx_bytes', 0))}")
    print(f"  Paquets reçus  : {stats.get('rx_packets', 0)}")
    print(f"  Paquets envoyés: {stats.get('tx_packets', 0)}")
    
    # Information sur les ports (pour les switches)
    if 'port_table' in device:
        print("\nPorts:")
        for port in device['port_table']:
            port_name = port.get('name', f"Port {port.get('port_idx', 'N/A')}")
            status = format_port_status(port)
            print(f"  {port_name:<12} : {status}")
    
    # Information WiFi (pour les points d'accès)
    if device.get('radio_table'):
        print("\nRadios WiFi:")
        for radio in device['radio_table']:
            band = "5 GHz" if radio.get('radio', '') == 'na' else "2.4 GHz"
            channel = radio.get('channel', 'N/A')
            tx_power = radio.get('tx_power', 'N/A')
            print(f"  {band:<12} : Canal {channel}, Puissance {tx_power}dBm")

def format_poe_status(port):
    """Format PoE status information"""
    if not port or not port.get('poe_enable'):
        return ''
        
    try:
        power = float(port.get('poe_power', 0))
        voltage = float(port.get('poe_voltage', 0))
        current = float(port.get('poe_current', 0))
        
        if power > 0:
            return f"PoE: {power:.1f}W ({voltage:.1f}V, {current:.0f}mA)"
    except (ValueError, TypeError):
        pass
        
    return 'PoE activé'

def main():
    """Main function to display device details"""
    with UnifiClient() as client:
        print("Récupération des appareils UniFi...")
        
        # Get devices
        devices = client.get_devices()
        if not devices or 'data' not in devices:
            print("Aucun appareil trouvé ou erreur de connexion")
            return
            
        # Find all APs
        aps = [device for device in devices['data'] if device.get('model') in ['U7PG2', 'U7LR', 'U7IW']]
        
        if aps:
            for i, ap in enumerate(aps, 1):
                if i > 1:
                    print("\n" + "=" * 80 + "\n")
                    
                # Show basic details
                show_device_details(ap)
            
            # Show WiFi details
            if 'radio_table' in ap:
                print("\nRadios WiFi:")
                for radio in ap['radio_table']:
                    band = "5 GHz" if radio.get('radio') == 'na' else "2.4 GHz"
                    print(f"  {band}: {format_radio_stats(radio)}")
                    
            # Show connected clients
            if 'vap_table' in ap:
                print("\nClients connectés:")
                for vap in ap['vap_table']:
                    if vap.get('sta_count', 0) > 0:
                        ssid = vap.get('essid', 'N/A')
                        print(f"\nSSID: {ssid}")
                        print("  Nom                  IP               Signal    Temps    Vitesse")
                        print("  " + "-" * 75)
                        
                        for client in vap.get('sta_table', []):
                            print(f"  {format_client_info(client)}")
            
        else:
            print("Aucun point d'accès trouvé")

if __name__ == "__main__":
    main()
