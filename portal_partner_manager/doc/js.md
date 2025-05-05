# Documentation JavaScript - Portal Partner Manager

Cette documentation détaille les fichiers JavaScript utilisés dans le module Portal Partner Manager pour améliorer l'expérience utilisateur du portail Odoo.

## 1. Fichiers JavaScript du module portal_partner_manager

### 1.1 portal_fix.js

#### Objectif

Ce script corrige une erreur courante dans le portail standard d'Odoo : `Cannot read properties of null (reading 'remove')` qui se produit dans le widget `PortalHomeCounters`.

#### Fonctionnement

Le script applique deux correctifs principaux :

1. **Patch de `Element.prototype.remove`** :
   - Remplace la méthode native `remove()` des éléments DOM
   - Ajoute une gestion d'erreur pour éviter les exceptions quand la méthode est appelée sur des éléments null ou undefined
   - Capture silencieusement les erreurs pour ne pas perturber la console

2. **Patch de `jQuery.fn.remove`** (si jQuery est disponible) :
   - Remplace la méthode jQuery `remove()`
   - Ajoute une gestion d'erreur similaire
   - Retourne l'objet jQuery pour maintenir la chaîne de méthodes

#### Intégration

Ce script est chargé directement dans les templates du portail et s'exécute immédiatement pour corriger les problèmes potentiels avant que d'autres scripts ne s'exécutent.

### 1.2 jquery_early_fix.js

#### Objectif

Ce script est chargé très tôt dans le processus de chargement de la page et intercepte l'erreur "$ is not defined" avant qu'elle ne se produise.

#### Fonctionnement

1. **Définition précoce de jQuery** :
   - Définit une version globale de `$` avant tout autre script
   - Fournit une implémentation minimale des fonctionnalités de base de jQuery

2. **Interception des erreurs** :
   - Intercepte spécifiquement les erreurs liées à jQuery
   - Examine les scripts de la page qui utilisent `$` sans vérification

3. **Injection de correctifs** :
   - Injecte un correctif dans le document pour les scripts inline
   - S'exécute dès que possible dans le cycle de vie du document

#### Intégration

Ce script est chargé en premier dans l'ordre des assets pour s'assurer qu'il est exécuté avant tout autre script qui pourrait utiliser jQuery.

### 1.3 jquery_safety.js

#### Objectif

Ce script assure que `$` est défini et fournit une implémentation de secours si nécessaire. Il résout également le problème "Cannot read properties of null (reading 'remove')" en ajoutant des vérifications de nullité.

#### Fonctionnement

1. **Remplacement de jQuery** :
   - Crée un remplacement minimal pour jQuery si celui-ci n'est pas défini
   - Implémente les méthodes les plus couramment utilisées (each, on, val, find, parent, show, hide, etc.)

2. **Protection contre les erreurs** :
   - Ajoute des vérifications de nullité aux méthodes critiques
   - Intercepte les erreurs courantes liées à jQuery

3. **Initialisation multiple** :
   - S'exécute à plusieurs moments du cycle de vie de la page
   - Assure que les protections sont en place même si jQuery est chargé dynamiquement

#### Intégration

Ce script est chargé après jquery_early_fix.js mais avant les autres scripts qui dépendent de jQuery.

### 1.4 debug_tools.js

#### Objectif

Cet outil de débogage avancé capture et analyse les erreurs JavaScript. Il intercepte toutes les erreurs et les affiche de manière détaillée dans la console, avec des outils spécifiques pour identifier les scripts qui utilisent jQuery sans vérifier son existence.

#### Fonctionnement

1. **Interception des erreurs** :
   - Remplace le gestionnaire d'erreurs global
   - Intercepte les rejets de promesses non gérés

2. **Analyse des erreurs** :
   - Extrait la stack trace des erreurs
   - Récupère le contenu des scripts externes
   - Analyse les scripts pour trouver les utilisations problématiques de jQuery

3. **Surveillance du DOM** :
   - Observe les mutations du DOM
   - Détecte les scripts ajoutés dynamiquement

#### Intégration

Ce script est chargé en mode développement pour aider à identifier et résoudre les problèmes JavaScript.

### 1.5 portal_partner.js

#### Objectif

