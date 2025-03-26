# Relations entre les modèles du module d'intégration UniFi

Ce document présente visuellement les relations entre les différents modèles du module d'intégration UniFi.

## Diagramme de relations principal

```
+-------------------+
|                   |
|     udm.site      |<-------------------+
|                   |                    |
+--------+----------+                    |
         |                               |
         |                               |
         v                               |
+--------+---------+     +---------------+--------------+
|                  |     |                              |
| udm.auth.session |     | udm.site.import.wizard      |
|                  |     | (TransientModel)            |
+------------------+     |                              |
                         +---------------+--------------+
                                         |
                                         |
                                         v
                         +---------------+--------------+
                         |                              |
                         | udm.site.discovery           |
                         | (TransientModel)             |
                         |                              |
                         +------------------------------+
```

## Hiérarchie des modèles avec le site comme entité centrale

```
                            +-------------------+
                            |                   |
                            |     udm.site      |
                            |                   |
                            +--+------+------+--+
                               |      |      |
                               |      |      |
                               |      |      |
                               |      |      |
                               v      v      v
+---------------+    +------------------+    +----------------+    +----------------+
|               |    |                  |    |                |    |                |
| udm.device    |    | udm.network      |    | udm.vlan       |    | udm.user       |
|               |    |                  |    |                |    |                |
+---------------+    +------------------+    +----------------+    +----------------+
                               |
                               |
                               v
                    +----------+---------+
                    |                    |
                    | udm.firewall.rule  |
                    |                    |
                    +--------------------+
```

## Modèles de support et leur relation avec udm.site

```
+-------------------+
|                   |
|     udm.site      |
|                   |
+--+------+------+--+
   |      |      |
   |      |      |
   v      v      v
+--+------+  +---+----+  +---+----+
|          |  |        |  |        |
| udm.api. |  | udm.   |  | udm.   |
| config   |  | api.log|  | sync.  |
|          |  |        |  | job    |
+----------+  +--------+  +--------+
```

## Détail des relations entre les modèles principaux

```
+-------------------+
|    udm.site       |
|-------------------|
| name              |
| api_type          |<---+
| site_id           |    |
| ...               |    |
+-------------------+    |
        ^                |
        |                |
        |                |
+-------+-------+       |
|  udm.network   |      |
|----------------|      |
| site_id        +------+
| name           |
| subnet         |
| ...            |
+----------------+
        ^
        |
        |
+-------+-------+
|  udm.device    |
|----------------|
| site_id        |
| network_id     +------+
| name           |      |
| mac_address    |      |
| ...            |      |
+----------------+      |
        ^               |
        |               |
        |               |
+-------+-------+      |
|  udm.user      |      |
|----------------|      |
| site_id        |      |
| network_id     +------+
| name           |
| email          |
| ...            |
+----------------+
```

## Relations spécifiques à l'authentification

```
+-------------------+
|    udm.site       |
|-------------------|
| api_type          |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+     +---------------+
| udm.auth.session |     | udm.mfa       |
|------------------|     |---------------|
| site_id          |     | site_id       |
| auth_type        |     | mfa_type      |
| token            |     | mfa_code      |
| expiry           |     | ...           |
| ...              |     |               |
+------------------+     +---------------+
```

## Modèles spécifiques à chaque type d'API

### API Site Manager (distante)

```
+-------------------+
|    udm.site       |
|-------------------|
| api_type='site_manager' |
| api_key           |
| mfa_enabled       |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.device        |
|------------------|
| site_id          |
| cloud_device_id  |
| ...              |
+------------------+

+-------------------+
|    udm.site       |
|-------------------|
| api_type='site_manager' |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.network       |
|------------------|
| site_id          |
| cloud_network_id |
| ...              |
+------------------+
```

### API Controller (locale)

```
+-------------------+
|    udm.site       |
|-------------------|
| api_type='controller' |
| host              |
| port              |
| username          |
| password          |
| controller_type   |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.device        |
|------------------|
| site_id          |
| device_id        |
| adopted          |
| ...              |
+------------------+

+-------------------+
|    udm.site       |
|-------------------|
| api_type='controller' |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.network       |
|------------------|
| site_id          |
| network_id       |
| ...              |
+------------------+
```

## Flux de données pour la synchronisation

```
+-------------------+
|    udm.site       |
|-------------------|
| api_type          |
| last_sync         |
| sync_interval     |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.sync.job      |
|------------------|
| site_id          |
| start_time       |
| end_time         |
| state            |
| sync_type        |
| ...              |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.api.log       |
|------------------|
| site_id          |
| sync_job_id      |
| endpoint         |
| method           |
| status_code      |
| ...              |
+------------------+
```

## Assistant d'importation de site

```
+-------------------+
| udm.site.import.  |
| wizard            |
|-------------------|
| state             |
| api_type          |
| ...               |
+--------+----------+
         |
         |
         v
+--------+---------+
| udm.site.discovery|
|------------------|
| wizard_id        |
| site_name        |
| site_id          |
| selected         |
| ...              |
+------------------+
         |
         |
         v
+--------+---------+
| udm.site          |
|------------------|
| (Créé par        |
|  l'assistant)    |
+------------------+
```

## Légende

- Les flèches indiquent les relations entre les modèles
- Les relations Many2one sont représentées par des flèches simples
- Les relations One2many sont implicites dans la direction opposée aux flèches Many2one
- Les modèles TransientModel sont utilisés pour les assistants et ne sont pas persistants

Cette représentation visuelle montre comment les différents modèles sont liés entre eux, avec le modèle `udm.site` comme entité centrale autour de laquelle s'articulent tous les autres modèles.
