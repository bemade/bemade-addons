/** @odoo-module **/

import { getScrollingElement as getTopScrollingEl } from "@web/core/utils/scrolling";

(function () {
    const w = window;
    const $ = w.jQuery;
    if (!$) {
        return;
    }
    // Polyfill only if missing to avoid overriding Odoo's legacy patch when present
    if (!$.fn.getScrollingElement) {
        /**
         * Returns the top-level scrolling element of the current document as a jQuery collection.
         * Usage parity: $().getScrollingElement()[0]
         */
        $.fn.getScrollingElement = function () {
            const doc = (this && this[0] && this[0].ownerDocument) || w.document;
            return $(getTopScrollingEl(doc));
        };
    }
    if (!$.fn.getScrollingTarget) {
        /**
         * Returns a jQuery collection to listen to scroll events for a given scrollable element.
         * Accepts a DOM element or a jQuery collection.
         * If the element is the document's scrollingElement, return $(window); otherwise return $(element).
         * Usage parity: $().getScrollingTarget(elem)[0]
         */
        $.fn.getScrollingTarget = function (el) {
            const node = (el && el.jquery) ? el[0] : el;
            const doc = (node && node.ownerDocument) || w.document;
            const isDocScrollEl = node === doc.scrollingElement;
            return isDocScrollEl ? $(w) : $(node);
        };
    }
})();
