/*
 * Task 1607 — the list header's « + Ajouter » for an inline add panel.
 *
 * button[data-sc-list-add-toggle][aria-controls=<details id>] opens / closes
 * that <details> (the add form right under the header, its own <summary>
 * hidden: the header is the one control). Opening moves the focus to the
 * panel's first TEXT field — task 1646: never a select / picker, and
 * nothing at all on a phone (sc_focus.js). aria-expanded follows the panel however it opens —
 * the button, a « …#<id> » link (sc_app_ui.js), a script — through the
 * <details> « toggle » event. The sort menu is sc_user_menu.js's popup.
 * Inert outside .o_sc_app.
 *
 * Task 1672:
 * - a panel the header toggles never opens / closes from its own title
 *   (<summary>): a tap mid-entry no longer collapses the form; the header
 *   « + Ajouter » stays THE control (aria-expanded / aria-controls kept),
 *   inner disclosures (« Contact d'urgence », « Lier cette note ») work;
 * - after a successful create (« sc:create-success » on the form — the form
 *   guard's fetch post, the player create — or, for a native POST, coming
 *   back to the page from the browser cache) the panel is reset: fields
 *   back to their defaults (a form-mode field — the page's team — and the
 *   device drafts follow « sc:form-reset »), inner disclosures closed, the
 *   check / guard state cleared, the panel closed (the Notepad's
 *   always-open card stays open).
 *
 * Task 1724: « Annuler » (button[data-sc-list-add-cancel], next to the
 * panel's submit) runs the same reset — fields back to their defaults,
 * device drafts dropped, the panel closed — and puts the focus back on the
 * header's « + Ajouter ».
 */

import { focusFirstField } from "@bemade_sports_clinic/js/sc_focus";
import { removeDraftsWithPrefix } from "@bemade_sports_clinic/js/sc_draft_store";

const RESETTABLE = "details.o_sc_list_add_panel, .o_sc_notepad_add";

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
        focusFirstField(panel);
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

// Task 1672: the title of a header-toggled panel never toggles it.
document.addEventListener(
    "click",
    (ev) => {
        const summary = ev.target.closest && ev.target.closest("summary");
        const panel = summary && summary.parentElement;
        if (!panel || !panel.matches("details.o_sc_list_add_panel") || !panel.id || !panel.closest(".o_sc_app")) {
            return;
        }
        if (togglesOf(panel).length) {
            ev.preventDefault();
        }
    },
    true
);

/** Task 1672: an add panel back to an empty form (see the header). */
export function resetAddPanel(form) {
    const panel = form && form.closest && form.closest(RESETTABLE);
    if (!panel || !panel.closest(".o_sc_app")) {
        return false;
    }
    form.reset();
    for (const details of form.querySelectorAll("details")) {
        details.open = false;
    }
    for (const node of form.querySelectorAll("[aria-invalid]")) {
        node.removeAttribute("aria-invalid");
    }
    if (form.dataset.scDraftPrefix) {
        removeDraftsWithPrefix(form.dataset.scDraftPrefix);
    }
    delete form.dataset.scSubmitted;
    // OWL fields, the form guard, the player check follow this event.
    form.dispatchEvent(new CustomEvent("sc:form-reset", { bubbles: true }));
    if (panel.tagName === "DETAILS" && togglesOf(panel).length) {
        panel.open = false;
    }
    return true;
}

document.addEventListener("sc:create-success", (ev) => {
    resetAddPanel(ev.target);
});

// A native POST (no fetch): remember the submit; coming back to this page
// from the browser cache shows the form as it was posted — reset it.
document.addEventListener("submit", (ev) => {
    const form = ev.target;
    if (!ev.defaultPrevented && form.closest && form.closest(RESETTABLE) && form.closest(".o_sc_app")) {
        form.dataset.scSubmitted = "1";
    }
});
window.addEventListener("pageshow", (ev) => {
    if (!ev.persisted) {
        return;
    }
    for (const form of document.querySelectorAll(".o_sc_app form[data-sc-submitted]")) {
        resetAddPanel(form);
    }
});

// Task 1724: « Annuler » of an inline add panel.
document.addEventListener("click", (ev) => {
    const button = ev.target.closest && ev.target.closest("[data-sc-list-add-cancel]");
    if (!button || !button.closest(".o_sc_app")) {
        return;
    }
    const panel = button.closest("details.o_sc_list_add_panel");
    const form = button.closest("form");
    if (!panel || !form) {
        return;
    }
    ev.preventDefault();
    resetAddPanel(form);
    panel.open = false;
    const toggle = togglesOf(panel)[0];
    if (toggle) {
        toggle.focus();
    }
});
