/** @odoo-module **/

/**
 * Outil de débogage avancé pour capturer et analyser les erreurs JavaScript.
 * Ce script intercepte toutes les erreurs JavaScript et les affiche de manière détaillée dans la console.
 * Il inclut également des outils spécifiques pour identifier les scripts qui utilisent jQuery sans vérifier son existence.
 */

// Sauvegarde de la fonction d'erreur originale
const originalErrorHandler = window.onerror;

// Fonction pour obtenir la stack trace d'une erreur
function getStackTrace(error) {
    if (!error || !error.stack) {
        return 'Stack trace non disponible';
    }
    return error.stack;
}

// Fonction pour extraire le contenu d'un script à partir d'une URL
async function fetchScriptContent(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        return await response.text();
    } catch (error) {
        console.error('Erreur lors de la récupération du script:', error);
        return null;
    }
}

// Fonction pour analyser un script et trouver les utilisations de jQuery
async function analyzeScriptForJQuery(source, lineno) {
    if (!source || source === 'edit') {
        // Pour les scripts inline, nous ne pouvons pas récupérer le contenu directement
        console.log('%cScript inline détecté', 'font-weight: bold; color: orange;');
        
        // Rechercher tous les scripts dans le document
        const scripts = document.querySelectorAll('script');
        console.log(`%cAnalyse de ${scripts.length} scripts dans le document`, 'font-weight: bold;');
        
        scripts.forEach((script, index) => {
            const content = script.textContent;
            if (content && content.includes('$') && !content.includes('function $') && !content.includes('window.$')) {
                console.log(`%cScript #${index + 1} utilise jQuery sans vérification:`, 'font-weight: bold; color: red;');
                console.log('%cContenu du script:', 'font-weight: bold;');
                console.log(content);
                
                // Essayer de localiser la ligne exacte
                const lines = content.split('\n');
                lines.forEach((line, lineIndex) => {
                    if (line.includes('$') && !line.includes('function $') && !line.includes('window.$')) {
                        console.log(`%cLigne ${lineIndex + 1}: ${line}`, 'color: red;');
                    }
                });
            }
        });
        return;
    }
    
    // Pour les scripts externes, récupérer le contenu
    const content = await fetchScriptContent(source);
    if (content) {
        const lines = content.split('\n');
        const startLine = Math.max(0, lineno - 10);
        const endLine = Math.min(lines.length, lineno + 10);
        
        console.log('%cExtrait du script autour de la ligne d\'erreur:', 'font-weight: bold;');
        for (let i = startLine; i < endLine; i++) {
            const lineHighlight = i === lineno - 1 ? 'color: red; font-weight: bold;' : '';
            console.log(`%c${i + 1}: ${lines[i]}`, lineHighlight);
        }
    }
}

// Fonction pour analyser une erreur
async function analyzeError(message, source, lineno, colno, error) {
    console.group('%c🔍 Erreur JavaScript interceptée', 'color: red; font-weight: bold; font-size: 14px;');
    console.log('%cMessage:', 'font-weight: bold;', message);
    console.log('%cSource:', 'font-weight: bold;', source);
    console.log('%cLigne:', 'font-weight: bold;', lineno);
    console.log('%cColonne:', 'font-weight: bold;', colno);
    
    if (error) {
        console.log('%cType d\'erreur:', 'font-weight: bold;', error.name);
        console.log('%cStack trace:', 'font-weight: bold;');
        console.log(getStackTrace(error));
        
        // Analyse spécifique pour les erreurs courantes
        if (message.includes('Cannot read properties of null')) {
            console.warn('%cAnalyse:', 'font-weight: bold; color: orange;', 
                'Tentative d\'accès à une propriété d\'un objet null ou undefined. ' +
                'Vérifiez si l\'élément DOM existe avant d\'y accéder.');
                
            // Essayer d'identifier l'élément manquant
            if (source && source.includes('assets_frontend')) {
                console.log('%cErreur dans les assets frontend d\'Odoo', 'font-weight: bold;');
                console.log('Cela peut être dû à un widget Odoo qui tente d\'accéder à un élément qui n\'existe pas encore.');
            }
        } else if (message.includes('$ is not defined')) {
            console.warn('%cAnalyse:', 'font-weight: bold; color: orange;', 
                'jQuery ($) n\'est pas disponible. ' +
                'Vérifiez que jQuery est chargé avant d\'utiliser $ ou utilisez document.querySelector à la place.');
            
            // Analyser le script pour trouver l'utilisation de jQuery
            await analyzeScriptForJQuery(source, lineno);
        }
    }
    
    // Récupérer l'état du DOM au moment de l'erreur
    try {
        console.log('%cÉtat du DOM:', 'font-weight: bold;');
        console.log('Éléments avec la classe "o_portal_details":', document.querySelectorAll('.o_portal_details').length);
        console.log('Éléments avec l\'ID "bemade_company_edit_form":', document.getElementById('bemade_company_edit_form') ? 1 : 0);
        console.log('Sélecteurs de pays:', document.querySelectorAll('select[name="country_id"]').length);
        console.log('Sélecteurs de province:', document.querySelectorAll('select[name="state_id"]').length);
        
        // Vérifier si jQuery est disponible
        console.log('jQuery disponible:', typeof jQuery !== 'undefined' ? 'Oui' : 'Non');
        console.log('$ disponible:', typeof $ !== 'undefined' ? 'Oui' : 'Non');
        
        // Lister tous les scripts de la page
        const scripts = document.querySelectorAll('script');
        console.log(`Nombre de scripts dans la page: ${scripts.length}`);
        scripts.forEach((script, index) => {
            if (script.src) {
                console.log(`Script #${index + 1}: ${script.src}`);
            } else if (script.textContent && script.textContent.length < 100) {
                console.log(`Script inline #${index + 1}: ${script.textContent.substring(0, 100)}...`);
            } else {
                console.log(`Script inline #${index + 1}: [contenu trop long]`);
            }
        });
    } catch (e) {
        console.error('Erreur lors de l\'analyse du DOM:', e);
    }
    
    console.groupEnd();
    
    // Appeler le gestionnaire d'erreurs original s'il existe
    if (originalErrorHandler) {
        return originalErrorHandler(message, source, lineno, colno, error);
    }
    
    // Retourner false pour indiquer que l'erreur a été gérée
    return false;
}

