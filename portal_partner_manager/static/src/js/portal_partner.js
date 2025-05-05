/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Surcharge du widget standard d'Odoo pour éviter les conflits.
 * Cette surcharge empêche le widget standard de s'initialiser et de causer des erreurs.
 */
publicWidget.registry.portal_details = publicWidget.Widget.extend({
    selector: '.o_portal_details',
    /**
     * @override
     */
    start: function () {
        console.log('Surcharging standard Odoo widget to prevent errors');
        // Ne rien faire pour éviter les conflits
        return this._super.apply(this, arguments);
    },
});

/**
 * Notre widget personnalisé pour la gestion des formulaires d'adresse.
 */
publicWidget.registry.bemadeCustomAddressManager = publicWidget.Widget.extend({
    selector: '#bemade_company_edit_form',
    events: {
        'change select[name="country_id"]': '_onCountryChange',
    },

    /**
     * @override
     */
    start: function () {
        console.log('Initializing custom country-state widget');
        this._adaptCountryState();
        return this._super.apply(this, arguments);
    },

    /**
     * Adapte les options de province en fonction du pays sélectionné
     * 
     * @private
     */
    _adaptCountryState: function() {
        var $country = this.$('select[name="country_id"]');
        if ($country.length) {
            this._onCountryChange({currentTarget: $country[0]});
        }
    },

    /**
     * Gère l'événement de changement de pays.
     * 
     * @private
     * @param {Event} ev - L'événement de changement
     */
    _onCountryChange: function (ev) {
        console.log('Country changed in custom widget');
        
        try {
            // Approche simplifiée pour éviter les erreurs
            var $country = $(ev.currentTarget);
            var countryID = $country.val() || 0;
            var $state = this.$('select[name="state_id"]');
            
            if (!$state.length) {
                console.warn('State element not found');
                return;
            }
            
            // Approche plus simple qui évite d'utiliser detach() et append()
            // qui peuvent causer des erreurs
            $state.find('option').each(function() {
                var $option = $(this);
                var isFirst = $option.is(':first-child');
                var dataCountryId = $option.data('country_id') || $option.data('country-id');
                
                if (isFirst) {
                    // Toujours afficher la première option (vide)
                    $option.removeClass('d-none').removeAttr('hidden');
                } else if (dataCountryId == countryID) {
                    // Afficher les options correspondant au pays
                    $option.removeClass('d-none').removeAttr('hidden');
                } else {
                    // Cacher les autres options
                    $option.addClass('d-none').attr('hidden', 'hidden');
                }
            });
            
            // Afficher ou cacher le champ d'état en fonction des options disponibles
            var hasVisibleOptions = $state.find('option:not(:first-child):not(.d-none)').length > 0;
            if (hasVisibleOptions) {
                $state.parent().show();
            } else {
                $state.parent().hide();
            }
            
            // Réinitialiser la valeur si l'option sélectionnée n'est plus valide
            var $selectedOption = $state.find('option:selected');
            if ($selectedOption.hasClass('d-none') || $selectedOption.attr('hidden')) {
                $state.val('');
            }
        } catch (error) {
            console.error('Error in _onCountryChange:', error);
        }
    },
});

/**
 * Fonction utilitaire sécurisée pour adapter le formulaire d'adresse
 * en fonction du pays sélectionné.
 * 
 * @param {jQuery} $state - L'élément select des états/provinces
 * @param {jQuery} $country - L'élément select des pays
 * @param {jQuery} $stateOptions - Les options d'états/provinces
 * @param {boolean} alwaysShow - Si true, toujours afficher le champ état
 */
function adaptAddressForm($state, $country, $stateOptions, alwaysShow = false) {
    try {
        if (!$state || !$state.length || !$country || !$country.length) {
            console.warn('Missing required elements for adaptAddressForm');
            return;
        }
        
        var countryID = ($country.val() || 0);
        
        // Vérifier si $stateOptions existe avant d'utiliser detach
        if ($stateOptions && $stateOptions.length) {
            try {
                $stateOptions.detach();
                var $displayedState = $stateOptions.filter('[data-country_id=' + countryID + ']');
                var nb = $displayedState.appendTo($state).length;
                $state.parent().toggle(alwaysShow || nb > 0);
            } catch (err) {
                console.error('Error in detach/append operations:', err);
                // Approche alternative sans detach/append
                $state.find('option').each(function() {
                    var $option = $(this);
                    var isFirst = $option.is(':first-child');
                    var dataCountryId = $option.data('country_id') || $option.attr('data-country_id');
                    
                    if (isFirst || dataCountryId == countryID) {
                        $option.removeClass('d-none').removeAttr('hidden');
                    } else {
                        $option.addClass('d-none').attr('hidden', 'hidden');
                    }
                });
            }
        } else {
            // Approche alternative si $stateOptions n'est pas disponible
            $state.find('option').each(function() {
                var $option = $(this);
                var isFirst = $option.is(':first-child');
                var dataCountryId = $option.data('country_id') || $option.attr('data-country_id');
                
                if (isFirst || dataCountryId == countryID) {
                    $option.removeClass('d-none').removeAttr('hidden');
                } else {
                    $option.addClass('d-none').attr('hidden', 'hidden');
                }
            });
            
            // Afficher ou cacher le champ d'état
            var hasVisibleOptions = $state.find('option:not(:first-child):not(.d-none)').length > 0;
            $state.parent().toggle(alwaysShow || hasVisibleOptions);
        }
        
        // Réinitialiser la valeur si l'option sélectionnée n'est plus valide
        var $selectedOption = $state.find('option:selected');
        if ($selectedOption.hasClass('d-none') || $selectedOption.attr('hidden')) {
            $state.val('');
        }
    } catch (error) {
        console.error('Error in adaptAddressForm:', error);
    }
}