Ce module implémente plusieurs widgets pour la gestion des formulaires d'adresse dans le portail, notamment pour filtrer dynamiquement les provinces/états en fonction du pays sélectionné.

#### Widgets

1. **bemadeCustomAddressManager** :
   - **Sélecteur** : `#bemade_company_edit_form`
   - **Événements** : `change select[name="country_id"]`
   - Adapte les options de province en fonction du pays sélectionné

2. **bemadeParentCompanyDetails** :
   - Gère le formulaire d'adresse du partenaire parent
   - Réutilise le même code que le widget principal avec un sélecteur différent

3. **bemadeSiblingDetails** :
   - Gère les formulaires d'adresse des partenaires frères
   - Supporte plusieurs formulaires sur la même page

#### Fonctions utilitaires

- **adaptAddressForm** : Adapte le formulaire d'adresse en fonction du pays sélectionné
- **initAddressForm** : Initialise les éléments du formulaire d'adresse

#### Intégration

Ce script est chargé dans les pages du portail qui contiennent des formulaires d'adresse, comme la page d'édition de la société ou des contacts.

### 1.6 portal_partner_utils.js

#### Objectif

Ce module fournit des fonctions utilitaires pour la gestion des partenaires dans le portail, en réutilisant au maximum le code standard d'Odoo.

#### Fonctions

1. **debugLog** :
   - Fonction de débogage pour afficher des messages dans la console
   - Utilise un formatage spécifique pour identifier facilement les messages

2. **adaptAddressForm** :
   - Adapte le formulaire d'adresse en fonction du pays sélectionné
   - Gère l'affichage conditionnel du champ état/province

3. **initAddressForm** :
   - Initialise les champs d'adresse pour un formulaire
   - Réutilisable pour le partenaire principal, parent ou frères

#### Intégration

Ce module est importé par portal_partner.js et utilisé dans les différents widgets pour gérer les formulaires d'adresse.

## 2. Intégration avec Odoo

### 2.1 Surcharge des widgets standard

Le module surcharge certains widgets standard d'Odoo pour éviter les conflits :

```javascript
publicWidget.registry.portal_details = publicWidget.Widget.extend({
    selector: '.o_portal_details',
    start: function () {
        // Ne rien faire pour éviter les conflits
        return this._super.apply(this, arguments);
    },
});
```

### 2.2 Gestion des dépendances

Les scripts sont chargés dans un ordre spécifique pour assurer que les correctifs sont en place avant l'exécution des autres scripts :

1. jquery_early_fix.js
2. jquery_safety.js
3. portal_fix.js
4. debug_tools.js (en mode développement)
5. portal_partner_utils.js
6. portal_partner.js

## 3. Résolution des problèmes courants

### 3.1 Erreur "Cannot read properties of null (reading 'remove')"

Cette erreur est résolue par plusieurs mécanismes :

1. **portal_fix.js** : Patch direct des méthodes `remove()`
2. **jquery_safety.js** : Vérifications de nullité dans les méthodes jQuery

### 3.2 Erreur "$ is not defined"

Cette erreur est résolue par :

1. **jquery_early_fix.js** : Définition précoce de `$`
2. **jquery_safety.js** : Implémentation de secours pour jQuery

### 3.3 Problèmes de formulaires d'adresse

Les problèmes liés aux formulaires d'adresse (affichage des provinces, validation, etc.) sont gérés par :

1. **portal_partner.js** : Widgets spécifiques pour chaque type de formulaire
2. **portal_partner_utils.js** : Fonctions utilitaires réutilisables**Méthodes principales** :

1. **`start()`** :
   - Initialise le widget
   - Capture les références aux éléments du formulaire
   - Appelle `_adaptAddressFormParent()` pour configurer initialement le formulaire

2. **`_adaptAddressFormParent()`** :
   - Filtre les options du champ province/état en fonction du pays sélectionné
   - Affiche uniquement les provinces/états correspondant au pays choisi
   - Masque complètement le champ province/état si aucune option n'est disponible pour le pays sélectionné

3. **`_onCountryChangeParent()`** :
   - Gestionnaire d'événement pour le changement de pays
   - Appelle `_adaptAddressFormParent()` pour mettre à jour le formulaire

