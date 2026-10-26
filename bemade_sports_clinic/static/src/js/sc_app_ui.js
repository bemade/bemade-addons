/*
 * Task 1542 (epic #1535) — app shell page behaviours (progressive
 * enhancement; inert outside .o_sc_app):
 *
 * - segmented page tabs (data-sc-tabs): switch panels in place, keep ?tab=
 *   in the address bar; without JS each tab is a plain link;
 * - sheets: [data-sc-sheet-open="<dialog id>"] opens the <dialog>, lazy body
 *   (data-sc-lazy-url) fetched once through sc_fetch — on EVERY open with
 *   data-sc-lazy-fresh (the histories, task 1581); a [data-sc-sheet-refetch]
 *   link inside a sheet reloads its body from its href (filter chips);
 * - lazy rows: <details data-sc-lazy-url> fetch their body on first open;
 * - the status toast (sc_fetch errors, offline / back online; task 1583:
 *   the pending session notification of a POST round-trip, on load);
 * - the device draft store: foreign drafts purged on load, every draft
 *   cleared on « Déconnexion »;
 * - task 1539: the toast may carry ONE action (« Annuler » after an instant
 *   status save: ``sc:toast`` event, detail {message, actionLabel, action});
 *   [data-sc-draft-clear="<key prefix>"] drops those drafts on load (the
 *   landing page of a created injury / added note); a legacy #fragment
 *   (#notes, #contacts… from the POST round-trips) opens the matching tab
 *   (data-sc-tab or one of data-sc-tab-aliases);
 * - task 1620: a sheet marked data-sc-sheet-open-on-load opens on load.
 */
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { focusFirstField } from "@bemade_sports_clinic/js/sc_focus";
import { scSetDisplay } from "@bemade_sports_clinic/js/sc_contact_href";
import { anchorEdited } from "@bemade_sports_clinic/js/sc_edit_anchor";
import {
    clearAllDrafts,
    purgeForeignDrafts,
    removeDraftsWithPrefix,
} from "@bemade_sports_clinic/js/sc_draft_store";

// Task 1676: the pencil ↔ ✓ swap (setToggleDone). Declared up here: the
// load-time handlers below (e.g. offerUndoCreatePlayer) already open cards.
const SC_CHECK_PATH = "M20 6L9 17l-5-5";
const scPencils = new WeakMap();

function app() {
    return document.querySelector(".o_sc_app[data-sc-app-shell]");
}

// ---------------------------------------------------------------- toast
let toastTimer = null;
// Owner review 2026-10-22: a toast shown while a modal popup is open (the
// medical popup's « Details cleared · Undo ») goes INTO that popup — the
// page behind a modal <dialog> is inert, its « Undo » could not be tapped.
// It goes back to its place when the popup closes (and stays visible).
let toastHome = null;
function placeToast(root, toast) {
    if (!toastHome && !toast.closest("dialog")) {
        toastHome = toast.parentElement;
    }
    const modal = [...root.querySelectorAll("dialog[open]")].pop();
    if (modal && toast.parentElement !== modal) {
        modal.appendChild(toast);
    } else if (!modal && toastHome && toast.parentElement !== toastHome) {
        toastHome.appendChild(toast);
    }
}
document.addEventListener(
    "close",
    (ev) => {
        const toast = ev.target instanceof HTMLDialogElement && ev.target.querySelector(":scope > .o_sc_toast");
        if (toast && toastHome) {
            toastHome.appendChild(toast);
        }
    },
    true
);

function showToast(message, actionLabel, action, duration, options) {
    const root = app();
    const toast = root && root.querySelector(".o_sc_toast");
    if (!toast) {
        return;
    }
    placeToast(root, toast);
    const { title, tone } = options || {};
    // Task 1678: the title sits above the text (one column), the action
    // button beside that column — under it, right-aligned, on a phone or
    // when it does not fit (sc_p2.scss, review round 1).
    const body = document.createElement("span");
    body.className = "o_sc_toast_body";
    if (title) {
        const strong = document.createElement("strong");
        strong.className = "o_sc_toast_title";
        strong.textContent = title;
        body.appendChild(strong);
    }
    const text = document.createElement("span");
    text.className = "o_sc_toast_text";
    text.textContent = message;
    body.appendChild(text);
    const parts = [body];
    if (tone) {
        toast.dataset.scToastTone = tone;
    } else {
        delete toast.dataset.scToastTone;
    }
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
    }, duration || (actionLabel ? 8000 : 4000));
}

