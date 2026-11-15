/*
 * Task 5202 (kit P7) — the dashboard's scroll anchoring ([data-pk-dashboard];
 * moved from the first consumer, task 1624 review round 2). Inert elsewhere.
 *
 * A fold-out of the dashboard (a <details> summary, a row's « Details »
 * [data-pk-row-expand]) never moves its own header in the viewport. Its top
 * is kept where it was across the toggle (window.scrollBy; the browser's own
 * anchoring is off on the dashboard, overflow-anchor: none), for the layout
 * and the lazy body that follow; a collapse near the page end keeps a spacer
 * rather than letting the page clamp the scroll. A user scroll ends the hold.
 */
export const PK_DASH_HOLD_MS = 900;

function dashboard() {
    return document.querySelector(".o_pk_app [data-pk-dashboard]");
}

let hold = null;

function spacerOf(dash) {
    return Number(dash.dataset.pkDashSpacer || 0);
}

function setSpacer(dash, px) {
    const value = Math.max(0, Math.round(px));
    dash.dataset.pkDashSpacer = String(value);
    dash.style.paddingBottom = value ? `${value}px` : "";
}

/** Scroll so that the held anchor is back where it was. */
export function pkDashKeep() {
    if (!hold) {
        return;
    }
    const { anchor, top, dash } = hold;
    if (!anchor.isConnected) {
        pkDashRelease();
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
    pkDashKeep();
    if (hold && performance.now() < hold.until) {
        hold.frame = window.requestAnimationFrame(tick);
    } else {
        pkDashRelease();
    }
}

export function pkDashRelease() {
    if (hold && hold.frame) {
        window.cancelAnimationFrame(hold.frame);
    }
    hold = null;
}

/** Is an anchor held (tests)? */
export function pkDashHeld() {
    return hold ? hold.anchor : null;
}

/** Keep ``anchor`` where it is in the viewport for the toggle that follows. */
export function pkDashHoldAnchor(anchor) {
    const dash = anchor && anchor.closest("[data-pk-dashboard]");
    if (!dash) {
        return false;
    }
    pkDashRelease();
    hold = {
        anchor,
        dash,
        top: anchor.getBoundingClientRect().top,
        until: performance.now() + PK_DASH_HOLD_MS,
        frame: 0,
    };
    // After the toggle's own handlers (same click), then every frame.
    setTimeout(pkDashKeep, 0);
    hold.frame = window.requestAnimationFrame(tick);
    return true;
}

/** The toggle a click lands on: a <details> summary or a row expander. */
export function pkDashAnchorOf(target) {
    if (!target || !target.closest) {
        return null;
    }
    const summary = target.closest("summary");
    if (summary && summary.parentElement && summary.parentElement.tagName === "DETAILS") {
        return summary;
    }
    return target.closest("[data-pk-row-expand]");
}

// Capture phase: measured BEFORE the toggle changes anything.
document.addEventListener(
    "click",
    (ev) => {
        const anchor = pkDashAnchorOf(ev.target);
        if (anchor && anchor.closest(".o_pk_app [data-pk-dashboard]")) {
            pkDashHoldAnchor(anchor);
        }
    },
    true
);

// A lazy body that lands later is kept in place as well.
document.addEventListener("pk:lazy-loaded", (ev) => {
    if (hold && hold.dash.contains(ev.target)) {
        hold.until = Math.max(hold.until, performance.now() + 300);
        pkDashKeep();
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
            if (name === "keydown" && ev.key === " " && pkDashAnchorOf(ev.target)) {
                return; // Space on a toggle: that toggle's own hold
            }
            pkDashRelease();
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