### Intégration

Ce widget est enregistré dans le registre des widgets publics d'Odoo et est automatiquement initialisé lorsque les éléments correspondant au sélecteur `.o_partner_manager_portal_details` sont présents dans la page.

### 1.3 Bonnes pratiques implémentées

1. **Gestion des erreurs** : Les deux scripts incluent une gestion robuste des erreurs pour éviter les interruptions d'exécution

2. **Commentaires détaillés** : Le code est bien documenté avec des commentaires expliquant le fonctionnement et l'objectif de chaque section

3. **Encapsulation** : Les scripts utilisent des IIFE (Immediately Invoked Function Expressions) ou le système de modules d'Odoo pour éviter de polluer l'espace de noms global

4. **Compatibilité** : Le code prend en compte différents scénarios (présence ou absence de jQuery, éléments manquants, etc.)

5. **Séparation des préoccupations** : Chaque fichier a une responsabilité unique et bien définie

## 2. Fichiers JavaScript du module portal standard d'Odoo

Cette section documente les fichiers JavaScript du module portal standard d'Odoo (`odoo/addons/portal/static/src/js`) qui servent de base au module Portal Partner Manager.

### Comparaison des méthodes de gestion des provinces/états

#### Comparaison entre `_adaptAddressForm()` (standard) et `_adaptAddressFormParent()` (personnalisé)

| Aspect | Solution 1 (portal_partner.js personnalisé) | Solution 2 (portal.js standard) |
|--------|-------------------------------------------|----------------------------------|
| **Sélecteur** | `.o_partner_manager_portal_details` | `.o_portal_details` |
| **Gestion des erreurs** | Utilise try/catch pour éviter les erreurs JS | Aucune |
| **Visibilité du champ état** | Option configurable (commentée) pour toujours afficher le champ ou le masquer | Masque le champ si aucun état n'est disponible |
| **Commentaires** | Détaillés expliquant le fonctionnement et les options | Minimalistes |
| **Flexibilité** | Propose deux approches (lignes 50-55) | Fixe |

#### Réutilisabilité de la solution 2 (standard)

La solution 2 (standard) d'Odoo pourrait-elle être remplacée par la solution 1 (personnalisée) ? Oui, et cela présenterait plusieurs avantages :

1. **Robustesse améliorée** : L'ajout de la gestion des erreurs avec try/catch éviterait les interruptions potentielles

2. **Flexibilité** : Le code personnalisé propose deux options commentées pour la visibilité du champ état :
   - Option 1 (ligne 51-52) : Toujours afficher le champ état, même sans options disponibles
   - Option 2 (ligne 55) : N'afficher que si des provinces sont disponibles (comportement standard)

3. **Maintenabilité** : Les commentaires détaillés faciliteraient la compréhension et la maintenance

4. **Compatibilité** : La solution 1 reste fonctionnellement équivalente à la solution 2 standard, assurant une compatibilité totale

Pour appliquer la solution personnalisée en remplacement de la solution standard, il suffirait de :
1. Copier la méthode `_adaptAddressFormParent()` dans le code standard
2. La renommer en `_adaptAddressForm()`
3. Ajuster le sélecteur pour utiliser `.o_portal_details`
4. Choisir l'option de visibilité souhaitée (décommenter l'option 1 ou conserver l'option 2)

## 3. Réutilisation maximale du code standard d'Odoo

### 3.1 Utilisation directe du code de `portal.js` pour les partenaires

Voici comment réutiliser directement le code standard d'Odoo (`odoo/addons/portal/static/src/js`) pour gérer l'édition du partenaire parent et des partenaires frères :

#### 1. Importation directe des modules standard

```javascript
// Dans votre fichier portal_partner.js
import { PortalHomeCounters } from "@portal/static/src/js/portal.js";
import PortalComposer from "@portal/static/src/js/portal_composer.js";

// Réutiliser directement les classes existantes
```

#### 2. Utilisation du widget portalDetails avec un minimum de modifications