/**
 * Initialise les éléments du formulaire d'adresse.
 * 
 * @param {Object} widget - Le widget contenant les éléments
 * @param {string} stateSelector - Sélecteur pour l'élément state
 * @param {string} countrySelector - Sélecteur pour l'élément country
 * @param {boolean} alwaysShow - Si true, toujours afficher le champ état
 */
function initAddressForm(widget, stateSelector, countrySelector, alwaysShow = false) {
    try {
        if (!widget || !widget.$) {
            console.warn('Invalid widget for initAddressForm');
            return;
        }
        
        var $state = widget.$(stateSelector);
        var $country = widget.$(countrySelector);
        
        if (!$state.length || !$country.length) {
            console.warn('State or country elements not found');
            return;
        }
        
        // Stocker les références pour une utilisation ultérieure
        widget.$state = $state;
        widget.$country = $country;
        widget.$stateOptions = $state.find('option[data-country_id]').detach();
        
        // Initialiser l'affichage
        adaptAddressForm($state, $country, widget.$stateOptions, alwaysShow);
    } catch (error) {
        console.error('Error in initAddressForm:', error);
    }
}

/**
 * Widget pour la gestion du formulaire d'adresse du partenaire parent.
 * Réutilise le même code que le widget principal avec un sélecteur différent.
 */
publicWidget.registry.bemadeParentCompanyDetails = publicWidget.Widget.extend({
    selector: '.o_portal_parent_company',
    events: {
        'change select[name="parent_country_id"]': '_onCountryChange',
    },
    
    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        
        try {
            // Utilisation de l'utilitaire d'initialisation avec des sélecteurs personnalisés
            initAddressForm(
                this, 
                'select[name="parent_state_id"]', 
                'select[name="parent_country_id"]', 
                true // Option 1: Toujours afficher le champ état
            );
        } catch (error) {
            console.error('Error initializing parent company form:', error);
        }
        
        return def;
    },
    
    /**
     * Gère l'événement de changement de pays pour le partenaire parent.
     * 
     * @private
     */
    _onCountryChange: function () {
        try {
            if (this.$state && this.$country && this.$stateOptions) {
                adaptAddressForm(this.$state, this.$country, this.$stateOptions, true);
            }
        } catch (error) {
            console.error('Error in parent company _onCountryChange:', error);
        }
    },
});

/**
 * Widget pour la gestion des formulaires d'adresse des partenaires frères.
 * Réutilise le même code que les autres widgets.
 */
publicWidget.registry.bemadeSiblingPartnerDetails = publicWidget.Widget.extend({
    selector: '.o_portal_sibling_partners',
    events: {
        'change select[name^="sibling_country_id"]': '_onCountryChange',
    },
    
    /**
     * @override
     */
    start: function () {
        var def = this._super.apply(this, arguments);
        
        try {
            // Initialiser chaque formulaire de partenaire frère
            this.$('div[data-sibling-id]').each(function() {
                try {
                    var siblingId = $(this).data('sibling-id');
                    var widget = {
                        $: function(selector) { return $(this).find(selector); }.bind(this)
                    };
                    
                    initAddressForm(
                        widget,
                        `select[name="sibling_state_id_${siblingId}"]`,
                        `select[name="sibling_country_id_${siblingId}"]`,
                        false // Option 2: Comportement standard
                    );
                    
                    // Stocker les références pour une utilisation ultérieure
                    $(this).data('widget', widget);
                } catch (innerError) {
                    console.error('Error initializing sibling form:', innerError);
                }
            });
        } catch (error) {
            console.error('Error in sibling partners initialization:', error);
        }
        
        return def;
    },
    
    /**
     * Gère l'événement de changement de pays pour un partenaire frère.
     * 
     * @private
     */
    _onCountryChange: function (ev) {
        try {
            // Identifier le partenaire frère concerné
            var $target = $(ev.currentTarget);
            var $siblingContainer = $target.closest('div[data-sibling-id]');
            var widget = $siblingContainer.data('widget');
            
            if (widget && widget.$state && widget.$country) {
                adaptAddressForm(widget.$state, widget.$country, widget.$stateOptions || null, false);
            }
        } catch (error) {
            console.error('Error in sibling _onCountryChange:', error);
        }
    },
});

export default {
    bemadePortalDetails: publicWidget.registry.bemadePortalDetails,
    bemadeParentCompanyDetails: publicWidget.registry.bemadeParentCompanyDetails,
    bemadeSiblingPartnerDetails: publicWidget.registry.bemadeSiblingPartnerDetails,
};
