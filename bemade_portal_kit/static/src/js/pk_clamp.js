/*
 * Clamped texts (moved to the kit by task 5381, P4c2). Inert outside
 * .o_pk_app.
 *
 * A text clamped to N lines by the kit's CSS ([data-pk-clamp="N"], N = 1
 * to 6) offers « See more » ([data-pk-clamp-more]) only when it really
 * overflows. Its parent holds a meta line ([data-pk-clamp-meta]) with the
 * « See more » / « See less » ([data-pk-clamp-less]) buttons, an optional
 * « · » separator ([data-pk-clamp-sep], shown only between two visible
 * items) and the consumer's own items (a date…); the meta line hides when
 * empty. « See more » expands the text in place (data-pk-clamp-open),
 * « See less » folds it back. Measured whenever the text gets a size (a
 * hidden tab panel shown, an edit view closing, a resize) and after a
 * fragment refresh (data-pk-clamp-ready: set up once).
 *
 * Exports setupClamps() and measureClamp(text).
 */

function otherItems(meta, more, less, sep) {
    return meta && [...meta.children].some(
        (child) => child !== more && child !== less && child !== sep && !child.hidden
    );
}

/** Show « See more » (and the separator, the meta line) as the text needs. */
export function measureClamp(text) {
    const box = text.parentElement;
    if (!box || text.dataset.pkClampOpen || !text.getClientRects().length) {
        return;
    }
    const more = box.querySelector("[data-pk-clamp-more]");
    if (!more) {
        return;
    }
    const clamped = text.scrollHeight > text.clientHeight + 1;
    more.hidden = !clamped;
    const sep = box.querySelector("[data-pk-clamp-sep]");
    const meta = box.querySelector("[data-pk-clamp-meta]");
    const less = box.querySelector("[data-pk-clamp-less]");
    const hasOther = otherItems(meta, more, less, sep);
    if (sep) {
        sep.hidden = !(clamped && hasOther);
    }
    if (meta) {
        meta.hidden = !(clamped || hasOther);
    }
}

const observer = window.ResizeObserver
    ? new ResizeObserver((entries) => entries.forEach((entry) => measureClamp(entry.target)))
    : null;

/** Set up the page's clamped texts not set up yet. */
export function setupClamps() {
    for (const text of document.querySelectorAll(".o_pk_app [data-pk-clamp]:not([data-pk-clamp-ready])")) {
        text.dataset.pkClampReady = "1";
        measureClamp(text);
        if (observer) {
            observer.observe(text);
        }
    }
}

function metaVisible(box) {
    const meta = box.querySelector("[data-pk-clamp-meta]");
    if (meta) {
        meta.hidden = ![...meta.children].some((child) => !child.hidden && !child.matches("[data-pk-clamp-sep]"));
    }
}

document.addEventListener("click", (ev) => {
    const button = ev.target.closest && ev.target.closest("[data-pk-clamp-more], [data-pk-clamp-less]");
    if (!button || !button.closest(".o_pk_app")) {
        return;
    }
    const box = button.closest("[data-pk-clamp-meta]")?.parentElement;
    const text = box && box.querySelector("[data-pk-clamp]");
    if (!text) {
        return;
    }
    ev.preventDefault();
    const more = box.querySelector("[data-pk-clamp-more]");
    const less = box.querySelector("[data-pk-clamp-less]");
    const sep = box.querySelector("[data-pk-clamp-sep]");
    const meta = box.querySelector("[data-pk-clamp-meta]");
    const hasOther = otherItems(meta, more, less, sep);
    if (button.matches("[data-pk-clamp-more]")) {
        text.dataset.pkClampOpen = "1";
        if (more) {
            more.hidden = true;
            more.setAttribute("aria-expanded", "true");
        }
        if (less) {
            less.hidden = false;
            less.focus({ preventScroll: true });
        }
        if (sep) {
            sep.hidden = !(less && hasOther);
        }
        metaVisible(box);
        return;
    }
    delete text.dataset.pkClampOpen;
    if (less) {
        less.hidden = true;
    }
    if (more) {
        more.setAttribute("aria-expanded", "false");
    }
    measureClamp(text);
    if (more && !more.hidden) {
        more.focus({ preventScroll: true });
    }
});

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupClamps);
} else {
    setupClamps();
}
document.addEventListener("pk:fragments", setupClamps);