```javascript
// Utiliser le widget portalDetails avec un minimum de modifications
publicWidget.registry.bemadePortalDetails = publicWidget.Widget.extend({
    selector: '.o_partner_manager_portal_details',
    events: {
        'change select[name="country_id"]': '_onCountryChangeParent',
    },

    start: function () {
        // Code identique à portalDetails.start()
        var def = this._super.apply(this, arguments);
        this.$state = this.$('select[name="state_id"]');
        this.$stateOptions = this.$state.filter(':enabled').find('option:not(:first)');
        this._adaptAddressFormParent();
        return def;
    },

    _adaptAddressFormParent: function () {
        // Code presque identique à _adaptAddressForm() avec try/catch en plus
        try {
            var $country = this.$('select[name="country_id"]');
            var countryID = $country.val() || 0;
            this.$stateOptions.detach();
            var $displayedState = this.$stateOptions.filter('[data-country_id="' + countryID + '"]');
            var nb = $displayedState.appendTo(this.$state).removeClass('d-none').show().length;
            this.$state.parent().toggle(nb >= 1);
        } catch (e) {
            console.error('Erreur lors de l\'adaptation du formulaire d\'adresse:', e);
        }
    },

    _onCountryChangeParent: function () {
        // Identique à _onCountryChange()
        this._adaptAddressFormParent();
    },
});
```

#### 3. Réutilisation du code pour les compteurs et la recherche

```javascript
// Réutiliser directement les widgets PortalHomeCounters et portalSearchPanel
export const PortalPartnerHomeCounters = PortalHomeCounters.extend({
    // Ajouter uniquement les méthodes spécifiques aux partenaires
    _getCountersAlwaysDisplayed() {
        // Surcharger pour ajouter les compteurs de partenaires
        return [...super._getCountersAlwaysDisplayed(), 'parent_company', 'sibling_partners'];
    },
});
```

### 3.2 Modifications minimales des templates

```xml
<!-- Réutiliser le template portal_my_details avec des modifications minimales -->
<template id="portal_my_details" inherit_id="portal.portal_my_details">
    <!-- Ajouter uniquement les champs spécifiques aux partenaires parent/frères -->
    <xpath expr="//div[hasclass('o_portal_details')]" position="attributes">
        <attribute name="class" add="o_partner_manager_portal_details" separator=" "/>
    </xpath>
</template>
```

### 3.3 Stratégie concrète pour maximiser la réutilisation

1. **Copier-coller stratégique** : Pour les fonctions comme `_adaptAddressForm()`, copier le code standard et ajouter uniquement les améliorations nécessaires (try/catch)

2. **Héritage minimal** : Hériter des widgets standard uniquement lorsque nécessaire, en préservant au maximum le comportement d'origine

3. **Partage de code** : Utiliser les mêmes noms de variables et de fonctions pour faciliter la maintenance

4. **Modifications CSS plutôt que HTML** : Utiliser CSS pour modifier l'apparence sans changer la structure HTML

5. **Conserver la compatibilité des événements** : Maintenir les mêmes noms d'événements et sélecteurs pour assurer la compatibilité

### 3.4 Exemple de mise en œuvre pour l'édition du partenaire parent

```javascript
// Exemple concret de réutilisation maximale

// 1. Copier directement le code de portal.js pour les fonctions de base
const adaptAddressForm = function($state, $country) {
    // Code copié directement de portal.js avec try/catch ajouté
    try {
        var countryID = ($country.val() || 0);
        var $stateOptions = $state.filter(':enabled').find('option:not(:first)');
        $stateOptions.detach();
        var $displayedState = $stateOptions.filter('[data-country_id=' + countryID + ']');
        var nb = $displayedState.appendTo($state).removeClass('d-none').show().length;
        $state.parent().toggle(nb >= 1);
    } catch (e) {
        console.error('Error in adaptAddressForm:', e);
    }
};

// 2. Utiliser cette fonction dans les widgets pour le partenaire parent et les contacts
publicWidget.registry.portalParentCompanyDetails = publicWidget.Widget.extend({
    selector: '.o_portal_parent_company',
    events: {
        'change select[name="country_id"]': '_onCountryChange',
    },
    
    start: function () {
        this.$state = this.$('select[name="state_id"]');
        this.$country = this.$('select[name="country_id"]');
        adaptAddressForm(this.$state, this.$country);
        return this._super.apply(this, arguments);
    },
    
    _onCountryChange: function () {
        adaptAddressForm(this.$state, this.$country);
    },
});
```

