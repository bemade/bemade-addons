/*
 * The shell's boot (moved to the kit by task 5381, P4c2). Inert outside
 * .o_pk_app[data-pk-app-shell].
 *
 * - The device drafts (pk_draft_store): another user's or database's drafts
 *   are purged on load; [data-pk-draft-clear="<record key prefix>"] drops
 *   this user's drafts under that prefix (the landing page of a record just
 *   created from a draft); the logout link (a[href^="/web/session/logout"])
 *   clears every draft on the device: nothing typed stays behind.
 * - A neutralized test database's ribbon (#oe_neutralize_banner), when the
 *   consumer pins it (position: fixed), lifts what sits at the bottom by
 *   its height: --pk-ribbon-h on the document (0 without a ribbon).
 *
 * Exports bootShell() (what runs on load).
 */
import {
    clearAllDrafts,
    purgeForeignDrafts,
    removeDraftsWithPrefix,
} from "@bemade_portal_kit/js/pk_draft_store";

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

function measureRibbon() {
    const banner = document.getElementById("oe_neutralize_banner");
    if (!banner || !app()) {
        return;
    }
    const update = () => {
        const fixed = getComputedStyle(banner).position === "fixed";
        document.documentElement.style.setProperty(
            "--pk-ribbon-h",
            fixed ? `${banner.getBoundingClientRect().height}px` : "0px"
        );
    };
    update();
    if (window.ResizeObserver) {
        new ResizeObserver(update).observe(banner);
    }
    window.addEventListener("resize", update);
}

/** What runs on load (exported for the tests). */
export function bootShell() {
    const root = app();
    if (!root) {
        return;
    }
    purgeForeignDrafts();
    for (const marker of root.querySelectorAll("[data-pk-draft-clear]")) {
        removeDraftsWithPrefix(marker.dataset.pkDraftClear);
    }
    measureRibbon();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootShell);
} else {
    bootShell();
}

document.addEventListener("click", (ev) => {
    const root = app();
    if (!root || !root.contains(ev.target)) {
        return;
    }
    if (ev.target.closest('a[href^="/web/session/logout"]')) {
        clearAllDrafts();
    }
});
