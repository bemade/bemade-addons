/*
 * Task 1607 — the list header's « + Ajouter » for an inline add panel.
 *
 * button[data-sc-list-add-toggle][aria-controls=<details id>] opens / closes
 * that <details> (the add form right under the header, its own <summary>
 * hidden: the header is the one control). Opening moves the focus to the
 * panel's first field. aria-expanded follows the panel however it opens —
 * the button, a « …#<id> » link (sc_app_ui.js), a script — through the
 * <details> « toggle » event. The sort menu is sc_user_menu.js's popup.
 * Inert outside .o_sc_app.
 */

const FOCUSABLE =
    'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])';

function togglesOf(panel) {
    return [...document.querySelectorAll("[data-sc-list-add-toggle]")].filter(
        (button) => button.getAttribute("aria-controls") === panel.id
    );
}

document.addEventListener("click", (ev) => {
    const button = ev.target.closest && ev.target.closest("[data-sc-list-add-toggle]");
    if (!button || !button.closest(".o_sc_app")) {
        return;
    }
    const panel = document.getElementById(button.getAttribute("aria-controls") || "");
    if (!panel || panel.tagName !== "DETAILS") {
        return;
    }
    ev.preventDefault();
    panel.open = !panel.open;
    if (panel.open) {
        const field = [...panel.querySelectorAll(FOCUSABLE)].find(
            (el) => el.offsetParent !== null && !el.closest("summary")
        );
        if (field) {
            field.focus({ preventScroll: true });
        }
        panel.scrollIntoView({ block: "nearest" });
    }
});

// <details> « toggle » does not bubble: listen in the capture phase.
document.addEventListener(
    "toggle",
    (ev) => {
        const panel = ev.target;
        if (!(panel instanceof HTMLDetailsElement) || !panel.id || !panel.closest(".o_sc_app")) {
            return;
        }
        for (const button of togglesOf(panel)) {
            button.setAttribute("aria-expanded", panel.open ? "true" : "false");
        }
    },
    true
);