### 2.1 portal.js

Ce fichier contient les widgets principaux du portail standard d'Odoo.

#### Widgets principaux

1. **portalDetails** - Widget pour gérer les formulaires d'adresse
   - **Sélecteur** : `.o_portal_details`
   - **Fonctionnalités** : Gère l'affichage dynamique des états/provinces en fonction du pays sélectionné
   - **Méthodes clés** : 
     - `_adaptAddressForm()` : Filtre les options d'états selon le pays
     - `_onCountryChange()` : Gère l'événement de changement de pays

2. **PortalHomeCounters** - Widget pour afficher les compteurs sur la page d'accueil du portail
   - **Sélecteur** : `.o_portal_my_home`
   - **Fonctionnalités** : Met à jour dynamiquement les compteurs de documents (factures, commandes, etc.)
   - **Méthodes clés** :
     - `_updateCounters()` : Récupère et affiche les compteurs via RPC
     - `_getCountersAlwaysDisplayed()` : Liste des compteurs à toujours afficher

3. **portalSearchPanel** - Widget pour gérer la recherche dans le portail
   - **Sélecteur** : `.o_portal_search_panel`
   - **Fonctionnalités** : Gère les filtres de recherche et le champ de recherche
   - **Méthodes clés** :
     - `_adaptSearchLabel()` : Met à jour le placeholder du champ de recherche
     - `_search()` : Exécute la recherche avec les paramètres sélectionnés

### 2.2 portal_composer.js

Gère le composeur de messages dans le portail, permettant aux utilisateurs d'envoyer des messages et des pièces jointes.

#### Widget PortalComposer

- **Template** : `portal.Composer`
- **Fonctionnalités** :
  - Composition de messages
  - Gestion des pièces jointes (ajout/suppression)
  - Envoi de messages avec pièces jointes

- **Méthodes clés** :
  - `_onFileInputChange()` : Gère l'ajout de fichiers
  - `_onAttachmentDeleteClick()` : Supprime une pièce jointe
  - `_onSubmitButtonClick()` : Envoie le message
  - `_chatterPostMessage()` : Effectue l'appel RPC pour poster le message

### 2.3 portal_security.js

Gère les fonctionnalités de sécurité du portail, notamment la gestion des clés API et la déconnexion des appareils.

#### Widgets principaux

1. **NewAPIKeyButton** - Gère la création de nouvelles clés API
   - **Sélecteur** : `.o_portal_new_api_key`
   - **Fonctionnalités** : Affiche un dialogue pour créer une nouvelle clé API avec description et durée

2. **RemoveAPIKeyButton** - Gère la suppression des clés API
   - **Sélecteur** : `.o_portal_remove_api_key`
   - **Fonctionnalités** : Supprime une clé API existante après confirmation

3. **LogOutAllDevicesButton** - Gère la déconnexion de tous les appareils
   - **Fonctionnalités** : Déconnecte l'utilisateur de toutes les sessions actives

#### Fonction utilitaire

- `handleCheckIdentity()` : Gère la vérification d'identité pour les opérations sensibles

### 2.4 portal_sidebar.js

Gère l'affichage de la barre latérale du portail, notamment les informations d'échéance.

#### Widget PortalSidebar

- **Fonctionnalités** :
  - Affichage des délais ("Dû aujourd'hui", "Dû dans X jours", "X jours de retard")
  - Impression de contenu via iframe

- **Méthodes clés** :
  - `_setDelayLabel()` : Calcule et affiche les informations de délai
  - `_printIframeContent()` : Gère l'impression de contenu

### 2.5 components/input_confirmation_dialog/input_confirmation_dialog.js

Composant OWL pour afficher une boîte de dialogue de confirmation avec un champ de saisie.

#### Classe InputConfirmationDialog

- **Hérite de** : `ConfirmationDialog`
- **Template** : `portal.InputConfirmationDialog`
- **Fonctionnalités** :
  - Affiche une boîte de dialogue avec un champ de saisie
  - Gère la validation par la touche Entrée
  - Permet de récupérer la valeur saisie lors de la confirmation