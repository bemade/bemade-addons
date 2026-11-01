/*
 * Task 1660 — guide videos on the Knowledge user-guide pages.
 *
 * The Knowledge editor strips <video controls>, so an author inserts a plain
 * link with the class « o_fc_video » to the video attachment
 * (/web/content/<id>…); this turns it into an inline phone-sized
 * <video controls playsinline> player.
 *
 * Safety rule: a same-origin /web/content/<id> attachment whose response is
 * a video/* type ONLY (checked with a HEAD request) — anything else stays a
 * plain link.
 *
 * Review 2026-10-24 (iPhone Chrome / WebKit):
 * - The page a logged-in PORTAL user sees at /knowledge/article/<id> is
 *   Knowledge's portal web client (bundle knowledge.webclient, built on
 *   web.assets_backend) — not the public frontend layout. This file is
 *   therefore listed in BOTH web.assets_frontend (anonymous visitors) and
 *   knowledge.webclient (portal users).
 * - Opening /web/content/<id> itself does not play on WebKit: Odoo serves
 *   attachments with « Content-Security-Policy: default-src 'none' » and
 *   WebKit applies it to its own media document (« Refused to load … media-src
 *   »). The inline player is not affected (the article page's policy
 *   applies), so once the player is in place the link is hidden; it comes
 *   back if the player fails.
 */

const VIDEO_PATH = /^\/web\/content\/\d+(\/[^?#]*)?$/;
const IMAGE_PATH = /^\/web\/(image|content)\/\d+(\/[^?#]*)?$/;
// /knowledge/… with an optional website language prefix (/fr/…, /fr_CA/…).
const KNOWLEDGE_PATH = /^(\/[a-z]{2}(_[A-Za-z]{2,4})?)?\/knowledge\//;

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

export function scVideoSource(href, origin = window.location.origin) {
    return sameOrigin(href, VIDEO_PATH, origin);
}

/** True when the attachment answers with a video/* Content-Type. */
export async function scIsVideo(src) {
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
    if (!(await scIsVideo(src)) || !link.isConnected) {
        return false; // not a video attachment: the link stays a link
    }
    const video = document.createElement("video");
    video.className = "o_fc_video_player";
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
 * Upgrade every « a.o_fc_video » under root (once per link).
 * @returns {Promise<number>} the number of players inserted
 */
export async function scUpgradeVideoLinks(root = document) {
    const jobs = [];
    for (const link of root.querySelectorAll("a.o_fc_video")) {
        if (link.dataset.scVideoDone || inEditor(link)) {
            continue;
        }
        link.dataset.scVideoDone = "1";
        const src = scVideoSource(link.getAttribute("href") || "");
        if (src) {
            jobs.push(upgrade(link, src));
        }
    }
    const done = await Promise.all(jobs);
    return done.filter(Boolean).length;
}

export function scOnKnowledgePage(pathname = window.location.pathname) {
    return KNOWLEDGE_PATH.test(pathname);
}

function start() {
    // The article may render after load (public sidebar navigation, the
    // portal web client): upgrade now and on DOM changes.
    scUpgradeVideoLinks();
    let pending = false;
    new MutationObserver(() => {
        if (!pending && scOnKnowledgePage()) {
            pending = true;
            window.requestAnimationFrame(() => {
                pending = false;
                scUpgradeVideoLinks();
            });
        }
    }).observe(document.body, { childList: true, subtree: true });
}

if (scOnKnowledgePage()) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
