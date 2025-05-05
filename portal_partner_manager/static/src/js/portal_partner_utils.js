/** @odoo-module **/

/**
 * Utilitaires pour la gestion des partenaires dans le portail
 * Réutilise au maximum le code standard d'Odoo
 */

// Fonction de débogage pour afficher des messages dans la console
function debugLog(message, obj) {
    console.log('%c[DEBUG UTILS] ' + message, 'background: #222; color: #bada55', obj || '');
}

/**
        
        debugLog('Displayed state options', $displayedState.length);
        
        var nb = $displayedState.appendTo($state).removeClass('d-none').show().length;
        debugLog('Number of displayed options', nb);
        
        // Option 1: Toujours afficher le champ état/province
        if (alwaysShow) {
            debugLog('Always show option enabled');
            $state.parent().show();
        } 
        // Option 2: N'afficher que si des provinces sont disponibles (comportement standard)
        else {
            debugLog('Toggling state visibility based on options count', nb >= 1);
            $state.parent().toggle(nb >= 1);
        }
        
        debugLog('adaptAddressForm completed successfully');
    } catch (e) {
        console.error('Erreur dans adaptAddressForm:', e);
    }
};

/**
 * Initialise les champs d'adresse pour un formulaire
 * Réutilisable pour le partenaire principal, parent ou frères
 * 
 * @param {Object} widget - Instance du widget contenant les éléments
 * @param {string} stateSelector - Sélecteur pour le champ état
 * @param {string} countrySelector - Sélecteur pour le champ pays
 * @param {boolean} alwaysShowState - Si true, toujours afficher le champ état
 */
export const initAddressForm = function(widget, stateSelector = 'select[name="state_id"]', 
                                      countrySelector = 'select[name="country_id"]', 
                                      alwaysShowState = false) {
    try {
        debugLog('initAddressForm called', {
            stateSelector: stateSelector,
            countrySelector: countrySelector,
            alwaysShowState: alwaysShowState
        });
        
        widget.$state = widget.$(stateSelector);
        widget.$country = widget.$(countrySelector);
        
        debugLog('Found elements', {
            state: widget.$state.length,
            country: widget.$country.length
        });
        widget.$stateOptions = widget.$state.filter(':enabled').find('option:not(:first)');
        
        adaptAddressForm(widget.$state, widget.$country, widget.$stateOptions, alwaysShowState);
    } catch (e) {
        console.error('Erreur dans initAddressForm:', e);
    }
};
