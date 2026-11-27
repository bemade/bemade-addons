/*
 * Task 5199 (P4a) — the screen refresh (read fragments), moved from the
 * first consumer (task 1611). What shows on screen follows an in-place save,
 * without a reload. Inert outside the shell root .o_pk_app[data-pk-app-shell].
 *
 * Server side (bemade_portal_kit/tools/fragments.py): a READ-ONLY region of
 * an app page carries data-pk-fragment="<model>:<id>:<part>"; a save answers
 * ``refresh`` — key patterns (``*`` = within one key segment) from its save
 * spec. This module:
 *
 * - on « pk:saved » {detail: {result}}, collects the patterns, waits ~300 ms
 *   (one fetch for a burst of saves), matches them against the keys the page
 *   carries and GETs the page's OWN URL with « X-Pk-Fragments: k1,k2 » — the
 *   route renders as for a reload and answers {fragments: {key: html},
 *   missing, title};
 * - a node with data-pk-fragment-keep is never emptied when its key is
 *   missing from the fresh render (it stays put until the next visit);
 * - swaps each node in place, NEVER one that holds an OWL island
 *   (owl-component), the focused element or an open dialog: such a key is
 *   kept « stale » and retried once the element lets go (focus out,
 *   « pk:refresh-now »); a <select> keeps its element and its value (options
 *   refreshed); a key missing from the fresh render empties and hides its
 *   node;
 * - data-pk-fragment-keep-empty on a list: it carries its own empty state,
 *   so it stays shown without items;
 * - data-pk-fragment-mode="list": the container's live items
 *   (data-pk-fragment-item) are KEPT — their islands survive — and only
 *   re-ordered / dropped / regrouped as in the fresh render (an item may move
 *   between the list's sub-lists; a details[data-pk-keep-open] keeps its open
 *   state); while an item is being edited (or holds the focus) the list
 *   waits;
 * - « pk:refresh-now »: what is queued (and what waited) goes at once;
 * - back / forward: the shell root carries its server render time
 *   (data-pk-rendered-at); a save stores its server time (``saved_at``) in
 *   sessionStorage (pk_dirty_at:v1; the old sc_dirty_at:v1 stamp is read once
 *   and moved); a page shown again from the back / forward cache (or the HTTP
 *   cache) reloads only when something was saved after it was rendered;
 *   a POST form of the shell marks the session dirty too, unless it carries
 *   data-pk-no-dirty (e.g. a preferences form).
 *
 * Consumer markers (registerRefreshMarkers): selectors of a list item being
 * edited (``editing``: its list waits) and of a node whose hidden state a
 * swap keeps (``keepsHidden``: e.g. an edit card's read view while the card
 * is open).
 *
 * API: requestRefresh(patterns, {immediate}), flushFragments(),
 * applyFragments(payload), matchFragmentKeys(patterns), markDirty(at),
 * pageIsStale(), serverNow(); or the DOM event « pk:refresh » {detail:
 * {patterns, immediate}}. After a swap the document receives « pk:fragments »
 * {detail: {keys}}.
 */
import { _t } from "@web/core/l10n/translation";
import { pkFetch } from "@bemade_portal_kit/js/pk_fetch";
import { pkLeavePage } from "@bemade_portal_kit/js/pk_confirm";
import { NAV_BF_RELOAD_KEY } from "@bemade_portal_kit/js/pk_app_nav";

export const FRAGMENTS_HEADER = "X-Pk-Fragments";
const DEBOUNCE_MS = 300;
export const DIRTY_KEY = "pk_dirty_at:v1";
// The stamp stored before task 5199: read once, then moved under DIRTY_KEY.
const OLD_DIRTY_KEY = "sc_dirty_at:v1";
const MAX_KEYS = 200;
// Client clock when this page was parsed (server time ≈ rendered-at + elapsed).
const LOADED_AT = Date.now();

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

