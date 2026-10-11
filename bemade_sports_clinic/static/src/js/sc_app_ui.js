/*
 * Task 1542 (epic #1535) — app shell page behaviours (progressive
 * enhancement; inert outside .o_sc_app):
 *
 * - segmented page tabs (data-sc-tabs): switch panels in place, keep ?tab=
 *   in the address bar; without JS each tab is a plain link;
 * - sheets: [data-sc-sheet-open="<dialog id>"] opens the <dialog>, lazy body
 *   (data-sc-lazy-url) fetched once through sc_fetch;
 * - lazy rows: <details data-sc-lazy-url> fetch their body on first open;
 * - the status toast (sc_fetch errors, offline / back online);
 * - the device draft store: foreign drafts purged on load, every draft
 *   cleared on « Déconnexion »;
 * - task 1539: the toast may carry ONE action (« Annuler » after an instant
 *   status save: ``sc:toast`` event, detail {message, actionLabel, action});
 *   [data-sc-draft-clear="<key prefix>"] drops those drafts on load (the
 *   landing page of a created injury / added note); a legacy #fragment
 *   (#notes, #contacts… from the POST round-trips) opens the matching tab
 *   (data-sc-tab or one of data-sc-tab-aliases).
 */
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import {
    clearAllDrafts,
    purgeForeignDrafts,
    removeDraftsWithPrefix,
} from "@bemade_sports_clinic/js/sc_draft_store";

function app() {
    return document.querySelector(".o_sc_app[data-sc-app-shell]");
}

// ---------------------------------------------------------------- toast
let toastTimer = null;
function showToast(message, actionLabel, action) {
    const root = app();
    const toast = root && root.querySelector(".o_sc_toast");
    if (!toast) {
        return;
    }
    const text = document.createElement("span");
    text.textContent = message;
    const parts = [text];
    if (actionLabel && action) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "o_sc_toast_action";
        button.dataset.scToastAction = "1";
        button.textContent = actionLabel;
        button.addEventListener("click", () => {
            toast.hidden = true;
            action();
        });
        parts.push(button);
    }
    toast.replaceChildren(...parts);
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.hidden = true;
    }, actionLabel ? 8000 : 4000);
}

document.addEventListener("sc:toast", (ev) => {
    const detail = ev.detail || {};
    showToast(detail.message || "", detail.actionLabel, detail.action);
});
// A save updates the page in place (owner review 2026-10-10):
// * the read views of inline-edit cards ([data-sc-display="model:id:field"]);
// * the player's status pill (a status save answers the new stage);
// * the player's heading (an Identity save answers it).
document.addEventListener("sc:saved", (ev) => {
    const { model, recordId, field, result } = ev.detail || {};
    if (!result) {
        return;
    }
    if (result.display !== undefined) {
        for (const el of document.querySelectorAll(`[data-sc-display="${model}:${recordId}:${field}"]`)) {
            el.textContent = result.display || "—";
        }
    }
    const card = ev.target && ev.target.closest && ev.target.closest("[data-sc-edit-card]");
    for (const opened of document.querySelectorAll("[data-sc-edit-card][data-sc-edit-open]")) {
        opened.dataset.scEditChanged = "1";
    }
    if (card) {
        card.dataset.scEditChanged = "1";
    }
    if (model !== "sports.patient") {
        return;
    }
    const stage = result.stage;
    if (stage) {
        for (const chip of document.querySelectorAll(`[data-sc-stage-chip="${recordId}"]`)) {
            chip.className = `o_sc_chip o_sc_chip_${stage.tone || "ghost"}`;
            chip.textContent = stage.label || "";
        }
    }
    const heading = result.heading;
    if (heading) {
        for (const el of document.querySelectorAll("[data-sc-heading]")) {
            const key = el.dataset.scHeading;
            if (key === "title" || key === "list_name") {
                el.textContent = heading[key] || "";
            } else if (key === "position_suffix") {
                el.textContent = heading.position ? ` · ${heading.position}` : "";
            } else if (key === "context") {
                const team = el.dataset.scHeadingTeam || "";
                el.textContent = [team, heading.position].filter(Boolean).join(" · ");
            }
        }
    }
});

