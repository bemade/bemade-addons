/*
 * The shell's segmented page tabs (moved to the kit by task 5381, P4c2).
 * Progressive enhancement, inert outside .o_pk_app[data-pk-app-shell].
 *
 * Markup (bemade_portal_kit.pk_page_tabs): <nav data-pk-tabs> of real links
 * <a data-pk-tab="<key>" [data-pk-tab-aliases="<name> …"]>, the panels
 * <section data-pk-tab-panel="<key>">. Without JS each tab is a plain link
 * (the server renders the active panel). With it, a tab whose panel is on
 * the page switches in place (aria-selected / aria-pressed, the other
 * panels hidden) and its href replaces the address (?tab=). On load, a
 * #hash naming a tab or one of its aliases (e.g. the #fragment of a POST
 * round-trip) opens that tab.
 *
 * Exports activateTab(root, key) and bootTabs() (what runs on load).
 */
import { browser } from "@web/core/browser/browser";

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

function show(root, tab, panel) {
    for (const other of tab.parentElement.querySelectorAll("a[data-pk-tab]")) {
        const on = other === tab;
        other.setAttribute("aria-selected", on ? "true" : "false");
        other.setAttribute("aria-pressed", on ? "true" : "false");
    }
    for (const pane of root.querySelectorAll("[data-pk-tab-panel]")) {
        pane.hidden = pane !== panel;
    }
}

/** Show the tab named ``key`` (its key or one of its aliases), if any. */
export function activateTab(root, key) {
    const name = CSS.escape(key);
    const tab = root.querySelector(
        `[data-pk-tabs] a[data-pk-tab="${name}"], [data-pk-tabs] a[data-pk-tab-aliases~="${name}"]`
    );
    const panel = tab && root.querySelector(`[data-pk-tab-panel="${CSS.escape(tab.dataset.pkTab)}"]`);
    if (!panel) {
        return false;
    }
    show(root, tab, panel);
    return true;
}

document.addEventListener("click", (ev) => {
    const root = app();
    if (!root || !root.contains(ev.target)) {
        return;
    }
    const tab = ev.target.closest("[data-pk-tabs] a[data-pk-tab]");
    if (!tab || ev.metaKey || ev.ctrlKey || ev.shiftKey) {
        return;
    }
    const panel = root.querySelector(`[data-pk-tab-panel="${CSS.escape(tab.dataset.pkTab)}"]`);
    if (!panel) {
        return; // let the link load the page
    }
    ev.preventDefault();
    show(root, tab, panel);
    try {
        browser.history.replaceState(browser.history.state, "", tab.href);
    } catch {
        // ignore
    }
});

/** What runs on load (exported for the tests). */
export function bootTabs() {
    const root = app();
    if (!root) {
        return;
    }
    const hash = (browser.location.hash || "").slice(1).split("?")[0];
    if (hash && /^[\w-]+$/.test(hash)) {
        activateTab(root, hash);
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootTabs);
} else {
    bootTabs();
}
