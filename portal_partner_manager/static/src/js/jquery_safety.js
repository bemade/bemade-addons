/** @odoo-module **/

/**
 * Script de sécurité pour jQuery
 * Ce script assure que $ est défini et fournit une implémentation de secours si nécessaire.
 * Il résout également le problème "Cannot read properties of null (reading 'remove')"
 * en ajoutant des vérifications de nullité.
 */

// Exécution immédiate pour définir $ avant tout autre script
(function() {
    // Définir une version globale de jQuery immédiatement
    if (typeof window.$ === 'undefined') {
        console.log('🛡️ Définition préventive de $ avant chargement de jQuery');
        
        // Créer un remplacement minimal pour jQuery
        window.$ = function(selector) {
            // Version simplifiée de jQuery pour les sélecteurs de base
            if (typeof selector === 'string') {
                return document.querySelectorAll(selector);
            } else if (selector instanceof Element) {
                // Envelopper un élément DOM dans un objet similaire à jQuery
                return {
                    0: selector,
                    length: 1,
                    each: function(callback) {
                        callback.call(selector, 0, selector);
                        return this;
                    },
                    on: function(event, handler) {
                        selector.addEventListener(event, handler);
                        return this;
                    },
                    val: function(value) {
                        if (value === undefined) {
                            return selector.value;
                        }
                        selector.value = value;
                        return this;
                    },
                    find: function(childSelector) {
                        return $(selector.querySelectorAll(childSelector));
                    },
                    parent: function() {
                        return $(selector.parentNode);
                    },
                    show: function() {
                        selector.style.display = '';
                        return this;
                    },
                    hide: function() {
                        selector.style.display = 'none';
                        return this;
                    },
                    addClass: function(className) {
                        selector.classList.add(className);
                        return this;
                    },
                    removeClass: function(className) {
                        selector.classList.remove(className);
                        return this;
                    },
                    hasClass: function(className) {
                        return selector.classList.contains(className);
                    },
                    attr: function(name, value) {
                        if (value === undefined) {
                            return selector.getAttribute(name);
                        }
                        selector.setAttribute(name, value);
                        return this;
                    },
                    removeAttr: function(name) {
                        selector.removeAttribute(name);
                        return this;
                    },
                    data: function(key, value) {
                        const dataKey = 'data-' + key;
                        if (value === undefined) {
                            return selector.getAttribute(dataKey);
                        }
                        selector.setAttribute(dataKey, value);
                        return this;
                    },
                    remove: function() {
                        if (selector && selector.parentNode) {
                            selector.parentNode.removeChild(selector);
                        }
                        return this;
                    }
                };
            }
            return { length: 0 };
        };
        
        // Ajouter des méthodes utiles à $.fn
        window.$.fn = {
            each: function(callback) {
                for (let i = 0; i < this.length; i++) {
                    callback.call(this[i], i, this[i]);
                }
                return this;
            },
            remove: function() {
                if (this && this.length > 0) {
                    for (let i = 0; i < this.length; i++) {
                        if (this[i] && this[i].parentNode) {
                            this[i].parentNode.removeChild(this[i]);
                        }
                    }
                }
                return this;
            }
        };
    }
    
    // Fonction complète d'initialisation des protections jQuery
    function initJQuerySafety() {
        console.log('🛡️ Initialisation des protections jQuery');
        
        // 1. S'assurer que $ est défini avec le vrai jQuery s'il est disponible
        if (typeof jQuery !== 'undefined' && window.$ !== jQuery) {
            // Sauvegarder notre implémentation de secours
            const backupJQuery = window.$;
            
            // Remplacer par le vrai jQuery
            window.$ = jQuery;
            console.log('🛡️ $ remplacé par le vrai jQuery');
            
            // Transférer les méthodes personnalisées si nécessaire
            if (backupJQuery.fn && !$.fn.safeRemove) {
                $.fn.safeRemove = function() {
                    if (this && this.length > 0) {
                        return this.remove();
                    }
                    return this;
                };
            }
        }
        
        // 2. Patch pour le problème "Cannot read properties of null"
        if (Element.prototype.remove) {
            const originalRemove = Element.prototype.remove;
            Element.prototype.remove = function() {
                if (this && this.parentNode) {
                    return originalRemove.apply(this, arguments);
                }
                console.warn('⚠️ Tentative de suppression d\'un élément null ou sans parent évitée');
                return null;
            };
        }
        
        // 3. Patch pour jQuery.remove si disponible
        if ($ && $.fn && $.fn.remove && !$.fn._safePatchApplied) {
            const originalJQueryRemove = $.fn.remove;
            $.fn.remove = function() {
                if (this && this.length > 0) {
                    return originalJQueryRemove.apply(this, arguments);
                }
                console.warn('⚠️ Tentative de $.remove() sur un élément non existant évitée');
                return this;
            };
            $.fn._safePatchApplied = true;
        }
        
        // 4. Intercepter les erreurs globales pour les erreurs jQuery
        if (!window._jqueryErrorHandlerInstalled) {
            const originalErrorHandler = window.onerror;
            window.onerror = function(message, source, lineno, colno, error) {
                // Intercepter spécifiquement les erreurs jQuery
                if (message && (message.includes('$ is not defined') || message.includes('jQuery is not defined'))) {
                    console.warn('⚠️ Erreur jQuery interceptée:', message);
                    return true; // Empêcher la propagation de l'erreur
                }
                
                // Laisser les autres erreurs être gérées normalement
                if (originalErrorHandler) {
                    return originalErrorHandler(message, source, lineno, colno, error);
                }
                return false;
            };
            window._jqueryErrorHandlerInstalled = true;
        }
        
        console.log('🛡️ Protections jQuery installées avec succès');
    }
    
    // Exécuter immédiatement et à plusieurs moments pour s'assurer que les protections sont en place
    try {
        // Exécuter immédiatement
        initJQuerySafety();
        
        // Exécuter quand le DOM est prêt
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initJQuerySafety);
        } else {
            initJQuerySafety();
        }
        
        // Exécuter quand la page est complètement chargée
        window.addEventListener('load', initJQuerySafety);
        
        // Exécuter après un court délai pour s'assurer que jQuery est chargé
        setTimeout(initJQuerySafety, 100);
        setTimeout(initJQuerySafety, 500);
        setTimeout(initJQuerySafety, 1000);
    } catch (e) {
        console.error('Erreur lors de l\'initialisation des protections jQuery:', e);
    }
})();
