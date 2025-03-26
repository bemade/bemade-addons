# Documentation de l'API Site Manager Ubiquiti

Cette documentation couvre l'API Site Manager de Ubiquiti, qui permet d'interagir avec les appareils UniFi via l'interface unifi.ui.com.

## Table des matières

- [Introduction](#introduction)
- [Authentification](#authentification)
- [Limites de taux](#limites-de-taux)
- [Endpoints](#endpoints)
  - [Liste des hôtes](#liste-des-hôtes)
  - [Obtenir un hôte par ID](#obtenir-un-hôte-par-id)
  - [Liste des sites](#liste-des-sites)
  - [Liste des appareils](#liste-des-appareils)
  - [Obtenir les métriques ISP](#obtenir-les-métriques-isp)
  - [Interroger les métriques ISP](#interroger-les-métriques-isp)
  - [Liste des configurations SD-WAN](#liste-des-configurations-sd-wan)
  - [Obtenir une configuration SD-WAN par ID](#obtenir-une-configuration-sd-wan-par-id)
  - [Obtenir le statut d'une configuration SD-WAN](#obtenir-le-statut-dune-configuration-sd-wan)

## Introduction

L'API Site Manager de Ubiquiti permet aux développeurs d'accéder et de gérer les appareils UniFi via l'interface unifi.ui.com. Cette API est actuellement en version Early Access (EA) et nécessite une inscription au programme EA.

## Authentification

L'authentification à l'API se fait via une clé API, qui est un identifiant unique utilisé pour authentifier les requêtes API. Ces clés sont essentielles pour garantir un accès sécurisé à votre compte UniFi et aux appareils associés. Chaque clé est liée au compte UI qui l'a créée, permettant des interactions API sécurisées et personnalisées.

### Obtention d'une clé API

1. Connectez-vous au gestionnaire de site UniFi à l'adresse [unifi.ui.com](https://unifi.ui.com/api).
2. Dans la barre de navigation de gauche, cliquez sur API.
3. Cliquez sur "Create API Key".
4. Copiez la clé et conservez-la en lieu sûr, car elle ne sera affichée qu'une seule fois.
5. Cliquez sur "Done" pour vous assurer que la clé est hachée et stockée en toute sécurité.

### Utilisation de la clé API

Incorporez la clé API dans l'en-tête X-API-Key. Suivez l'exemple ci-dessous, en remplaçant YOUR_API_KEY par votre clé API réelle.

```bash
curl -X GET 'https://api.ui.com/ea/hosts' \
 -H 'X-API-KEY: YOUR_API_KEY' \
 -H 'Accept: application/json'
```

## Limites de taux

La limite de taux de l'API est fixée à 100 requêtes par minute. Si vous dépassez cette limite, le serveur répondra avec un code d'état 429 Too Many Requests.

## Champs optionnels pendant l'EA

Dans la version Early Access de l'API, tous les champs dans `response.data` sont considérés comme optionnels. Cette conception flexible nous permet d'itérer et d'améliorer notre API au fil du temps. Nous vous encourageons à construire vos intégrations en tenant compte de cette optionalité.

## Endpoints

### Liste des hôtes

Récupère une liste de tous les hôtes associés au compte UI effectuant l'appel API.

**Endpoint**: `GET https://api.ui.com/ea/hosts`

**Paramètres de requête**:
- `pageSize` (optionnel): Nombre d'éléments à retourner par page
- `nextToken` (optionnel): Token pour la pagination

**Exemple de requête**:
```bash
curl -X GET 'https://api.ui.com/ea/hosts?pageSize=10&nextToken=602232A870250000000006C514FF00000000073DD8DB000000006369FDA2:1467082514' \
  -H 'Accept: application/json' \
  -H 'X-API-KEY: YOUR_API_KEY'
```

**Exemple de réponse**:
```json
{
  "data": [
    {
      "hardwareId": "eae0f123-0000-5111-b111-f833f56eade5",
      "id": "900A6F00301100000000074A6BA90000000007A3387E0000000063EC9853:123456789",
      "ipAddress": "192.168.220.114",
      "isBlocked": false,
      "lastConnectionStateChange": "2024-06-23T03:59:52Z",
      "latestBackupTime": "2024-06-22T11:55:10Z",
      "owner": true,
      "registrationTime": "2024-04-17T07:27:14Z",
      "reportedState": {
        // Structure détaillée de l'état rapporté
      },
      "type": "console",
      "userData": {
        // Structure détaillée des données utilisateur
      }
    }
  ],
  "httpStatusCode": 200,
  "traceId": "a7dc15e0eb4527142d7823515b15f87d",
  "nextToken": "ba8e384e-3308-4236-b344-7357657351ca"
}
```

**Note**: La structure de `userData` et `reportedState` peut varier en fonction de la version de UniFi OS ou Network Server. L'exemple fourni est basé sur UniFi OS 4.0.6.

### Obtenir un hôte par ID

Récupère des informations détaillées sur un hôte spécifique par ID.

**Endpoint**: `GET https://api.ui.com/ea/hosts/{hostId}`

**Paramètres de chemin**:
- `hostId` (obligatoire): ID de l'hôte à récupérer

**Exemple de requête**:
```bash
curl -X GET 'https://api.ui.com/ea/hosts/900A6F00301100000000074A6BA90000000007A3387E0000000063EC9853:123456789' \
  -H 'Accept: application/json' \
  -H 'X-API-KEY: YOUR_API_KEY'
```

**Note**: La structure de `userData` et `reportedState` peut varier en fonction de la version de UniFi OS ou Network Server. L'exemple fourni est basé sur UniFi OS 4.0.6.

### Liste des sites

Récupère une liste de tous les sites associés au compte UI effectuant l'appel API.

**Endpoint**: `GET https://api.ui.com/ea/sites`

**Paramètres de requête**:
- `pageSize` (optionnel): Nombre d'éléments à retourner par page
- `nextToken` (optionnel): Token pour la pagination

**Exemple de requête**:
```bash
curl -X GET 'https://api.ui.com/ea/sites?pageSize=10&nextToken=602232A870250000000006C514FF00000000073DD8DB000000006369FDA2:1467082514' \
  -H 'Accept: application/json' \
  -H 'X-API-KEY: YOUR_API_KEY'
```

**Exemple de réponse**:
```json
{
  "data": [
    {
      "hostId": "900A6F00301100000000074A6BA90000000007A3387E0000000063EC9853:123456789",
      "isOwner": true,
      "meta": {
        "desc": "Default",
        "gatewayMac": "f4:e2:c6:c2:3f:13",
        "name": "default",
        "timezone": "Europe/Riga"
      },
      "permission": "admin",
      "siteId": "661900ae6aec8f548d49fd54",
      "statistics": {
        // Structure détaillée des statistiques
      }
    }
  ],
  "httpStatusCode": 200,
  "traceId": "a7dc15e0eb4527142d7823515b15f87d",
  "nextToken": "ba8e384e-3308-4236-b344-7357657351ca"
}
```

**Note**: La structure de `meta` et `statistics` peut varier en fonction de la version de UniFi OS ou Network Server. L'exemple fourni est basé sur UniFi OS 4.0.6.

### Liste des appareils

Récupère une liste des appareils UniFi gérés par les hôtes où le compte UI effectuant l'appel API est le propriétaire ou un super administrateur.

**Endpoint**: `GET https://api.ui.com/ea/devices`

**Paramètres de requête**:
- `pageSize` (optionnel): Nombre d'éléments à retourner par page
- `nextToken` (optionnel): Token pour la pagination

**Note**: La structure de `devices.uidb` peut varier en fonction de la version de UniFi OS ou Network Server. L'exemple fourni est basé sur UniFi OS 4.0.6.

### Obtenir les métriques ISP

Récupère les données de métriques ISP pour tous les sites liés à la clé API du compte UI. Les métriques de 5 minutes sont disponibles pendant au moins 24 heures, et les métriques d'une heure pendant au moins 30 jours.

**Endpoint**: `GET https://api.ui.com/ea/isp-metrics`

### Interroger les métriques ISP

Récupère les données de métriques ISP en fonction de paramètres de requête spécifiques. Les métriques de 5 minutes sont disponibles pendant au moins 24 heures, et les métriques d'une heure pendant au moins 30 jours.

**Endpoint**: `POST https://api.ui.com/ea/isp-metrics/query`

**Note**: Si le compte UI n'a pas accès à tous les sites demandés, une erreur 502 est renvoyée. Si un accès partiel est accordé, la réponse inclura `status: partialSuccess`.

### Liste des configurations SD-WAN

Récupère une liste de toutes les configurations SD-WAN associées au compte UI effectuant l'appel API.

**Endpoint**: `GET https://api.ui.com/ea/sdwan-configs`

### Obtenir une configuration SD-WAN par ID

Récupère des informations détaillées sur une configuration SD-WAN spécifique par ID.

**Endpoint**: `GET https://api.ui.com/ea/sdwan-configs/{configId}`

**Paramètres de chemin**:
- `configId` (obligatoire): ID de la configuration SD-WAN à récupérer

### Obtenir le statut d'une configuration SD-WAN

Récupère le statut d'une configuration SD-WAN spécifique, y compris la progression du déploiement, les erreurs et les hubs associés.

**Endpoint**: `GET https://api.ui.com/ea/sdwan-configs/{configId}/status`

**Paramètres de chemin**:
- `configId` (obligatoire): ID de la configuration SD-WAN dont le statut doit être récupéré