function escapeRe(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** A key pattern (``*`` = any one segment part) as a RegExp. */
export function patternToRegExp(pattern) {
    const segments = String(pattern)
        .split(":")
        .map((segment) => segment.split("*").map(escapeRe).join("[^:]*"));
    return new RegExp(`^${segments.join(":")}$`);
}

/** The fragment keys on the page that match one of ``patterns``. */
export function matchFragmentKeys(patterns, root = document) {
    const regs = (patterns || []).map(patternToRegExp);
    const keys = [];
    if (!regs.length) {
        return keys;
    }
    for (const el of root.querySelectorAll("[data-pk-fragment]")) {
        const key = el.dataset.pkFragment;
        if (key && !keys.includes(key) && regs.some((re) => re.test(key))) {
            keys.push(key);
        }
    }
    return keys;
}

function nodesFor(key) {
    return [...document.querySelectorAll("[data-pk-fragment]")].filter(
        (el) => el.dataset.pkFragment === key
    );
}

function holdsFocus(el) {
    const active = document.activeElement;
    return Boolean(active && active !== document.body && el.contains(active));
}

/** May this node be replaced right now? */
function isBusy(el) {
    return (
        holdsFocus(el) ||
        el.matches("owl-component, dialog[open]") ||
        Boolean(el.querySelector("owl-component, dialog[open]"))
    );
}

function parse(html) {
    const template = document.createElement("template");
    template.innerHTML = String(html || "").trim();
    return template.content.firstElementChild;
}

// -------------------------------------------------------------- markers
const markers = { editing: [], keepsHidden: [] };

/**
 * A consumer's own markers: ``editing`` = selectors of a list item being
 * edited (its list waits until it is not); ``keepsHidden`` = selectors of a
 * node whose hidden state a swap keeps.
 */
export function registerRefreshMarkers({ editing = [], keepsHidden = [] } = {}) {
    for (const selector of editing) {
        if (!markers.editing.includes(selector)) {
            markers.editing.push(selector);
        }
    }
    for (const selector of keepsHidden) {
        if (!markers.keepsHidden.includes(selector)) {
            markers.keepsHidden.push(selector);
        }
    }
}

// ------------------------------------------------------------- swapping
const stale = new Set();

function swapSelect(el, fresh) {
    const value = el.value;
    el.replaceChildren(...fresh.childNodes);
    if ([...el.options].some((option) => option.value === value)) {
        el.value = value;
    }
}

function swapNode(el, fresh, key) {
    if (isBusy(el)) {
        stale.add(key);
        return false;
    }
    if (fresh.matches("owl-component") || fresh.querySelector("owl-component")) {
        // A fragment must never hold an island (it could not be mounted).
        return false;
    }
    if (el.tagName === "SELECT" && fresh.tagName === "SELECT") {
        swapSelect(el, fresh);
        return true;
    }
    if (markers.keepsHidden.some((selector) => el.matches(selector))) {
        // E.g. an edit card open on its edit view: the read view stays hidden.
        fresh.hidden = el.hidden;
    }
    el.replaceWith(fresh);
    return true;
}

function emptyNode(el, key) {
    if (isBusy(el)) {
        stale.add(key);
        return;
    }
    el.replaceChildren();
    el.hidden = true;
}

/** A list's structure: its items' keys in place, everything else as text
 * (group headings…) — equal means nothing to move. */
function itemSignature(node) {
    const parts = [];
    for (const child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
            const text = child.textContent.trim();
            if (text) {
                parts.push(text);
            }
        } else if (child.nodeType === Node.ELEMENT_NODE) {
            if (child.dataset.pkFragmentItem) {
                parts.push(`[${child.dataset.pkFragmentItem}]`);
            } else {
                parts.push(`<${child.tagName}>${itemSignature(child)}</>`);
            }
        }
    }
    return parts.join("|");
}

function itemBusy(item) {
    return (
        holdsFocus(item) ||
        markers.editing.some((selector) => item.matches(selector)) ||
        Boolean(item.querySelector("dialog[open]"))
    );
}

/**
 * A list fragment: keep the live items, take the fresh order / grouping;
 * drop the items gone from the fresh render (unless being edited).
 */
