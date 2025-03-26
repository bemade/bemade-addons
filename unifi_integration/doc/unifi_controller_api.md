# Documentation de l'API du Contrôleur UniFi

Cette documentation couvre l'API du contrôleur UniFi, qui permet d'interagir directement avec les contrôleurs UniFi Network.

## Table des matières

- [Introduction](#introduction)
- [Différences entre les contrôleurs UniFi et UDM Pro/UCG Max](#différences-entre-les-contrôleurs-unifi-et-udm-proucg-max)
- [Authentification](#authentification)
- [Endpoints du contrôleur](#endpoints-du-contrôleur)
- [Endpoints spécifiques aux sites](#endpoints-spécifiques-aux-sites)
  - [Commandes exécutables](#commandes-exécutables)
  - [Tables de données](#tables-de-données)
  - [Liste des endpoints](#liste-des-endpoints)
- [Mise à jour des règles de redirection de port](#mise-à-jour-des-règles-de-redirection-de-port)

## Introduction

L'API du contrôleur UniFi permet aux développeurs d'accéder et de gérer les contrôleurs UniFi Network. Cette API REST offre un accès programmatique aux fonctionnalités du contrôleur UniFi.

## Différences entre les contrôleurs UniFi et UDM Pro/UCG Max

Il existe deux différences critiques entre les contrôleurs UniFi standard et l'API des UDM Pro et UCG Max :

1. L'endpoint de connexion est `/api/auth/login` (au lieu de `/api/login`)
2. Tous les endpoints API doivent être préfixés avec `/proxy/network` (par exemple, `https://192.168.0.1/proxy/network/api/s/default/self`)

## Authentification

### Pour les contrôleurs UniFi standard

L'authentification se fait via l'endpoint `/api/login` avec les informations d'identification.

### Pour UDM Pro et UCG Max

L'authentification se fait via l'endpoint `/api/auth/login` avec les informations d'identification.

#### Exemples d'authentification pour UDM Pro/UCG Max

**Avec curl**:
```bash
# Authentification et sauvegarde du contenu du cookie dans le fichier local cookie.txt avec l'option '-c'
curl -k -X POST --data '{"username": "usr", "password": "$pw"}' --header 'Content-Type: application/json' -c cookie.txt https://udmp:443/api/auth/login
# Répond avec des données JSON

# Utilisation du fichier local cookie.txt avec l'option '-b'
curl -k -X GET -b cookie.txt https://udmp/proxy/network/api/s/default/self
# Répond avec du JSON approprié
```

**Avec Python**:
```python
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
headers = {"Accept": "application/json","Content-Type": "application/json"}
data = {'username': 'usr', 'password': 'pw'}
s = requests.Session()
r = s.post('https://udmp:443/api/auth/login', headers = headers, json = data, verify = False, timeout = 1)
print(r.status_code)
print(s.get('https://udmp/proxy/network/api/s/default/self', headers = headers, verify = False, timeout = 1).text)
```

## Endpoints du contrôleur

Ces appels REST peuvent être effectués sans contexte de site. Il ne semble pas que des mises à jour (PUT) puissent être appelées sur ces endpoints.

Exemple de réponse :
```json
{
  "data": [],
  "meta": {
    "rc": "ok",
    "server_version": "5.7.23",
    "up": true,
    "uuid": "0e727580-ffff-ffff-ffff-403dcd5a7bd4"
  }
}
```

## Endpoints spécifiques aux sites

Tous les endpoints sont présumés être préfixés avec `api/s/{site}` où `{site}` est l'identifiant du site.

### Commandes exécutables

En envoyant une requête POST à l'endpoint `api/s/{site}/cmd/<manager>` avec le JSON `{"cmd": "command"}`, vous pouvez invoquer des commandes sur le contrôleur.

### Tables de données

Ces données ont été extraites du JavaScript du site. Il y a 2 213 applications nommées dans le fichier JavaScript dynamic.dpi.js.

L'ID d'application est un ID composé utilisant un décalage binaire à gauche sur l'ID de catégorie + l'ID d'application envoyé depuis l'API en utilisant `list_dpi_stats_filtered`.

```php
function compoundId($cat, $app){
  return (intval($cat) << 16) + intval($app);
}
```

### Liste des endpoints

Voici une liste des endpoints disponibles dans l'API du contrôleur UniFi :

```
# Utilisateur connecté
api/s/{site}/self

# Codes de pays
api/s/{site}/stat/ccode
# Canaux WiFi disponibles
api/s/{site}/stat/current-channel

# Santé du tableau de bord
api/s/{site}/stat/health

# Appareils clients actifs
api/s/{site}/stat/sta
# Clients configurés
api/s/{site}/stat/user

# Appareils
api/s/{site}/stat/device-basic - mac, type
api/s/{site}/stat/device - peut être filtré avec macs: [ ..., ... ]

# Paramètres détaillés du site
api/s/{site}/stat/sysinfo

# Les endpoints /rest/ ont également un /cnt/ qui renvoie le nombre pour la partie données
# peut être utilisé pour n'importe lequel mais semble ciblé vers les alarmes

# Paramètres du site
api/s/{site}/rest/setting - c'est un gros endpoint avec un mécanisme étrange pour la mise à jour

# Règles de pare-feu
api/s/{site}/rest/firewallrule - liste uniquement les règles définies par l'utilisateur

# Groupes de pare-feu
api/s/{site}/rest/firewallgroup

# Routes
api/s/{site}/rest/routing

# Alarmes
# Liste des alarmes
api/s/{site}/rest/alarm
# Liste des alarmes non archivées
api/s/{site}/rest/alarm?archived=false

# Groupes d'utilisateurs - paramètres de bande passante
api/s/{site}/rest/usergroup

# ?
api/s/{site}/rest/wlangroup

# Réseaux sans fil
api/s/{site}/rest/wlanconf

# ?
api/s/{site}/rest/tag

# Réseaux du site
api/s/{site}/rest/networkconf

# Exemple de chemin de sauvegarde
dl/autobackup/autobackup_5.7.23_20180513_0000_1526169600008.unf

# Insights - sessions
api/s/{site}/stat/session?type=all&start=1526515200&end=1526688000

# Insights - flux EDU
api/s/{site}/stat/stream

# Configuration des ports de commutateur ?
api/s/{site}/rest/portconf

# Redirections de port configurées et uPNP - les octets de transfert sont listés mais ne semblent pas être remplis
api/s/{site}/stat/portforward

# Mise à jour de l'utilisateur (les utilisateurs sont les clients)  
api/s/{site}/upd/user/{UserId}
Vous pouvez obtenir les utilisateurs et l'ID utilisateur à partir de "/api/s/{SiteId}/stat/alluser" (Tous les clients) ou "/api/s/{SiteId}/stat/sta" (Clients actifs) qui contient l'ID client (_id).
Exemple : changer le nom de l'utilisateur avec l'ID client 5aca464bb79fc60200460394 en 'test-raw' :
${curl_cmd} --data "json={'name':'test-raw'}" $baseurl/api/s/$site/upd/user/5aca464bb79fc60200460394

# Obtenir la configuration du Hotspot
guest/s/{site}/hotspotconfig
Vous obtiendrez dans "auth" la valeur "none" si elle n'est pas activée, si elle est activée, vous obtiendrez par exemple "hotspot" et de nombreuses autres valeurs sur la conception de la page.

# Obtenir les packages Hotspot
guest/s/{site}/hotspotpackages
??

# Obtenir les règles de trafic
v2/api/site/{site}/trafficrules
Possibilité également d'ajouter une nouvelle règle avec une requête POST.

# Modifier les règles de trafic
v2/api/site/{site}/trafficrules/{id}/
Requête PUT ou DELETE pour mettre à jour ou supprimer une règle de trafic
GET n'est pas autorisé sur des règles de trafic spécifiques.
Avec PUT, le code de résultat est 201 et non 200 pour un changement réussi.

# Liste possible de tous les gestionnaires appelables
system
devmgr
stamgr
evtmgr
cfgmgr
hotspot
sitemgr
streammgr
backup
throughput
stat
firmware
firewall
elite
```

## Mise à jour des règles de redirection de port

Cela peut s'appliquer à d'autres configurations, mais les tests initiaux montrent que les règles de redirection de port peuvent être activées/désactivées en utilisant PUT contre l'endpoint `/api/s/{site}/rest/portforward/{rule-id}` avec un corps tel que :

```json
{
    "enabled": true
}
```

L'ID de règle peut être récupéré en utilisant la requête GET de redirection de port décrite ci-dessus et se trouve dans la clé "_id".

De nouvelles règles peuvent être créées en utilisant POST, mais sachez qu'il semble y avoir très peu de validation (il est possible de créer des entrées sans autre information que le fait qu'elles soient activées, par exemple).
