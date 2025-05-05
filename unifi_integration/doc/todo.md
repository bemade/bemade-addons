## 11. Refactorisation avec mixins

Suite à la refactorisation du modèle UnifiSite en utilisant des mixins, voici les tâches à accomplir pour finaliser cette approche :

### 11.1 Implémentation des mixins
- [x] Créer le mixin `UnifiControllerAPIMixin` pour les fonctionnalités spécifiques à l'API Controller
- [x] Créer le mixin `UnifiSiteManagerAPIMixin` pour les fonctionnalités spécifiques à l'API Site Manager
- [x] Documenter les mixins et leur utilisation

### 11.2 Méthodes à implémenter dans les mixins
- [ ] Compléter l'implémentation de `_get_controller_vlan_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_controller_user_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_controller_firewall_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_controller_port_forward_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_controller_system_info_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_controller_dns_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_controller_wifi_data` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_network_data` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_vlan_data` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_user_data` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_firewall_data` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_port_forward_data` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_system_info_data` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_get_site_manager_dns_data` dans `UnifiSiteManagerAPIMixin`

### 11.3 Méthodes de synchronisation
- [ ] Compléter l'implémentation de `_sync_controller_devices` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_networks` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_vlans` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_users` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_firewall_rules` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_port_forwards` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_system_info` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_dns` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_wifi` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_controller_routing` dans `UnifiControllerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_devices` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_networks` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_vlans` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_users` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_firewall_rules` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_port_forwards` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_system_info` dans `UnifiSiteManagerAPIMixin`
- [ ] Compléter l'implémentation de `_sync_site_manager_dns` dans `UnifiSiteManagerAPIMixin`

### 11.4 Intégration avec le modèle UnifiSite
- [ ] Mettre à jour toutes les méthodes du modèle UnifiSite pour déléguer aux mixins
- [ ] Vérifier que toutes les méthodes de délégation fonctionnent correctement
- [ ] Tester la compatibilité avec les vues existantes
- [ ] S'assurer que les méthodes de calcul (`_compute_*`) fonctionnent correctement avec les mixins

### 11.5 Tests et validation
- [ ] Créer des tests unitaires pour les mixins
- [ ] Tester les méthodes de synchronisation avec des données réelles
- [ ] Vérifier que les performances sont maintenues ou améliorées
- [ ] Valider que toutes les fonctionnalités existantes continuent de fonctionner

### 11.6 Documentation
- [ ] Mettre à jour la documentation technique pour refléter l'utilisation des mixins
- [ ] Documenter les bonnes pratiques pour étendre les mixins
- [ ] Créer des exemples d'utilisation des mixins pour les développeurs