// Task 1679: a card the toast is about keeps its bottom (its buttons) above
// the toast (fixed over the page): the page scrolls up by the overlap, with
// room made under the page when it is already at its end (removed with the
// toast). Call it once the card's own scroll is done (an instant one: a
// smooth scroll still running would end where it was heading). ``fitOnly``:
// only when the whole card fits above the toast (a tall card being edited
// keeps its top in view).
function keepClearOfToast(el, { fitOnly = false } = {}) {
    const root = app();
    const toast = root && root.querySelector(".o_sc_toast");
    if (!el || !toast || toast.hidden) {
        return;
    }
    const gap = 8;
    const toastTop = toast.getBoundingClientRect().top;
    const rect = el.getBoundingClientRect();
    const overlap = rect.bottom - (toastTop - gap);
    if (overlap <= 0 || (fitOnly && rect.height > toastTop - gap)) {
        return;
    }
    const scroller = document.scrollingElement || document.documentElement;
    const room = window.scrollY + overlap - (scroller.scrollHeight - window.innerHeight);
    if (room > 0 && !document.body.dataset.scToastRoom) {
        document.body.dataset.scToastRoom = "1";
        document.body.style.paddingBottom = `${Math.ceil(room)}px`;
        const observer = new MutationObserver(() => {
            if (toast.hidden) {
                observer.disconnect();
                delete document.body.dataset.scToastRoom;
                document.body.style.paddingBottom = "";
            }
        });
        observer.observe(toast, { attributes: true, attributeFilter: ["hidden"] });
    }
    window.scrollBy({ top: overlap, behavior: "instant" });
}

document.addEventListener("sc:toast", (ev) => {
    const detail = ev.detail || {};
    showToast(detail.message || "", detail.actionLabel, detail.action, detail.duration,
        { title: detail.title, tone: detail.tone });
});

// Task 1583: the pending session notification of a POST round-trip
// (« Add to Team »…), rendered on the toast host by sc_app_layout — shown
// once on load, whatever the page. Errors stay longer.
function showSessionNotification() {
    const root = app();
    const toast = root && root.querySelector(".o_sc_toast[data-sc-notify]");
    if (!toast) {
        return;
    }
    const message = toast.dataset.scNotify;
    const tone = toast.dataset.scNotifyTone || "success";
    const title = toast.dataset.scNotifyTitle || "";
    delete toast.dataset.scNotify;
    delete toast.dataset.scNotifyTitle;
    delete toast.dataset.scNotifyTone;
    showToast(message, null, null, tone === "error" ? 10000 : 6000, { title, tone });
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showSessionNotification);
} else {
    showSessionNotification();
}

// A save updates the page in place (owner review 2026-10-10): the read views
// of inline-edit cards ([data-sc-display="model:id:field"]) at once; a
// tap-to-call / tap-to-email link's href follows (task 1585). Task 1611:
// everything else the save touches (titles, hero, chips, lists…) refreshes as
// read fragments (sc_fragments.js) — the former ad-hoc « heading » / « stage »
// payloads are gone.
document.addEventListener("sc:saved", (ev) => {
    const { model, recordId, field, result } = ev.detail || {};
    if (!result) {
        return;
    }
    // Task 1594: a holder flagged data-sc-display-hide-empty (the hero's
    // « Actual return » chip) shows only while its value is set.
    const show = (el, display) => {
        scSetDisplay(el, display);
        const holder = el.closest("[data-sc-display-hide-empty]");
        if (holder) {
            holder.hidden = !display;
        }
    };
    if (result.display !== undefined) {
        for (const el of document.querySelectorAll(`[data-sc-display="${model}:${recordId}:${field}"]`)) {
            show(el, result.display);
        }
    }
    for (const [name, shown] of Object.entries(result.also || {})) {
        for (const el of document.querySelectorAll(`[data-sc-display="${model}:${recordId}:${name}"]`)) {
            show(el, shown.display);
        }
    }
});