function reconcileList(live, fresh, key) {
    if (itemSignature(live) === itemSignature(fresh)) {
        return false;
    }
    const liveItems = new Map();
    for (const item of live.querySelectorAll("[data-pk-fragment-item]")) {
        liveItems.set(item.dataset.pkFragmentItem, item);
    }
    // An item being edited (or holding the focus) never moves or goes under
    // the user's hands: the new order waits for « Done » / focus out.
    if ([...liveItems.values()].some(itemBusy)) {
        stale.add(key);
        return false;
    }
    // A fold-out of the list (details[data-pk-keep-open]) stays as the user
    // left it.
    for (const fold of live.querySelectorAll("details[data-pk-keep-open]")) {
        const twin = [...fresh.querySelectorAll("details[data-pk-keep-open]")].find(
            (el) => el.dataset.pkKeepOpen === fold.dataset.pkKeepOpen
        );
        if (twin) {
            twin.open = fold.open;
        }
    }
    const active = document.activeElement;
    for (const slot of [...fresh.querySelectorAll("[data-pk-fragment-item]")]) {
        const existing = liveItems.get(slot.dataset.pkFragmentItem);
        if (existing) {
            slot.replaceWith(existing);
        } else if (slot.querySelector("owl-component")) {
            // A new item with islands cannot be mounted here: the next visit
            // of the page shows it (the « back » check reloads).
            slot.remove();
        }
    }
    live.replaceChildren(...fresh.childNodes);
    live.hidden = false;
    if (active && active !== document.body && active.isConnected && document.activeElement !== active) {
        active.focus({ preventScroll: true });
    }
    return true;
}

/** Apply a fragment answer ({fragments, missing, title}) to the page. */
export function applyFragments(payload) {
    const fragments = (payload && payload.fragments) || {};
    const swapped = [];
    const lists = [];
    for (const [key, html] of Object.entries(fragments)) {
        for (const el of nodesFor(key)) {
            const fresh = parse(html);
            if (!fresh) {
                continue;
            }
            if (el.dataset.pkFragmentMode === "list") {
                lists.push([el, fresh, key]);
            } else if (swapNode(el, fresh, key)) {
                swapped.push(key);
            }
        }
    }
    for (const key of (payload && payload.missing) || []) {
        for (const el of nodesFor(key)) {
            if (el.dataset.pkFragmentKeep) {
                // A node the fresh render shows elsewhere stays as it is (it
                // moves on the next visit).
                continue;
            }
            if (el.dataset.pkFragmentMode === "list" && el.dataset.pkFragmentKeepEmpty) {
                // A whole section gone from the fresh
                // render (switched off elsewhere) hides.
                emptyNode(el, key);
            } else if (el.dataset.pkFragmentMode === "list") {
                const empty = document.createElement(el.tagName);
                lists.push([el, empty, key]);
            } else {
                emptyNode(el, key);
            }
        }
    }
    // Lists last: their items' own fragments were refreshed above.
    for (const [el, fresh, key] of lists) {
        if (reconcileList(el, fresh, key)) {
            swapped.push(key);
            // data-pk-fragment-keep-empty: a list that
            // renders its own empty state (a dashboard section) stays shown.
            if (!el.querySelector("[data-pk-fragment-item]") && !el.dataset.pkFragmentKeepEmpty) {
                el.hidden = true;
            }
        }
    }
    if (payload && payload.title) {
        document.title = payload.title;
    }
    document.dispatchEvent(new CustomEvent("pk:fragments", { detail: { keys: swapped } }));
    return swapped;
}

// -------------------------------------------------------------- queueing
const pending = new Set();
let timer = null;
let chain = Promise.resolve();

async function run() {
    const keys = matchFragmentKeys([...pending]);
    pending.clear();
    for (const key of [...stale]) {
        // Retried once nothing holds it any more.
        const held = nodesFor(key).some((el) =>
            el.dataset.pkFragmentMode === "list"
                ? [...el.querySelectorAll("[data-pk-fragment-item]")].some(itemBusy)
                : isBusy(el)
        );
        if (!held) {
            stale.delete(key);
            if (!keys.includes(key)) {
                keys.push(key);
            }
        }
    }
    if (!keys.length || !app()) {
        return;
    }
    let payload;
    try {
        payload = await pkFetch(window.location.href, {
            headers: { [FRAGMENTS_HEADER]: keys.slice(0, MAX_KEYS).join(",") },
            toast: false,
        });
    } catch (error) {
        // This page is no longer readable (access lost, e.g. from
        // another tab): leave it, with a neutral note, instead of an error.
        if (error && error.status === 403) {
            pkLeavePage(_t("You no longer have access to this page."));
            return;
        }
        // Offline / error: what shows stays as it is; the next visit of the
        // page is fresh (the save marked the session dirty).
        return;
    }
    if (payload && payload.fragments) {
        applyFragments(payload);
    }
}

