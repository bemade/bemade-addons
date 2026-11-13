/*
 * The shell's sheets and lazy bodies (moved to the kit by task 5381, P4c2).
 * Progressive enhancement, inert outside .o_pk_app[data-pk-app-shell].
 *
 * - Sheets: a native <dialog class="o_pk_sheet"> (bemade_portal_kit.pk_sheet)
 *   opened by any [data-pk-sheet-open="<dialog id>"] control; closed by
 *   [data-pk-sheet-close] or a click on the backdrop. A lazy body
 *   (data-pk-lazy-url) is fetched once through pk_fetch, or on EVERY open
 *   with data-pk-lazy-fresh="1" (a history the page can change). An opener
 *   with data-pk-sheet-url loads that body into the shared sheet, fresh on
 *   every open (it is a link to the full page: a new-tab click, or a page
 *   without the sheet, follows the link). A [data-pk-sheet-refetch] link
 *   inside a sheet reloads its body from its href (filter chips), the sheet
 *   staying open. data-pk-sheet-open-on-load: the sheet opens on load (e.g.
 *   a form the server answered an error in).
 * - Lazy rows: a <details data-pk-lazy-url> fetches its body
 *   (.o_pk_lazy_body) on first open; a row « Details » control
 *   ([data-pk-row-expand="<region id>"]) shows / hides that region (a
 *   data-pk-lazy-url region fetches its body on first open) and marks its
 *   .o_pk_row_group « o_pk_row_open »; a refreshed row face
 *   (« pk:fragments ») follows the region it controls.
 * - A loaded body is marked data-pk-loaded="1" ("0" after a failure: retried
 *   on the next open). An answer with nothing in it (no li, a, tr,
 *   .o_pk_empty or [data-pk-lazy-filled]) reads « Nothing to show. »; the
 *   loaded body is announced with « pk:lazy-loaded ».
 *
 * Exports openSheet(id) and bootSheets() (what runs on load).
 */
import { _t } from "@web/core/l10n/translation";
import { pkFetch } from "@bemade_portal_kit/js/pk_fetch";

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

// ------------------------------------------------------------ lazy load
async function loadLazy(container, url, target) {
    if (!url || !target || container.dataset.pkLoaded === "1") {
        return;
    }
    container.dataset.pkLoaded = "1";
    try {
        const html = await pkFetch(url, { as: "html" });
        target.innerHTML = html;
        // Listeners may enhance the injected body (e.g. date bounds).
        target.dispatchEvent(new CustomEvent("pk:lazy-loaded", { bubbles: true }));
        // A fragment with its own empty state keeps it; [data-pk-lazy-filled]
        // = content even without a link.
        if (!target.querySelector("li, a, tr, .o_pk_empty, [data-pk-lazy-filled]")) {
            const empty = document.createElement("p");
            empty.className = "o_pk_empty";
            empty.textContent = _t("Nothing to show.");
            target.replaceChildren(empty);
        }
    } catch {
        container.dataset.pkLoaded = "0"; // retry on next open
        const failed = document.createElement("p");
        failed.className = "o_pk_empty";
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
            details.dataset.pkLazyUrl &&
            details.closest(".o_pk_app")
        ) {
            loadLazy(details, details.dataset.pkLazyUrl, details.querySelector(".o_pk_lazy_body"));
        }
    },
    true
);

// A row's « Details » control: a button, not a <details>, so the row's main
// link stays one stretched link and the detail spans the row's full width.
document.addEventListener("click", (ev) => {
    const toggle = ev.target.closest && ev.target.closest("[data-pk-row-expand]");
    if (!toggle || !toggle.closest(".o_pk_app")) {
        return;
    }
    const region = document.getElementById(toggle.dataset.pkRowExpand);
    if (!region) {
        return;
    }
    ev.preventDefault();
    const open = region.hidden;
    region.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.closest(".o_pk_row_group")?.classList.toggle("o_pk_row_open", open);
    if (open && region.dataset.pkLazyUrl) {
        loadLazy(region, region.dataset.pkLazyUrl, region.querySelector(".o_pk_lazy_body"));
    }
});

document.addEventListener("pk:fragments", () => {
    for (const toggle of document.querySelectorAll(".o_pk_app [data-pk-row-expand]")) {
        const region = document.getElementById(toggle.dataset.pkRowExpand);
        if (region) {
            toggle.setAttribute("aria-expanded", region.hidden ? "false" : "true");
        }
    }
});

// --------------------------------------------------------------- sheets
function refetchSheet(dialog, url) {
    const body = dialog.querySelector(".o_pk_sheet_body");
    dialog.dataset.pkLoaded = "0";
    const loading = document.createElement("p");
    loading.className = "o_pk_empty o_pk_lazy_loading";
    loading.textContent = _t("Loading…");
    body.replaceChildren(loading);
    return loadLazy(dialog, url, body);
}

/** Open the sheet ``id`` (its lazy body loaded, or reloaded when fresh). */
export function openSheet(id) {
    const dialog = document.getElementById(id);
    if (!dialog || typeof dialog.showModal !== "function") {
        return;
    }
    if (!dialog.open) {
        dialog.showModal();
    }
    if (dialog.dataset.pkLazyUrl) {
        if (dialog.dataset.pkLazyFresh === "1") {
            refetchSheet(dialog, dialog.dataset.pkLazyUrl);
            return;
        }
        loadLazy(dialog, dialog.dataset.pkLazyUrl, dialog.querySelector(".o_pk_sheet_body"));
    }
}

document.addEventListener("click", (ev) => {
    const root = app();
    if (!root || !root.contains(ev.target)) {
        return;
    }
    const opener = ev.target.closest("[data-pk-sheet-open]");
    if (opener) {
        const url = opener.dataset.pkSheetUrl;
        if (url) {
            const dialog = document.getElementById(opener.dataset.pkSheetOpen);
            if (!dialog || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) {
                return;
            }
            dialog.dataset.pkLazyUrl = url;
            dialog.dataset.pkLazyFresh = "1";
        }
        ev.preventDefault();
        openSheet(opener.dataset.pkSheetOpen);
        return;
    }
    const refetch = ev.target.closest("dialog.o_pk_sheet [data-pk-sheet-refetch]");
    if (refetch && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey) {
        ev.preventDefault();
        refetchSheet(refetch.closest("dialog"), refetch.getAttribute("href"));
        return;
    }
    const closer = ev.target.closest("[data-pk-sheet-close]");
    if (closer) {
        const dialog = closer.closest("dialog");
        if (dialog) {
            dialog.close();
        }
        return;
    }
    // A click on the backdrop lands on the <dialog> itself.
    if (ev.target instanceof HTMLDialogElement && ev.target.classList.contains("o_pk_sheet")) {
        const rect = ev.target.getBoundingClientRect();
        const inside =
            ev.clientX >= rect.left && ev.clientX <= rect.right &&
            ev.clientY >= rect.top && ev.clientY <= rect.bottom;
        if (!inside) {
            ev.target.close();
        }
    }
});

/** What runs on load (exported for the tests). */
export function bootSheets() {
    const root = app();
    const reopen = root && root.querySelector("dialog.o_pk_sheet[data-pk-sheet-open-on-load]");
    if (reopen) {
        openSheet(reopen.id);
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootSheets);
} else {
    bootSheets();
}
