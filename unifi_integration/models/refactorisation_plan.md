# Plan de refactorisation du module UniFi Integration

## Problème identifié

Le fichier `unifi_site.py` est trop volumineux (plus de 4000 lignes) et contient une logique qui mélange deux types d'API différents (Controller et Site Manager). Cela rend le code difficile à maintenir et à faire évoluer.

## Approche de refactorisation

Nous allons utiliser des mixins pour séparer la logique spécifique à chaque type d'API. Voici les étapes de la refactorisation :

1. Créer deux mixins :
   - `UnifiControllerAPIMixin` : pour les fonctionnalités spécifiques à l'API Controller
   - `UnifiSiteManagerAPIMixin` : pour les fonctionnalités spécifiques à l'API Site Manager

2. Modifier le modèle `UnifiSite` pour déléguer les appels aux mixins appropriés en fonction du type d'API.

3. Déplacer les méthodes spécifiques à chaque type d'API dans les mixins correspondants.

## Avantages de cette approche

1. **Séparation des préoccupations** : Chaque mixin contient uniquement le code spécifique à un type d'API.
2. **Réduction de la taille des fichiers** : Le fichier principal devient beaucoup plus petit et gérable.
3. **Facilité d'extension** : Ajouter un nouveau type d'API nécessite simplement de créer un nouveau mixin.
4. **Meilleure testabilité** : Les mixins peuvent être testés indépendamment du modèle principal.
5. **Clarté du code** : Les développeurs peuvent facilement identifier où se trouve l'implémentation d'une fonctionnalité pour un type d'API spécifique.

## Implémentation

Les fichiers suivants ont été créés ou modifiés :

1. `unifi_controller_api_mixin.py` : Contient le mixin pour l'API Controller
2. `unifi_site_manager_api_mixin.py` : Contient le mixin pour l'API Site Manager
3. `unifi_site.py` : Modifié pour utiliser les mixins

Le modèle `UnifiSite` délègue maintenant les appels aux mixins appropriés en fonction du type d'API, ce qui permet de réduire considérablement la taille du fichier et d'améliorer la maintenabilité du code.