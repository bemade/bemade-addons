# Analyse des modules portail vendeur Odoo

## 1. portal_partner_manager
- **Rôle** : Extension du portail Odoo pour permettre aux utilisateurs de gérer leur société parente et leurs contacts via le portail.
- **Points clés** :
    - Ajoute/modifie les templates du portail (cartes société, contacts, vendors).
    - Utilise des templates hérités de `portal.portal_my_home`.
    - Les blocs vendors/clients sont insérés via des xpaths, mais il faut que les IDs ciblés existent dans la vue parente.
    - Les modèles Python gèrent les droits et la logique de modification côté portail.
    - Contrôleurs spécifiques pour la gestion des sociétés/contacts via le portail.
    - Sécurité renforcée par des règles d'accès et des contrôles dans les méthodes.

## 2. st_laurent_portal_vendor
- **Rôle** : Fournit l'espace vendeur, la gestion des demandes pour devenir vendeur, l'affichage des produits vendeurs, etc.
- **Points clés** :
    - Nombreux templates pour l'espace vendeur, les demandes, la gestion des produits et des catégories.
    - Contrôleurs dédiés pour les routes `/my/vendor`, `/my/vendor/request`, etc.
    - Les boutons d'accès aux produits, locations, etc., dépendent de la structure des templates et de la logique de visibilité.
    - Les vues utilisent parfois des conditions (`t-if`) pour afficher ou non certains boutons.
    - Les modèles Python gèrent la logique des demandes, les droits d'accès, et l'affichage des informations vendeur.
    - Les modules peuvent se marcher sur les pieds si plusieurs héritent ou modifient la même vue parent.

## 3. vendor_product_management
- **Rôle** : Gestion des produits et des emplacements (locations) côté vendeur.
- **Points clés** :
    - Modèles `res.partner` enrichis avec des One2many vers produits et locations.
    - Champs calculés pour compter produits/locations.
    - Vues pour la gestion des produits, locations, supplierinfo, etc.
    - Si les boutons n'apparaissent pas dans le portail, vérifier que les champs sont bien passés au template et que les routes existent côté contrôleur.
    - Peut nécessiter une intégration explicite dans les templates du portail vendeur.

## 4. vendor_portal_management
- **Rôle** : Fournit une surcouche portail vendeur, cartes d'accès rapide (produits, locations), et personnalisation de l'UI.
- **Points clés** :
    - Ajoute/étend le template `portal_my_home_vendor` avec des entrées pour produits et locations (cartes avec icônes, liens, compteurs).
    - Utilise des xpaths pour insérer les blocs dans la vue parente.
    - Les templates attendent que les variables `products_count`, `locations_count` soient passées au contexte.
    - Breadcrumbs personnalisés pour navigation produits/locations.
    - Si les boutons n'apparaissent pas, vérifier l'ordre de chargement des modules, l'héritage des vues et la présence des variables dans le contexte.

## 5. st_laurent_vendor_orders
- **Rôle** : Gestion des commandes vendeurs dans le portail (affichage, suivi, expédition, notifications).
- **Points clés** :
    - Ajoute des vues portail pour afficher la liste et le détail des commandes vendeurs (`vendor_order_portal_templates.xml`).
    - Les vendeurs voient les commandes associées à leurs produits, avec statuts, montants, et actions d’expédition.
    - Système de notification pour nouvelles commandes et suivi d’expédition.
    - Dépend des modules : `vendor_product_management`, `vendor_portal_management`, `st_laurent_portal_vendor`.
    - Les templates attendent que la variable `vendor_orders` soit passée au contexte par le contrôleur.
    - Ajoute des menus spécifiques pour accéder aux commandes vendeur dans le portail.
    - Les droits d’accès sont gérés via les security et les règles d’accès Odoo.
    - Si la liste n’apparaît pas, vérifier le contexte, les droits, et la route du contrôleur.

## 6. Interactions et points de vigilance
- Plusieurs modules héritent ou modifient les mêmes templates portail (ex: `portal.portal_my_home`).
- Les IDs ou classes ciblés dans les xpaths doivent exister dans la vue héritée, sinon Odoo lève une erreur et/ou le bloc n'est pas inséré.
- Les variables de contexte (ex: `products_count`, `locations_count`) doivent être injectées par le contrôleur pour que les widgets/cartes s'affichent correctement.
- L'ordre d'installation/chargement des modules peut impacter l'affichage (un module peut écraser la vue d'un autre).
- Les droits d'accès (groupes, security) peuvent masquer des boutons ou sections si non configurés pour l'utilisateur courant.
- Le cache Odoo peut empêcher la prise en compte immédiate des modifications de vues/templates.

## 6. Recommandations
- Toujours vérifier l'existence des IDs/classes dans les vues héritées avant d'utiliser un xpath.
- S'assurer que les variables nécessaires sont bien passées au contexte du template.
- Contrôler l'ordre d'installation des modules et l'héritage des vues lors de l'ajout de nouvelles fonctionnalités portail.
- Si un bouton ou une carte n'apparaît pas, vérifier : le template, le contrôleur, les droits, l'ordre des modules, et le cache.

---

**Dernière analyse générée automatiquement le 20/04/2025 à 09:09**

Pour toute question ou besoin de diagnostic sur un point précis, se référer à ce document ou demander une analyse ciblée.