// Remplacer le gestionnaire d'erreurs global
window.onerror = analyzeError;

// Intercepter également les rejets de promesses non gérés
window.addEventListener('unhandledrejection', function(event) {
    console.group('%c🔍 Promesse rejetée non gérée', 'color: red; font-weight: bold; font-size: 14px;');
    console.log('%cRaison:', 'font-weight: bold;', event.reason);
    if (event.reason instanceof Error) {
        console.log('%cStack trace:', 'font-weight: bold;');
        console.log(getStackTrace(event.reason));
    }
    console.groupEnd();
});

// Ajouter un outil pour surveiller les mutations du DOM
function setupDOMObserver() {
    // Créer un observateur de mutations
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && 
                (mutation.target.id === 'bemade_company_edit_form' || 
                 mutation.target.classList.contains('o_portal_details'))) {
                console.log('%c🔄 Mutation du DOM détectée', 'color: blue; font-weight: bold;', {
                    target: mutation.target,
                    addedNodes: mutation.addedNodes.length,
                    removedNodes: mutation.removedNodes.length
                });
            }
        });
    });
    
    // Observer le document entier
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });
    
    console.log('%c🔍 Observateur de DOM installé', 'color: green; font-weight: bold;');
    
    // Rechercher immédiatement les scripts qui utilisent jQuery sans vérification
    const scripts = document.querySelectorAll('script');
    let jQueryUsageFound = false;
    
    scripts.forEach((script, index) => {
        const content = script.textContent;
        if (content && content.includes('$') && !content.includes('function $') && !content.includes('window.$') && !content.includes('typeof $')) {
            jQueryUsageFound = true;
            console.group('%c🔍 Script utilisant jQuery sans vérification détecté', 'color: red; font-weight: bold;');
            console.log(`Script #${index + 1}:`);
            console.log(content);
            console.groupEnd();
        }
    });
    
    if (!jQueryUsageFound) {
        console.log('%cAucun script utilisant jQuery sans vérification n\'a été trouvé dans le document actuel', 'color: green; font-weight: bold;');
    }
}

// Installer l'observateur de DOM lorsque le document est chargé
document.addEventListener('DOMContentLoaded', setupDOMObserver);

// Installer également un observateur pour les scripts ajoutés dynamiquement
function setupScriptObserver() {
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(function(node) {
                    if (node.tagName === 'SCRIPT') {
                        console.log('%c🔍 Script ajouté dynamiquement détecté', 'color: blue; font-weight: bold;');
                        console.log(node);
                        
                        const content = node.textContent;
                        if (content && content.includes('$') && !content.includes('function $') && !content.includes('window.$') && !content.includes('typeof $')) {
                            console.group('%c🔍 Script dynamique utilisant jQuery sans vérification détecté', 'color: red; font-weight: bold;');
                            console.log(content);
                            console.groupEnd();
                        }
                    }
                });
            }
        });
    });
    
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });
    
    console.log('%c🔍 Observateur de scripts dynamiques installé', 'color: green; font-weight: bold;');
}

// Installer l'observateur de scripts dynamiques
document.addEventListener('DOMContentLoaded', setupScriptObserver);

// Afficher un message de démarrage
console.log('%c🔧 Outils de débogage JavaScript avancés chargés', 'color: green; font-weight: bold; font-size: 14px;');
