/*
 * Task 1660 / 5200 (kit P5) — guide videos in help articles.
 *
 * A rich-text editor that strips <video controls> leaves the author a plain
 * link to the video attachment (/web/content/<id>…) with the class
 * « o_pk_video »; this turns it into an inline phone-sized
 * <video controls playsinline> player. The old class « o_fc_video » is read
 * too: articles already stored with it keep their players (their HTML is
 * content, never rewritten).
 *
 * Safety rule: a same-origin /web/content/<id> attachment whose response is
 * a video/* type ONLY (checked with a HEAD request) — anything else stays a
 * plain link.
 *
 * Opening /web/content/<id> itself does not play on WebKit: Odoo serves
 * attachments with « Content-Security-Policy: default-src 'none' » and WebKit
 * applies it to its own media document. The inline player is not affected
 * (the article page's policy applies), so once the player is in place the
 * link is hidden; it comes back if the player fails.
 *
 * On load, the links already in the page are upgraded (only if there is one).
 * A page whose article renders later calls pkWatchVideoLinks(isActive): the
 * links that appear are upgraded while isActive(location.pathname) holds.
 */

// The link classes: the kit's, and the one stored articles already use.
export const LINKS = "a.o_pk_video, a.o_fc_video";

const VIDEO_PATH = /^\/web\/content\/\d+(\/[^?#]*)?$/;
const IMAGE_PATH = /^\/web\/(image|content)\/\d+(\/[^?#]*)?$/;

function sameOrigin(href, pattern, origin) {
    let url;
    try {
        url = new URL(href, origin);
    } catch {
        return null;
    }
    if (url.origin !== origin || !pattern.test(url.pathname)) {
        return null;
    }
    return url.pathname + url.search;
}

export function pkVideoSource(href, origin = window.location.origin) {
    return sameOrigin(href, VIDEO_PATH, origin);
}

/** True when the attachment answers with a video/* Content-Type. */
export async function pkIsVideo(src) {
    try {
        const res = await fetch(src, { method: "HEAD", credentials: "same-origin" });
        return res.ok && /^video\//i.test(res.headers.get("Content-Type") || "");
    } catch {
        return false;
    }
}

function inEditor(link) {
    return Boolean(link.closest("[contenteditable=true], .odoo-editor-editable"));
}

async function upgrade(link, src) {
    if (!(await pkIsVideo(src)) || !link.isConnected) {
        return false; // not a video attachment: the link stays a link
    }
    const video = document.createElement("video");
    video.className = "o_pk_video_player";
    video.controls = true;
    video.setAttribute("playsinline", "");
    video.preload = "metadata";
    const poster =
        link.dataset.poster && sameOrigin(link.dataset.poster, IMAGE_PATH, window.location.origin);
    if (poster) {
        video.poster = poster;
    }
    video.style.maxWidth = "100%";
    video.style.width = "420px";
    video.style.display = "block";
    video.addEventListener("error", () => {
        // The player failed: back to the plain link.
        video.remove();
        link.hidden = false;
    });
    video.src = src;
    link.before(video);
    link.hidden = true;
    return true;
}

/**
 * Upgrade every guide video link (LINKS) under root (once per link).
 * @returns {Promise<number>} the number of players inserted
 */
export async function pkUpgradeVideoLinks(root = document) {
    const jobs = [];
    for (const link of root.querySelectorAll(LINKS)) {
        if (link.dataset.pkVideoDone || inEditor(link)) {
            continue;
        }
        link.dataset.pkVideoDone = "1";
        const src = pkVideoSource(link.getAttribute("href") || "");
        if (src) {
            jobs.push(upgrade(link, src));
        }
    }
    const done = await Promise.all(jobs);
    return done.filter(Boolean).length;
}

/**
 * Upgrade the links now and on every DOM change while
 * ``isActive(window.location.pathname)`` is true.
 */
export function pkWatchVideoLinks(isActive = () => true) {
    pkUpgradeVideoLinks();
    let pending = false;
    const observer = new MutationObserver(() => {
        if (!pending && isActive(window.location.pathname)) {
            pending = true;
            window.requestAnimationFrame(() => {
                pending = false;
                pkUpgradeVideoLinks();
            });
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return observer;
}

function start() {
    if (document.querySelector(LINKS)) {
        pkUpgradeVideoLinks();
    }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
