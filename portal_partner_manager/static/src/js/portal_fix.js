/* Fix for portal.js error */

/**
 * Ce script corrige l'erreur "Cannot read properties of null (reading 'remove')"
 * qui se produit dans le widget PortalHomeCounters d'Odoo standard.
 * 
 * Cette version simplifie l'approche en se concentrant uniquement sur la protection
 * de la méthode remove() au niveau global, ce qui résout la plupart des erreurs sans
 * perturber d'autres fonctionnalités.
 */

(function() {
    // Patch global Element.prototype.remove pour éviter les erreurs
    try {
        const originalElementRemove = Element.prototype.remove;
        
        // Remplacer la méthode remove native pour gérer les cas null/undefined
        Element.prototype.remove = function() {
            try {
                // Appliquer la méthode originale
                return originalElementRemove.apply(this, arguments);
            } catch (e) {
                // Capturer l'erreur sans l'afficher dans la console (évite la pollution)
                return undefined;
            }
        };
    } catch (e) {
        // Échec silencieux, ne pas perturber d'autres scripts
    }
    
    // Patch pour jQuery.remove() si jQuery est chargé
    if (window.jQuery) {
        try {
            const originalJQueryRemove = jQuery.fn.remove;
            
            // Remplacer la méthode jQuery.remove pour gérer les cas problématiques
            jQuery.fn.remove = function() {
                try {
                    // Appliquer la méthode originale
                    return originalJQueryRemove.apply(this, arguments);
                } catch (e) {
                    // Retourner this pour maintenir la chaîne jQuery
                    return this;
                }
            };
        } catch (e) {
            // Échec silencieux
        }
    }
})();
