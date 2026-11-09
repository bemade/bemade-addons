/*
 * Task 1585 — the tap-to-call / tap-to-email href of a shown phone or email
 * (kind "tel" / "mailto"), or null when there is nothing to dial or write
 * to. A phone keeps only "+" and its digits. Same rule on the server:
 * controllers/app_shell.py sc_contact_href.
 */
export function scContactHref(kind, value) {
    const text = typeof value === "string" ? value.trim() : "";
    if (!text) {
        return null;
    }
    if (kind === "tel") {
        const digits = text.replace(/[^0-9+]/g, "");
        return /[0-9]/.test(digits) ? `tel:${digits}` : null;
    }
    if (kind === "mailto") {
        return `mailto:${text}`;
    }
    return null;
}

/* Show ``display`` in a read-view element; a contact link
 * ([data-sc-display-href]) follows with its href (none while empty). */
export function scSetDisplay(el, display) {
    el.textContent = display || "—";
    const kind = el.dataset.scDisplayHref;
    if (!kind) {
        return;
    }
    const href = scContactHref(kind, display);
    if (href) {
        el.setAttribute("href", href);
    } else {
        el.removeAttribute("href");
    }
}
