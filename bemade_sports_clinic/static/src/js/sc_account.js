/*
 * « Mon compte » (views/sc_app_account.xml, inert outside .o_sc_app):
 * « Contact details » and « Address » are edit cards (pencil → edit view,
 * « Done » closes it — sc_app_ui.js) inside ONE core address form.
 *
 * Review fixes 2026-10-18, round 2 (1018c) — like the rest of the app, each
 * field saves ON ITS OWN (no « Save » / « Cancel »):
 * - a field's change (blur for a text field, pick for a select, Enter)
 *   posts the whole form — ALL current values — to the core
 *   /my/address/submit (its validation; for app-shell users only the name
 *   and the email are required, AppShellAccountPortal);
 * - the field shows the app's save states next to its label
 *   ([data-sc-account-state]: « Saving… », « Saved · 14:05 », « Error — not
 *   saved »); typing again clears it;
 * - success: the cards' read views refresh (read fragments, task 1611), the
 *   page stays; refusal: the core messages show in the card's error box
 *   ([data-sc-account-errors]) and the core's invalid fields are flagged
 *   (.is-invalid);
 * - saves never overlap: a change during a save is sent right after it,
 *   with the values of that moment.
 * A new country is saved without a province (the core address JS reloads
 * the province list for that country; the user then picks one).
 */
import { _t } from "@web/core/l10n/translation";
import { requestRefresh } from "@bemade_sports_clinic/js/sc_fragments";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

const lastSaved = new WeakMap(); // field → the value the server holds
const queues = new WeakMap(); // form → { busy, pending: Set<field> }

function accountForm(node) {
    const form = node && node.closest && node.closest("form[data-sc-account-form]");
    return form && form.closest(".o_sc_app") ? form : null;
}

function cards(form) {
    return [...form.querySelectorAll("[data-sc-edit-card^='account-']")];
}

function cardOf(node) {
    return (node && node.closest && node.closest("[data-sc-edit-card^='account-']")) || null;
}

/** A card's editable field (an input / select of its edit view), or null. */
function accountField(node) {
    if (!node || !node.matches || !node.matches("input[name], select[name], textarea[name]")) {
        return null;
    }
    if (node.type === "hidden" || !node.closest('[data-sc-edit-view="edit"]')) {
        return null;
    }
    return accountForm(node) && cardOf(node) ? node : null;
}

function remember(form) {
    for (const card of cards(form)) {
        for (const field of card.querySelectorAll('[data-sc-edit-view="edit"] [name]')) {
            if (!lastSaved.has(field)) {
                lastSaved.set(field, field.value);
            }
        }
    }
}

function stateNode(field) {
    const box = field.closest(".o_sc_field");
    return box ? box.querySelector("[data-sc-account-state]") : null;
}

function setState(field, status) {
    const node = stateNode(field);
    const box = field.closest(".o_sc_field");
    if (box) {
        if (status) {
            box.dataset.scState = status;
        } else {
            delete box.dataset.scState;
        }
    }
    if (!node) {
        return;
    }
    let text = "";
    if (status === "saving") {
        text = _t("Saving…");
    } else if (status === "saved") {
        const now = new Date();
        text = _t("Saved · %s", `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}`);
    } else if (status === "error") {
        text = _t("Error — not saved");
    }
    node.className = status ? `o_sc_save_state o_sc_save_state_${status}` : "o_sc_save_state";
    node.textContent = text;
    node.hidden = !text;
}

function showErrors(card, messages) {
    const box = card.querySelector("[data-sc-account-errors]");
    if (!box) {
        return;
    }
    box.replaceChildren(
        ...messages.map((text) => {
            const line = document.createElement("h5");
            line.textContent = text;
            return line;
        })
    );
}

