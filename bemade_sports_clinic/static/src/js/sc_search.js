/*
 * Task 1650 — the app header's search (inert outside .o_sc_app).
 *
 * The magnifier ([data-sc-search-open], a link to /my/players without JS),
 * « / » or Ctrl/⌘-K (laptop; never while typing in a field) open
 * #sc_search_sheet: full screen on a phone, the centred sheet on a laptop.
 * Its input (focused: the user asked to search) fetches
 * /my/app/search?q=… 250 ms after the last key, a newer request aborting the
 * older one; the HTML fragment replaces the results. ArrowDown / ArrowUp
 * move among the results, Enter opens the highlighted one (else the first);
 * Escape closes (the native dialog).
 */
const DEBOUNCE_MS = 250;

let timer = null;
let inflight = null;
let active = -1;

function sheet() {
    return document.getElementById("sc_search_sheet");
}

function results(dialog) {
    return [...dialog.querySelectorAll("[data-sc-search-result]")];
}

function highlight(dialog, index) {
    const items = results(dialog);
    items.forEach((item, i) => item.classList.toggle("o_sc_search_active", i === index));
    active = items.length ? Math.max(-1, Math.min(index, items.length - 1)) : -1;
    if (active >= 0) {
        items[active].scrollIntoView({ block: "nearest" });
    }
}

async function runSearch(dialog, query) {
    if (inflight) {
        inflight.abort();
    }
    const controller = new AbortController();
    inflight = controller;
    try {
        const response = await fetch(`/my/app/search?q=${encodeURIComponent(query)}`, {
            credentials: "same-origin",
            signal: controller.signal,
            headers: { "X-Requested-With": "XMLHttpRequest", Accept: "text/html" },
        });
        if (!response.ok) {
            return;
        }
        const html = await response.text();
        if (inflight !== controller) {
            return; // a newer search answered meanwhile
        }
        dialog.querySelector("[data-sc-search-body]").innerHTML = html;
        highlight(dialog, -1);
        dialog.dataset.scSearchQuery = query;
    } catch {
        // aborted / offline: the previous results stay
    } finally {
        if (inflight === controller) {
            inflight = null;
        }
    }
}

export function openSearch() {
    const dialog = sheet();
    if (!dialog || typeof dialog.showModal !== "function") {
        return false;
    }
    if (!dialog.open) {
        dialog.showModal();
    }
    const input = dialog.querySelector("[data-sc-search-input]");
    if (input) {
        input.focus();
        input.select();
    }
    return true;
}

function typing(target) {
    return Boolean(
        target &&
            (target.isContentEditable ||
                target.closest?.("input, textarea, select, [contenteditable='true']"))
    );
}

document.addEventListener("click", (ev) => {
    const opener = ev.target.closest && ev.target.closest("[data-sc-search-open]");
    if (!opener || !opener.closest(".o_sc_app")) {
        return;
    }
    if (ev.metaKey || ev.ctrlKey || ev.shiftKey) {
        return; // a new tab: the link
    }
    if (openSearch()) {
        ev.preventDefault();
    }
});

document.addEventListener("input", (ev) => {
    const input = ev.target;
    if (!input.matches || !input.matches("[data-sc-search-input]")) {
        return;
    }
    const dialog = input.closest("dialog");
    clearTimeout(timer);
    timer = setTimeout(() => runSearch(dialog, input.value.trim()), DEBOUNCE_MS);
});

document.addEventListener("keydown", (ev) => {
    const dialog = sheet();
    if (!dialog || !document.querySelector(".o_sc_app")) {
        return;
    }
    if (dialog.open && dialog.contains(ev.target)) {
        const items = results(dialog);
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            highlight(dialog, active + (ev.key === "ArrowDown" ? 1 : -1));
        } else if (ev.key === "Enter" && ev.target.matches("[data-sc-search-input]")) {
            ev.preventDefault();
            clearTimeout(timer);
            const target = items[active >= 0 ? active : 0];
            if (target) {
                target.click();
            } else if (ev.target.value.trim()) {
                runSearch(dialog, ev.target.value.trim());
            }
        }
        return;
    }
    if (dialog.open || typing(ev.target) || ev.altKey) {
        return;
    }
    const slash = ev.key === "/" && !ev.ctrlKey && !ev.metaKey;
    const ctrlK = (ev.ctrlKey || ev.metaKey) && (ev.key === "k" || ev.key === "K");
    if ((slash || ctrlK) && document.querySelector("[data-sc-search-open]")) {
        ev.preventDefault();
        openSearch();
    }
});