// A just-created injury (inline « Add Injury », owner decision 2026-10-11):
// « Injury created · Undo » for the undo window (the server enforces it
// too), and the address loses ?created= so a reload opens the injury
// without offering the undo again.
const SC_UNDO_CREATE_MS = 2 * 60 * 1000;
function offerUndoCreate() {
    const card = document.querySelector(".o_sc_app [data-sc-created-injury]");
    const form = card && card.querySelector('form[data-sc-form="injury.undo"]');
    if (!form) {
        return;
    }
    showToast(form.dataset.scToastMessage, form.dataset.scToastAction, () => form.submit(), SC_UNDO_CREATE_MS);
    const url = new URL(window.location.href);
    if (url.searchParams.has("created")) {
        url.searchParams.set("injury", url.searchParams.get("created"));
        url.searchParams.delete("created");
        window.history.replaceState(window.history.state, "", url.toString());
    }
    // Task 1679: instant, then lifted above the toast when it fits.
    card.scrollIntoView({ block: "start", behavior: "instant" });
    keepClearOfToast(card, { fitOnly: true });
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", offerUndoCreate);
} else {
    offerUndoCreate();
}

// Task 1663: a team announcement just archived — « Announcement archived ·
// Undo » for the pills' undo time (~8 s; the server re-checks its window);
// the address loses ?announcement_archived= so a reload does not offer it.
function offerUndoAnnouncement() {
    const form = document.querySelector('.o_sc_app form[data-sc-form="announcement.undo"]');
    if (form) {
        showToast(form.dataset.scToastMessage, form.dataset.scToastAction, () => form.submit(), 8000);
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("announcement_archived")) {
        url.searchParams.delete("announcement_archived");
        window.history.replaceState(window.history.state, "", url.toString());
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", offerUndoAnnouncement);
} else {
    offerUndoAnnouncement();
}

// Task 1656: a toast kept for this page by the previous one (it was left
// after its viewer lost access to it: sc_confirm.js scLeavePage).
function showPendingToast() {
    let message = null;
    try {
        message = window.sessionStorage.getItem("sc_pending_toast:v1");
        window.sessionStorage.removeItem("sc_pending_toast:v1");
    } catch {
        return;
    }
    if (message && app()) {
        showToast(message);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showPendingToast);
} else {
    showPendingToast();
}

// Task 1655: a player just created inline — the identity card opens in edit
// and « Player created · Undo » is offered for the undo window; the address
// loses ?created_player= so a reload offers neither again.
function offerUndoCreatePlayer() {
    const form = document.querySelector('.o_sc_app form[data-sc-form="player.undo"]');
    if (form) {
        showToast(form.dataset.scToastMessage, form.dataset.scToastAction, () => form.submit(), SC_UNDO_CREATE_MS);
    }
    for (const card of document.querySelectorAll(".o_sc_app [data-sc-edit-card][data-sc-edit-open-on-load]")) {
        setCardEditing(card, true);
        card.scrollIntoView({ block: "start" });
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("created_player")) {
        url.searchParams.delete("created_player");
        window.history.replaceState(window.history.state, "", url.toString());
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", offerUndoCreatePlayer);
} else {
    offerUndoCreatePlayer();
}

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

// Task 1676: while its card is in edit mode the head pencil is a ✓
// (« Finish editing ») that closes the card — the same close path as
// « Done » (refresh, #1642 anchoring), whether or not the user shows the
// « Done » buttons (Paramètres).
function setToggleDone(toggle, editing) {
    const svg = toggle.querySelector("svg");
    if (editing) {
        if (!scPencils.has(toggle)) {
            scPencils.set(toggle, {
                icon: svg ? svg.innerHTML : null,
                label: toggle.getAttribute("aria-label"),
                title: toggle.getAttribute("title"),
            });
        }
        if (svg) {
            svg.innerHTML = `<path d="${SC_CHECK_PATH}"/>`;
        }
        // The label comes translated from the layout (a card may open on
        // load, before the JS translations are there).
        const root = app();
        const label = (root && root.dataset.scEditDoneLabel) || "✓";
        toggle.setAttribute("aria-label", label);
        toggle.setAttribute("title", label);
        toggle.classList.add("o_sc_edit_toggle_done");
        toggle.dataset.scEditToggleDone = "1";
        return;
    }
    const saved = scPencils.get(toggle);
    if (saved) {
        if (svg && saved.icon !== null) {
            svg.innerHTML = saved.icon;
        }
        for (const [attr, value] of [["aria-label", saved.label], ["title", saved.title]]) {
            if (value === null) {
                toggle.removeAttribute(attr);
            } else {
                toggle.setAttribute(attr, value);
            }
        }
    }
    toggle.classList.remove("o_sc_edit_toggle_done");
    delete toggle.dataset.scEditToggleDone;
}

// Inline-edit cards: ONE pencil per card toggles its edit view; « Done »
// closes it and (task 1611) refreshes the read fragments at once — no reload.
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
        setToggleDone(toggle, editing);
    }
    if (editing) {
        // Task 1646: a text field only (never a picker), nothing on a phone.
        focusFirstField(edit);
    }
}