function flag(form, invalid) {
    for (const field of form.querySelectorAll(".is-invalid")) {
        if (!invalid.includes(field.name)) {
            field.classList.remove("is-invalid");
            field.removeAttribute("aria-invalid");
        }
    }
    for (const name of invalid) {
        const field = form.elements[name];
        if (field && field.classList) {
            field.classList.add("is-invalid");
            field.setAttribute("aria-invalid", "true");
        }
    }
}

function queue(form) {
    if (!queues.has(form)) {
        queues.set(form, { busy: false, pending: new Set() });
    }
    return queues.get(form);
}

/** Save ``field`` (and whatever else changed meanwhile): the whole form. */
export async function saveField(field) {
    const form = accountForm(field);
    if (!form) {
        return;
    }
    remember(form);
    const q = queue(form);
    q.pending.add(field);
    if (q.busy) {
        return; // sent right after the save in flight
    }
    q.busy = true;
    try {
        while (q.pending.size) {
            const fields = [...q.pending];
            q.pending.clear();
            await send(form, fields);
        }
    } finally {
        q.busy = false;
    }
}

async function send(form, fields) {
    const data = Object.fromEntries(new FormData(form).entries());
    if (fields.some((field) => field.name === "country_id")) {
        // The province list is reloaded for the new country (core JS).
        data.state_id = "";
    }
    const sent = new Map(fields.map((field) => [field, field.value]));
    for (const field of fields) {
        setState(field, "saving");
    }
    let result;
    try {
        result = await scFetch(form.dataset.submitUrl || form.action, { method: "POST", data });
    } catch {
        // scFetch toasts network / server errors.
        for (const field of fields) {
            setState(field, "error");
            lastSaved.set(field, null);
        }
        return;
    }
    if (result && result.redirectUrl) {
        for (const [field, value] of sent) {
            lastSaved.set(field, value);
            setState(field, field.value === value ? "saved" : "");
        }
        if ("state_id" in data && form.elements.state_id) {
            lastSaved.set(form.elements.state_id, data.state_id);
        }
        flag(form, []);
        for (const card of cards(form)) {
            showErrors(card, []);
        }
        const keys = [...form.querySelectorAll("[data-sc-fragment]")].map((n) => n.dataset.scFragment);
        if (keys.length) {
            requestRefresh(keys, { immediate: true });
        }
        form.dataset.scAccountSaved = String(Date.now());
        return;
    }
    const invalid = (result && result.invalid_fields) || [];
    const messages = (result && result.messages) || [];
    flag(form, invalid);
    for (const field of fields) {
        setState(field, "error");
        // Not saved: any next change (even back to the old value) saves.
        lastSaved.set(field, null);
    }
    // The messages in the card(s) of the changed field(s) and of every
    // flagged field.
    const concerned = new Set(fields.map(cardOf));
    for (const name of invalid) {
        const node = form.elements[name];
        if (node && node.closest) {
            concerned.add(cardOf(node));
        }
    }
    for (const card of cards(form)) {
        showErrors(card, concerned.has(card) ? messages : []);
    }
}

function changed(field) {
    const form = accountForm(field);
    if (form) {
        remember(form);
    }
    return lastSaved.get(field) !== field.value;
}

// The values the page was rendered with = the saved ones.
function init() {
    for (const form of document.querySelectorAll(".o_sc_app form[data-sc-account-form]")) {
        remember(form);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}

// A text field saves on blur (« change »), a select when picked.
document.addEventListener("change", (ev) => {
    const field = accountField(ev.target);
    if (field && changed(field)) {
        saveField(field);
    }
});

// Typing again: the last state no longer applies.
document.addEventListener("input", (ev) => {
    const field = accountField(ev.target);
    if (field && field.tagName !== "SELECT") {
        setState(field, "");
    }
});

// Enter in a field saves it (never a page submit).
document.addEventListener("submit", (ev) => {
    const form = accountForm(ev.target);
    if (!form) {
        return;
    }
    ev.preventDefault();
    const field = accountField(document.activeElement);
    if (field && changed(field)) {
        saveField(field);
    }
});
