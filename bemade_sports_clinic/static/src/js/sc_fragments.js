/*
 * Task 1611 — read fragments: what shows on screen follows an in-place save,
 * without a reload and without « Done ». Inert outside .o_sc_app.
 *
 * Server side (controllers/app_shell.py, « Read fragments »): a READ-ONLY
 * region of a shell page carries data-sc-fragment="<model>:<id>:<part>"; a
 * save answers ``refresh`` — key patterns (``*`` = one key segment) from its
 * SAVE_REGISTRY spec. This module:
 *
 * - on « sc:saved », collects the patterns, waits ~300 ms (one fetch for a
 *   burst of saves), matches them against the keys the page carries and GETs
 *   the page's OWN URL with « X-Sc-Fragments: k1,k2 » — the route renders as
 *   for a reload and answers {fragments: {key: html}, missing, title};
 * - swaps each node in place, NEVER one that holds an OWL island
 *   (owl-component), the focused element or an open sheet: such a key is
 *   kept « stale » and retried once the element lets go (focus out, « Done »);
 *   a <select> keeps its element and its value (options refreshed); an edit
 *   card's read view keeps its hidden state; a key missing from the fresh
 *   render empties and hides its node;
 * - data-sc-fragment-mode="list": the container's live items
 *   (data-sc-fragment-item) are KEPT — their islands survive — and only
 *   re-ordered / dropped / regrouped as in the fresh render; while an item is
 *   being edited (or holds the focus) the list waits (retried after « Done »);
 * - « Done » of an edit card refreshes at once (``sc:refresh-now``);
 * - back / forward (owner decision 2026-10-17): every page carries its server
 *   render time (data-sc-rendered-at); a save stores its server time
 *   (``saved_at``) in sessionStorage; a page shown again from the
 *   back / forward cache (or the HTTP cache) reloads only when something was
 *   saved after it was rendered — otherwise the instant cached back stays.
 *
 * API for other modules: requestRefresh(patterns, {immediate}),
 * flushFragments(), applyFragments(payload), matchFragmentKeys(patterns);
 * or the DOM event « sc:refresh » {detail: {patterns, immediate}}.
 * After a swap the document receives « sc:fragments » {detail: {keys}}.
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

export const FRAGMENTS_HEADER = "X-Sc-Fragments";
const DEBOUNCE_MS = 300;
const DIRTY_KEY = "sc_dirty_at:v1";
const MAX_KEYS = 200;
// Client clock when this page was parsed (server time ≈ rendered-at + elapsed).
const LOADED_AT = Date.now();

function app() {
    return document.querySelector(".o_sc_app[data-sc-app-shell]");
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
    for (const el of root.querySelectorAll("[data-sc-fragment]")) {
        const key = el.dataset.scFragment;
        if (key && !keys.includes(key) && regs.some((re) => re.test(key))) {
            keys.push(key);
        }
    }
    return keys;
}

function nodesFor(key) {
    return [...document.querySelectorAll("[data-sc-fragment]")].filter(
        (el) => el.dataset.scFragment === key
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
    if (el.hasAttribute("data-sc-edit-view")) {
        // The card may be open on its edit view: the read view stays hidden.
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
            if (child.dataset.scFragmentItem) {
                parts.push(`[${child.dataset.scFragmentItem}]`);
            } else {
                parts.push(`<${child.tagName}>${itemSignature(child)}</>`);
            }
        }
    }
    return parts.join("|");
}

function itemBusy(item) {
    return holdsFocus(item) || Boolean(item.dataset.scEditOpen) || Boolean(item.querySelector("dialog[open]"));
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
    for (const item of live.querySelectorAll("[data-sc-fragment-item]")) {
        liveItems.set(item.dataset.scFragmentItem, item);
    }
    // An item being edited (or holding the focus) never moves or goes under
    // the user's hands: the new order waits for « Done » / focus out.
    if ([...liveItems.values()].some(itemBusy)) {
        stale.add(key);
        return false;
    }
    const active = document.activeElement;
    for (const slot of [...fresh.querySelectorAll("[data-sc-fragment-item]")]) {
        const existing = liveItems.get(slot.dataset.scFragmentItem);
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
            if (el.dataset.scFragmentMode === "list") {
                lists.push([el, fresh, key]);
            } else if (swapNode(el, fresh, key)) {
                swapped.push(key);
            }
        }
    }
    for (const key of (payload && payload.missing) || []) {
        for (const el of nodesFor(key)) {
            if (el.dataset.scFragmentMode === "list") {
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
            if (!el.querySelector("[data-sc-fragment-item]")) {
                el.hidden = true;
            }
        }
    }
    if (payload && payload.title) {
        document.title = payload.title;
    }
    document.dispatchEvent(new CustomEvent("sc:fragments", { detail: { keys: swapped } }));
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
            el.dataset.scFragmentMode === "list"
                ? [...el.querySelectorAll("[data-sc-fragment-item]")].some(itemBusy)
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
        payload = await scFetch(window.location.href, {
            headers: { [FRAGMENTS_HEADER]: keys.slice(0, MAX_KEYS).join(",") },
            toast: false,
        });
    } catch {
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
    const rendered = Number((root && root.dataset.scRenderedAt) || 0);
    return rendered ? rendered + (Date.now() - LOADED_AT) : Date.now();
}

export function markDirty(at) {
    const store = storage();
    if (!store) {
        return;
    }
    try {
        const previous = Number(store.getItem(DIRTY_KEY) || 0);
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
        dirty = Number(store.getItem(DIRTY_KEY) || 0);
    } catch {
        return false;
    }
    const rendered = Number(root.dataset.scRenderedAt || 0);
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
        // Task 1618: this reload replays a back/forward step — the nav stack
        // (sc_app_nav.js) must not treat it as a reload (which resets it).
        try {
            storage() && storage().setItem("sc_nav_bf_reload:v1", "1");
        } catch {
            // ignore: the stack falls back to the declared parent
        }
        window.location.reload();
    } else if (ev.persisted) {
        document.dispatchEvent(new CustomEvent("sc:live-count-refresh"));
    }
});

// ---------------------------------------------------------------- wiring
document.addEventListener("sc:saved", (ev) => {
    const result = ev.detail && ev.detail.result;
    if (!result || !app()) {
        return;
    }
    markDirty(result.saved_at);
    if (result.live_counts) {
        document.dispatchEvent(new CustomEvent("sc:live-count-refresh"));
    }
    if (Array.isArray(result.refresh) && result.refresh.length) {
        requestRefresh(result.refresh);
    }
});

document.addEventListener("sc:refresh", (ev) => {
    const detail = ev.detail || {};
    requestRefresh(detail.patterns || [], { immediate: Boolean(detail.immediate) });
});

// « Done » (sc_app_ui.js): what is queued — and what waited for the card —
// goes at once.
document.addEventListener("sc:refresh-now", () => {
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
        form.closest(".o_sc_app") &&
        (form.method || "").toLowerCase() === "post" &&
        !form.matches("form[data-sc-pref]")
    ) {
        markDirty(serverNow());
    }
});