document.addEventListener("sc:edit-open", (ev) => {
    const card = ev.target.closest && ev.target.closest("[data-sc-edit-card]");
    if (card && !card.dataset.scEditOpen) {
        setCardEditing(card, true);
    }
});

document.addEventListener("click", (ev) => {
    const toggle = ev.target.closest && ev.target.closest("[data-sc-edit-toggle]");
    const done = !toggle && ev.target.closest && ev.target.closest("[data-sc-edit-done]");
    const card = (toggle || done) && (toggle || done).closest("[data-sc-edit-card]");
    if (!card) {
        return;
    }
    ev.preventDefault();
    if (toggle) {
        const closing = Boolean(card.dataset.scEditOpen);
        setCardEditing(card, !closing);
        if (closing) {
            // Task 1676: the ✓ closes like « Done » — focus out of the card,
            // read fragments refreshed, back to the block's top (#1642).
            if (card.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            document.dispatchEvent(new CustomEvent("sc:refresh-now"));
            anchorEdited(card);
        }
        return;
    }
    setCardEditing(card, false);
    // The hidden « Done » would keep the focus inside the card (a busy card
    // is never re-ordered or dropped by a list refresh).
    if (done && done.contains(document.activeElement)) {
        document.activeElement.blur();
    }
    document.dispatchEvent(new CustomEvent("sc:refresh-now"));
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

// Task 1643 addendum: a neutralized test DB's banner (#oe_neutralize_banner)
// is pinned at the bottom on a phone (sc_tokens.scss); the tabs rise by its
// height. No banner (prod) = 0.
function measureRibbon() {
    const banner = document.getElementById("oe_neutralize_banner");
    if (!banner || !app()) {
        return;
    }
    const update = () => {
        const fixed = getComputedStyle(banner).position === "fixed";
        document.documentElement.style.setProperty(
            "--sc-ribbon-h",
            fixed ? `${banner.getBoundingClientRect().height}px` : "0px"
        );
    };
    update();
    if (window.ResizeObserver) {
        new ResizeObserver(update).observe(banner);
    }
    window.addEventListener("resize", update);
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", measureRibbon);
} else {
    measureRibbon();
}

// ------------------------------------------------------------ lazy load
async function loadLazy(container, url, target) {
    if (!url || container.dataset.scLoaded === "1") {
        return;
    }
    container.dataset.scLoaded = "1";
    try {
        const html = await scFetch(url, { as: "html" });
        target.innerHTML = html;
        // Task 1640: listeners may enhance the injected body (date bounds).
        target.dispatchEvent(new CustomEvent("sc:lazy-loaded", { bubbles: true }));
        // A fragment with its own empty state (task 1581 histories) keeps it.
        // Task 1614: [data-sc-lazy-filled] = content even without a link
        // (a digest day whose players have no page link).
        if (!target.querySelector("li, a, tr, .o_sc_empty, [data-sc-lazy-filled]")) {
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

// Task 1593: a player row's « Details » control ([data-sc-row-expand] =
// the id of the detail region under the row) shows / hides that region and
// fetches its body on first open. A button, not a <details>: the row's main
// link stays one stretched link and the detail spans the row's full width.
document.addEventListener("click", (ev) => {
    const toggle = ev.target.closest && ev.target.closest("[data-sc-row-expand]");
    if (!toggle || !toggle.closest(".o_sc_app")) {
        return;
    }
    const region = document.getElementById(toggle.dataset.scRowExpand);
    if (!region) {
        return;
    }
    ev.preventDefault();
    const open = region.hidden;
    region.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.closest(".o_sc_player_row")?.classList.toggle("o_sc_row_open", open);
    if (open && region.dataset.scLazyUrl) {
        loadLazy(region, region.dataset.scLazyUrl, region.querySelector(".o_sc_lazy_body"));
    }
});

// Task 1634: a player card's face is a read fragment (a status pick swaps
// it): its fresh « Details » control follows the region it controls, which
// stays open or closed under the card.
document.addEventListener("sc:fragments", () => {
    for (const toggle of document.querySelectorAll(".o_sc_app [data-sc-row-expand]")) {
        const region = document.getElementById(toggle.dataset.scRowExpand);
        if (region) {
            toggle.setAttribute("aria-expanded", region.hidden ? "false" : "true");
        }
    }
});

// --------------------------------------------------------------- sheets
function refetchSheet(dialog, url) {
    const body = dialog.querySelector(".o_sc_sheet_body");
    dialog.dataset.scLoaded = "0";
    const loading = document.createElement("p");
    loading.className = "o_sc_empty o_sc_lazy_loading";
    loading.textContent = _t("Loading…");
    body.replaceChildren(loading);
    return loadLazy(dialog, url, body);
}

function openSheet(id) {
    const dialog = document.getElementById(id);
    if (!dialog || typeof dialog.showModal !== "function") {
        return;
    }
    if (!dialog.open) {
        dialog.showModal();
    }
    if (dialog.dataset.scLazyUrl) {
        if (dialog.dataset.scLazyFresh === "1") {
            // A history that can change on this page: fetched on every open
            // (task 1581: every history of the shell).
            refetchSheet(dialog, dialog.dataset.scLazyUrl);
            return;
        }
        loadLazy(dialog, dialog.dataset.scLazyUrl, dialog.querySelector(".o_sc_sheet_body"));
    }
}

// Task 1665: « Add My Timesheet » when I already have an editable timesheet
// on this event — open THAT card in edit (scrolled to), and a toast offers
// « Add another timesheet » (the add sheet, split shifts). The sheet's own
// « Edit my timesheet » does the same from inside it.
function editExistingTimesheet(id, behavior) {
    const card = document.querySelector(`.o_sc_app [data-sc-timesheet-id="${id}"][data-sc-edit-card]`);
    if (!card) {
        return false;
    }
    setCardEditing(card, true);
    card.scrollIntoView({ block: "center", behavior: behavior || "auto" });
    return card;
}
document.addEventListener("click", (ev) => {
    const root = app();
    if (!root || !root.contains(ev.target)) {
        return;
    }
    const add = ev.target.closest('[data-sc-action="timesheet.add"][data-sc-sheet-open]');
    const edit = !add && ev.target.closest("[data-sc-ts-edit]");
    if (!add && !edit) {
        return;
    }
    const holder = root.querySelector("[data-sc-ts-existing-id]");
    const id = edit ? edit.dataset.scTsEdit : holder && holder.dataset.scTsExistingId;
    if (!id) {
        return;
    }
    const dialog = edit && edit.closest("dialog");
    // Task 1679: an instant scroll when the toast follows (it then lifts
    // the card above itself).
    const card = editExistingTimesheet(id, add ? "instant" : undefined);
    if (!card) {
        return; // no card on this page: let the sheet open as usual
    }
    ev.preventDefault();
    ev.stopImmediatePropagation();
    if (dialog) {
        dialog.close();
    }
    if (add) {
        showToast(_t("You already have a timesheet for this event."), _t("Add another timesheet"),
            () => openSheet(add.dataset.scSheetOpen || "sc_ts_add_sheet"));
        // Task 1679: its « Delete » / « Done » never sit under the toast.
        keepClearOfToast(card);
    }
}, true);

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
    // Task 1581: filters INSIDE a lazy sheet (the injury notes' scope
    // chips) re-fetch its body from their href, the sheet stays open.
    const refetch = ev.target.closest("dialog.o_sc_sheet [data-sc-sheet-refetch]");
    if (refetch && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey) {
        ev.preventDefault();
        refetchSheet(refetch.closest("dialog"), refetch.getAttribute("href"));
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
    // Task 1620: a sheet the server answered an error in (« Supprimer le
    // compte » with a wrong password) opens again on load.
    const reopen = root.querySelector("dialog.o_sc_sheet[data-sc-sheet-open-on-load]");
    if (reopen) {
        openSheet(reopen.id);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
