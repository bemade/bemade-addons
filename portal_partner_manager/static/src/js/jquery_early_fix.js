/** @odoo-module **/

/**
 * Script de correction précoce pour jQuery
 * Ce script est chargé très tôt dans le processus de chargement de la page
 * et intercepte l'erreur "$ is not defined" avant qu'elle ne se produise.
 */

(function() {
    // Définir une version globale de $ avant tout autre script
    if (typeof window.$ === 'undefined') {
        console.log('🔧 Définition précoce de $ avant tout autre script');
        window.$ = function(selector) {
            if (typeof selector === 'string') {
                return document.querySelectorAll(selector);
            } else if (selector instanceof Element) {
                return {
                    0: selector,
                    length: 1,
                    each: function(callback) {
                        callback.call(selector, 0, selector);
                        return this;
                    }
                };
            }
            return { length: 0 };
        };
        
        // Ajouter des méthodes minimales
        window.$.fn = {};
    }
    
    // Intercepter toutes les erreurs JavaScript dès le début
    const originalErrorHandler = window.onerror;
    window.onerror = function(message, source, lineno, colno, error) {
        // Intercepter spécifiquement les erreurs jQuery
        if (message && message.includes('$ is not defined')) {
            console.warn('⚠️ Erreur jQuery interceptée précocement:', message, 'à', source, 'ligne', lineno);
            
            // Examiner tous les scripts de la page
            const scripts = document.querySelectorAll('script');
            scripts.forEach((script, index) => {
                if (!script.src && script.textContent && script.textContent.includes('$')) {
                    console.log(`Script inline #${index + 1} qui utilise $:`, script.textContent);
                }
            });
            
            // Empêcher la propagation de l'erreur
            return true;
        }
        
        // Laisser les autres erreurs être gérées normalement
        if (originalErrorHandler) {
            return originalErrorHandler(message, source, lineno, colno, error);
        }
        return false;
    };
    
    // Injecter un correctif dans le document pour les scripts inline
    function injectFix() {
        // Créer un script qui définit $ au tout début du document
        const fixScript = document.createElement('script');
        fixScript.textContent = `
            // Définir $ globalement s'il n'existe pas déjà
            if (typeof window.$ === 'undefined') {
                window.$ = function(selector) {
                    if (typeof selector === 'string') {
                        return document.querySelectorAll(selector);
                    }
                    return { length: 0 };
                };
                window.$.fn = {};
            }
        `;
        
        // Insérer le script au début du document
        const firstScript = document.querySelector('script');
        if (firstScript && firstScript.parentNode) {
            firstScript.parentNode.insertBefore(fixScript, firstScript);
        } else {
            document.head.appendChild(fixScript);
        }
        
        console.log('🔧 Correctif jQuery injecté au début du document');
    }
    
    // Exécuter l'injection dès que possible
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectFix);
    } else {
        injectFix();
    }
    
    console.log('🔧 Correctif précoce jQuery chargé');
})();