// A link to « …#<details id> » opens that inline card (e.g. Overview's
// « Add Injury » → the Injuries tab's card), owner review 2026-10-10.
function openHashedDetails() {
    const id = window.location.hash.slice(1);
    const details = id && /^[\w-]+$/.test(id) && document.getElementById(id);
    if (details && details.tagName === "DETAILS" && details.closest(".o_sc_app")) {
        details.open = true;
        details.scrollIntoView({ block: "start" });
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", openHashedDetails);
} else {
    openHashedDetails();
}
window.addEventListener("hashchange", openHashedDetails);

// Inline-edit cards: ONE pencil per card toggles its edit view; « Done »
// closes it (a card whose read view is server-built reloads after a change).
function setCardEditing(card, editing) {
    const edit = card.querySelector('[data-sc-edit-view="edit"]');
    const read = card.querySelector('[data-sc-edit-view="read"]');
    if (!edit) {
        return;
    }
    edit.hidden = !editing;
    if (read) {
        read.hidden = editing;
    }
    if (editing) {
        card.dataset.scEditOpen = "1";
    } else {
        delete card.dataset.scEditOpen;
    }
    const toggle = card.querySelector("[data-sc-edit-toggle]");
    if (toggle) {
        toggle.setAttribute("aria-expanded", editing ? "true" : "false");
    }
    if (editing) {
        const first = edit.querySelector("input, textarea, select");
        if (first) {
            first.focus({ preventScroll: true });
        }
    }
}

document.addEventListener("click", (ev) => {
    const toggle = ev.target.closest && ev.target.closest("[data-sc-edit-toggle]");
    const done = !toggle && ev.target.closest && ev.target.closest("[data-sc-edit-done]");
    const card = (toggle || done) && (toggle || done).closest("[data-sc-edit-card]");
    if (!card) {
        return;
    }
    ev.preventDefault();
    if (toggle) {
        setCardEditing(card, !card.dataset.scEditOpen);
        return;
    }
    if (card.dataset.scEditReload && card.dataset.scEditChanged) {
        window.location.reload();
        return;
    }
    setCardEditing(card, false);
});
document.addEventListener("sc:fetch-error", (ev) => {
    const error = ev.detail || {};
    if (error.status === 0) {
        showToast(_t("No connection. Try again when you are back online."));
    } else {
        showToast(_t("Something went wrong. Please try again."));
    }
});
window.addEventListener("offline", () => app() && showToast(_t("You are offline.")));
window.addEventListener("online", () => app() && showToast(_t("Back online.")));

// ------------------------------------------------------------ lazy load
async function loadLazy(container, url, target) {
    if (!url || container.dataset.scLoaded === "1") {
        return;
    }
    container.dataset.scLoaded = "1";
    try {
        const html = await scFetch(url, { as: "html" });
        target.innerHTML = html;
        if (!target.querySelector("li, a, tr")) {
            const empty = document.createElement("p");
            empty.className = "o_sc_empty";
            empty.textContent = _t("Nothing to show.");
            target.replaceChildren(empty);
        }
    } catch {
        container.dataset.scLoaded = "0"; // retry on next open
        const failed = document.createElement("p");
        failed.className = "o_sc_empty";
        failed.textContent = _t("Could not load. Close and open again to retry.");
        target.replaceChildren(failed);
    }
}

// <details> « toggle » does not bubble: listen in the capture phase.
document.addEventListener(
    "toggle",
    (ev) => {
        const details = ev.target;
        if (
            details instanceof HTMLDetailsElement &&
            details.open &&
            details.dataset.scLazyUrl &&
            details.closest(".o_sc_app")
        ) {
            loadLazy(details, details.dataset.scLazyUrl, details.querySelector(".o_sc_lazy_body"));
        }
    },
    true
);

// --------------------------------------------------------------- sheets
function openSheet(id) {
    const dialog = document.getElementById(id);
    if (!dialog || typeof dialog.showModal !== "function") {
        return;
    }
    if (!dialog.open) {
        dialog.showModal();
    }
    if (dialog.dataset.scLazyUrl) {
        loadLazy(dialog, dialog.dataset.scLazyUrl, dialog.querySelector(".o_sc_sheet_body"));
    }
}

document.addEventListener("click", (ev) => {
    const root = app();
    if (!root || !root.contains(ev.target)) {
        return;
    }
    const opener = ev.target.closest("[data-sc-sheet-open]");
    if (opener) {
        ev.preventDefault();
        openSheet(opener.dataset.scSheetOpen);
        return;
    }
    const closer = ev.target.closest("[data-sc-sheet-close]");
    if (closer) {
        const dialog = closer.closest("dialog");
        if (dialog) {
            dialog.close();
        }
        return;
    }
    // A click on the backdrop lands on the <dialog> itself.
    if (ev.target instanceof HTMLDialogElement && ev.target.classList.contains("o_sc_sheet")) {
        const rect = ev.target.getBoundingClientRect();
        const inside =
            ev.clientX >= rect.left && ev.clientX <= rect.right &&
            ev.clientY >= rect.top && ev.clientY <= rect.bottom;
        if (!inside) {
            ev.target.close();
        }
        return;
    }
    // Segmented page tabs.
    const tab = ev.target.closest("[data-sc-tabs] a[data-sc-tab]");
    if (tab && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey) {
        const key = tab.dataset.scTab;
        const panel = root.querySelector(`[data-sc-tab-panel="${key}"]`);
        if (!panel) {
            return; // let the link load the page
        }
        ev.preventDefault();
        for (const other of tab.parentElement.querySelectorAll("a[data-sc-tab]")) {
            const on = other === tab;
            other.setAttribute("aria-selected", on ? "true" : "false");
            other.setAttribute("aria-pressed", on ? "true" : "false");
        }
        for (const pane of root.querySelectorAll("[data-sc-tab-panel]")) {
            pane.hidden = pane !== panel;
        }
        try {
            window.history.replaceState(window.history.state, "", tab.href);
        } catch {
            // ignore
        }
        return;
    }
    // « Déconnexion »: nothing typed stays on the device.
    const logout = ev.target.closest('a[href^="/web/session/logout"]');
    if (logout) {
        clearAllDrafts();
    }
});

// ------------------------------------------------------------ bootstrap
function activateTab(root, key) {
    const tab = root.querySelector(
        `[data-sc-tabs] a[data-sc-tab="${key}"], [data-sc-tabs] a[data-sc-tab-aliases~="${key}"]`
    );
    const panel = tab && root.querySelector(`[data-sc-tab-panel="${tab.dataset.scTab}"]`);
    if (!panel) {
        return;
    }
    for (const other of tab.parentElement.querySelectorAll("a[data-sc-tab]")) {
        const on = other === tab;
        other.setAttribute("aria-selected", on ? "true" : "false");
        other.setAttribute("aria-pressed", on ? "true" : "false");
    }
    for (const pane of root.querySelectorAll("[data-sc-tab-panel]")) {
        pane.hidden = pane !== panel;
    }
}

function init() {
    const root = app();
    if (!root) {
        return;
    }
    purgeForeignDrafts();
    for (const marker of root.querySelectorAll("[data-sc-draft-clear]")) {
        removeDraftsWithPrefix(marker.dataset.scDraftClear);
    }
    const hash = (window.location.hash || "").slice(1).split("?")[0];
    if (hash && /^[\w-]+$/.test(hash)) {
        activateTab(root, hash);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