/** Refresh the fragments matching ``patterns`` (debounced unless immediate). */
export function requestRefresh(patterns, { immediate = false } = {}) {
    for (const pattern of patterns || []) {
        pending.add(pattern);
    }
    clearTimeout(timer);
    timer = setTimeout(flushFragments, immediate ? 0 : DEBOUNCE_MS);
}

/** Run the queued refresh now; resolves once applied. */
export function flushFragments() {
    clearTimeout(timer);
    timer = null;
    chain = chain.then(run, run);
    return chain;
}

// ------------------------------------------------------- back / forward
function storage() {
    try {
        return window.sessionStorage;
    } catch {
        return null;
    }
}

/** The server clock now, as seen from this page (render time + elapsed). */
export function serverNow() {
    const root = app();
    const rendered = Number((root && root.dataset.pkRenderedAt) || 0);
    return rendered ? rendered + (Date.now() - LOADED_AT) : Date.now();
}

/** The stored dirty stamp; the old key's stamp is moved once (task 5199). */
function readDirty(store) {
    const old = store.getItem(OLD_DIRTY_KEY);
    if (old !== null) {
        store.removeItem(OLD_DIRTY_KEY);
        const merged = Math.max(Number(store.getItem(DIRTY_KEY) || 0), Number(old) || 0);
        if (merged) {
            store.setItem(DIRTY_KEY, String(merged));
        }
    }
    return Number(store.getItem(DIRTY_KEY) || 0);
}

export function markDirty(at) {
    const store = storage();
    if (!store) {
        return;
    }
    try {
        const previous = readDirty(store);
        store.setItem(DIRTY_KEY, String(Math.max(previous, Number(at) || serverNow())));
    } catch {
        // private mode: back shows the cached page
    }
}

/** Was something saved after this page was rendered? */
export function pageIsStale() {
    const root = app();
    const store = storage();
    if (!root || !store) {
        return false;
    }
    let dirty = 0;
    try {
        dirty = readDirty(store);
    } catch {
        return false;
    }
    const rendered = Number(root.dataset.pkRenderedAt || 0);
    return Boolean(dirty && rendered && dirty > rendered);
}

function navigationType() {
    try {
        const entry = performance.getEntriesByType("navigation")[0];
        return (entry && entry.type) || "navigate";
    } catch {
        return "navigate";
    }
}

window.addEventListener("pageshow", (ev) => {
    if (!app()) {
        return;
    }
    if (!ev.persisted && navigationType() !== "back_forward") {
        return;
    }
    if (pageIsStale()) {
        // This reload replays a back/forward step — the nav stack
        // (pk_app_nav.js) must not treat it as a reload (which resets it).
        try {
            storage() && storage().setItem(NAV_BF_RELOAD_KEY, "1");
        } catch {
            // ignore: the stack falls back to the declared parent
        }
        window.location.reload();
    } else if (ev.persisted) {
        document.dispatchEvent(new CustomEvent("pk:live-count-refresh"));
    }
});

// ---------------------------------------------------------------- wiring
document.addEventListener("pk:saved", (ev) => {
    const result = ev.detail && ev.detail.result;
    if (!result || !app()) {
        return;
    }
    markDirty(result.saved_at);
    if (result.live_counts) {
        document.dispatchEvent(new CustomEvent("pk:live-count-refresh"));
    }
    if (Array.isArray(result.refresh) && result.refresh.length) {
        requestRefresh(result.refresh);
    }
});

document.addEventListener("pk:refresh", (ev) => {
    const detail = ev.detail || {};
    requestRefresh(detail.patterns || [], { immediate: Boolean(detail.immediate) });
});

// « Done » of an edit card: what is queued — and what waited for the card —
// goes at once.
document.addEventListener("pk:refresh-now", () => {
    if (pending.size || stale.size) {
        flushFragments();
    }
});

// A node skipped while it held the focus is retried once it lets go.
document.addEventListener("focusout", () => {
    if (stale.size && !timer) {
        timer = setTimeout(flushFragments, DEBOUNCE_MS);
    }
});

// A shell form POST changes data too: pages shown again by « back » reload.
document.addEventListener("submit", (ev) => {
    const form = ev.target;
    if (
        form instanceof HTMLFormElement &&
        form.closest(".o_pk_app") &&
        (form.method || "").toLowerCase() === "post" &&
        !form.hasAttribute("data-pk-no-dirty")
    ) {
        markDirty(serverNow());
    }
});
