/*
 * Task 1646 — where the focus goes when an add panel / edit view opens.
 *
 * Owner decision (2026-10-22): on a phone (coarse pointer) NOTHING is
 * focused — no keyboard, no picker pops up; the user taps the field they
 * want. Elsewhere the first visible TEXT field takes the focus (text-like
 * input or textarea) — never a <select>, a date / time / file input or any
 * other picker (on iOS focusing a <select> opens its native picker). No such
 * field: nothing is focused.
 */

const TEXT_FIELD = [
    "textarea",
    "input:not([type])",
    'input[type="text"]',
    'input[type="email"]',
    'input[type="tel"]',
    'input[type="search"]',
    'input[type="number"]',
    'input[type="url"]',
]
    .map((selector) => `${selector}:not([disabled]):not([readonly])`)
    .join(", ");

export function isCoarsePointer() {
    return Boolean(window.matchMedia && window.matchMedia("(pointer: coarse)").matches);
}

/** The first visible text field of ``container`` (never a picker), or null. */
export function firstTextField(container) {
    if (!container) {
        return null;
    }
    return (
        [...container.querySelectorAll(TEXT_FIELD)].find(
            (el) => el.offsetParent !== null && !el.closest("summary")
        ) || null
    );
}

/** Focus per the rule above; returns the focused field (or null). */
export function focusFirstField(container) {
    if (isCoarsePointer()) {
        return null;
    }
    const field = firstTextField(container);
    if (field) {
        field.focus({ preventScroll: true });
    }
    return field;
}
