# Exemples d'intégration UniFi

Ce document décrit les exemples fournis dans le répertoire `doc/examples` qui illustrent l'utilisation des API UniFi pour l'intégration avec Odoo.

## Structure des exemples

Le répertoire `doc/examples` contient plusieurs fichiers qui démontrent différents aspects de l'intégration avec les API UniFi :

### Documentation

- **api.md** : Documentation détaillée des endpoints de l'API du contrôleur UniFi, incluant les méthodes REST, les commandes disponibles et les codes d'appareil.
- **models.md** : Description des modèles de données proposés pour l'intégration UniFi dans Odoo, incluant les structures de tables et relations.

### Client Python

- **unifi_client.py** : Classe cliente Python pour interagir avec l'API UniFi UDM Pro. Cette classe gère l'authentification et les opérations API de base.

### Scripts d'exemple

Plusieurs scripts Python qui démontrent l'utilisation du client UniFi pour différentes tâches :

- **show_devices.py** : Affiche tous les appareils UniFi gérés par le contrôleur dans un format lisible.
- **show_device_details.py** : Affiche des informations détaillées sur un appareil spécifique.
- **show_clients.py** : Liste tous les clients (appareils connectés) sur le réseau.
- **show_networks.py** : Affiche les configurations réseau définies sur le contrôleur.
- **show_vlans.py** : Liste les VLANs configurés sur le système.
- **show_firewall.py** : Affiche les règles de pare-feu configurées.
- **test_firewall.py** : Démontre comment interagir avec les règles de pare-feu.
- **test_unifi.py** : Script de test général pour vérifier la connexion et les fonctionnalités de base.

### Fichiers de configuration

- **credential.txt** : Fichier de configuration contenant les informations d'authentification pour se connecter au contrôleur UniFi.
- **requirements.txt** : Liste des dépendances Python nécessaires pour exécuter les scripts d'exemple.

## Utilisation des exemples

### Configuration

1. Copiez le fichier `credential.txt` et modifiez-le avec vos propres informations d'authentification :
   ```
   UNIFI_HOST=192.168.1.1
   UNIFI_PORT=443
   UNIFI_USERNAME=votre_utilisateur
   UNIFI_PASSWORD=votre_mot_de_passe
   UNIFI_SITE=default
   ```

2. Installez les dépendances requises :
   ```bash
   pip install -r requirements.txt
   ```

### Exécution des scripts

Pour exécuter un script d'exemple, utilisez la commande Python suivante :

```bash
python show_devices.py
```

## Intégration avec Odoo

Les modèles décrits dans `models.md` fournissent une structure de données proposée pour l'intégration avec Odoo. Ces modèles incluent :

- **udm.site** : Représente un site UniFi géré par un UDM/UDR ou un contrôleur logiciel
- **udm.system_info** : Informations système du contrôleur
- **udm.network** : Configurations réseau
- **udm.vlan** : Configurations VLAN
- **udm.device** : Appareils UniFi (points d'accès, switches, etc.)
- **udm.user** : Utilisateurs/clients sur le réseau
- **udm.firewall_rule** : Règles de pare-feu
- **udm.firewall_group** : Groupes de pare-feu

Ces modèles peuvent être utilisés comme base pour développer le module d'intégration UniFi pour Odoo, en s'appuyant sur les exemples de code fournis pour interagir avec l'API UniFi.

## Adaptation pour l'intégration

Pour adapter ces exemples à une intégration complète avec Odoo, il faudrait :

1. Implémenter les modèles décrits dans `models.md`
2. Adapter la classe `UnifiClient` pour fonctionner dans le contexte d'Odoo
3. Créer un assistant (wizard) pour configurer la connexion, comme décrit dans le fichier `objectifs.md`
4. Implémenter des méthodes de synchronisation périodique des données
5. Développer des vues pour afficher et gérer les données UniFi dans l'interface Odoo
