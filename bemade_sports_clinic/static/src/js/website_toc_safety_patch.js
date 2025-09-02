/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Safely guard against null elements in TOC snippet's _stripNavbarStyles
if (publicWidget && publicWidget.registry && publicWidget.registry.snippetTableOfContent) {
    publicWidget.registry.snippetTableOfContent.include({
        _stripNavbarStyles() {
            // This matches Odoo's original intent while being defensive
            const root = this && this.el ? this.el : null;
            if (!root) {
                return;
            }
            const nodes = root.querySelectorAll('.s_table_of_content_navbar .table_of_content_link');
            nodes.forEach((node) => {
                let el = node;
                try {
                    const translationEl = el ? el.querySelector('span[data-oe-translation-state]') : null;
                    if (translationEl instanceof Element) {
                        el = translationEl;
                    }
                    if (el && typeof el.textContent !== 'undefined') {
                        const text = el.textContent || '';
                        el.textContent = text;
                    }
                } catch (_e) {
                    // Silently ignore to avoid breaking the page due to malformed DOM
                }
            });
        },
    });
}
