/*
 * Task 1624, owner UAT round 2 (2026-10-29) — the app dashboard (/my/home,
 * [data-sc-dashboard]) in the browser. Inert elsewhere.
 *
 * - (The cause of the jumps was the former CSS flowing columns, which
 *   rebalanced on every fold-out; the page now has three fixed zones —
 *   left / right / bottom, views/sc_app_dashboard.xml.)
 * - Scroll anchoring: a fold-out of the dashboard (an « À faire » line, a
 *   « Voir les N autres », a player / event « Détails ») never moves its own
 *   header in the viewport. Its top is kept where it was across the toggle
 *   (window.scrollBy; the browser's own anchoring is off on the dashboard,
 *   overflow-anchor: none), for the layout and the lazy body that follow;
 *   a collapse near the page end keeps a spacer rather than letting the
 *   page clamp the scroll. A user scroll ends the hold.
 * - The quick « Retour prévu » of « Retours dépassés »: once saved, the
 *   card's date follows and « Dépassé » goes (a past date is refused by the
 *   field, #1727); the line counts refresh as read fragments.
 */
import { requestRefresh } from "@bemade_sports_clinic/js/sc_fragments";

const HOLD_MS = 900;

function dashboard() {
    return document.querySelector(".o_sc_app [data-sc-dashboard]");
}

// ------------------------------------------------------- scroll anchoring
let hold = null;

function spacerOf(dash) {
    return Number(dash.dataset.scDashSpacer || 0);
}

function setSpacer(dash, px) {
    const value = Math.max(0, Math.round(px));
    dash.dataset.scDashSpacer = String(value);
    dash.style.paddingBottom = value ? `${value}px` : "";
}

function keep() {
    if (!hold) {
        return;
    }
    const { anchor, top, dash } = hold;
    if (!anchor.isConnected) {
        release();
        return;
    }
    let delta = anchor.getBoundingClientRect().top - top;
    if (Math.abs(delta) < 0.5) {
        return;
    }
    window.scrollBy(0, delta);
    delta = anchor.getBoundingClientRect().top - top;
    if (delta > 0.5) {
        // The page got too short to scroll back (a collapse near its end):
        // a spacer under the dashboard, dropped as it scrolls out of view.
        setSpacer(dash, spacerOf(dash) + delta);
        window.scrollBy(0, delta);
    }
}

function tick() {
    if (!hold) {
        return;
    }
    keep();
    if (hold && performance.now() < hold.until) {
        hold.frame = window.requestAnimationFrame(tick);
    } else {
        release();
    }
}

function release() {
    if (hold && hold.frame) {
        window.cancelAnimationFrame(hold.frame);
    }
    hold = null;
}

/** Keep ``anchor`` where it is in the viewport for the toggle that follows. */
export function holdAnchor(anchor) {
    const dash = anchor && anchor.closest("[data-sc-dashboard]");
    if (!dash) {
        return;
    }
    release();
    hold = {
        anchor,
        dash,
        top: anchor.getBoundingClientRect().top,
        until: performance.now() + HOLD_MS,
        frame: 0,
    };
    // After the toggle's own handlers (same click), then every frame.
    setTimeout(keep, 0);
    hold.frame = window.requestAnimationFrame(tick);
}

function anchorOf(target) {
    if (!target || !target.closest) {
        return null;
    }
    const summary = target.closest("summary");
    if (summary && summary.parentElement && summary.parentElement.tagName === "DETAILS") {
        return summary;
    }
    return target.closest("[data-sc-row-expand]");
}

// Capture phase: measured BEFORE the toggle changes anything.
document.addEventListener(
    "click",
    (ev) => {
        const anchor = anchorOf(ev.target);
        if (anchor && anchor.closest(".o_sc_app [data-sc-dashboard]")) {
            holdAnchor(anchor);
        }
    },
    true
);

// Keyboard toggles (Enter / Space on a summary or a « Détails » button)
// fire a click too; a lazy body that lands later is kept in place as well.
document.addEventListener("sc:lazy-loaded", (ev) => {
    if (hold && hold.dash.contains(ev.target)) {
        hold.until = Math.max(hold.until, performance.now() + 300);
        keep();
    }
});

// The user scrolls: theirs, not ours.
for (const name of ["wheel", "touchstart", "keydown"]) {
    window.addEventListener(
        name,
        (ev) => {
            if (name === "keydown" && !["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(ev.key)) {
                return;
            }
            if (name === "keydown" && ev.key === " " && anchorOf(ev.target)) {
                return; // Space on a toggle: that toggle's own hold
            }
            release();
        },
        { passive: true, capture: true }
    );
}

window.addEventListener(
    "scroll",
    () => {
        const dash = dashboard();
        if (!dash || hold || !spacerOf(dash)) {
            return;
        }
        const spare = document.documentElement.scrollHeight - (window.scrollY + window.innerHeight);
        if (spare > 0) {
            setSpacer(dash, spacerOf(dash) - spare);
        }
    },
    { passive: true }
);

// ------------------------------------------------ quick « Retour prévu »
document.addEventListener("sc:saved", (ev) => {
    const { model, recordId, field, result } = ev.detail || {};
    if (model !== "sports.patient" || field !== "predicted_return_date" || !result || !dashboard()) {
        return;
    }
    for (const holder of document.querySelectorAll(`.o_sc_app [data-sc-row-return-value="${recordId}"]`)) {
        const date = holder.querySelector("[data-sc-row-return-date]");
        if (date && result.display !== undefined) {
            date.textContent = result.display || "—";
        }
        // Saved = today or later (a past date is refused): no longer passed.
        holder.classList.remove("o_sc_overdue");
        for (const flag of holder.querySelectorAll(".o_sc_overdue_sep, .o_sc_overdue_flag")) {
            flag.remove();
        }
    }
    // The « À faire » counts follow (the card itself stays until the next
    // visit: the player leaves the line then).
    requestRefresh(["sc.dashboard:todo:*"]);
});
