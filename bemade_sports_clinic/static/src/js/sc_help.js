/*
 * Task 1660 — in-app help.
 *
 * 1. The app bar « ? » follows the page's segmented tab: on a tab switch its
 *    href becomes the article of « <page>.<tab> », else « <page> », else the
 *    guide home (the mapping is rendered on the link, data-sc-help-map).
 * 2. Guide videos on the PUBLIC Knowledge pages (/knowledge/article/…): the
 *    Knowledge editor strips <video controls>, so an author inserts a plain
 *    link with the class « o_fc_video » to the video attachment
 *    (/web/content/<id>…); this turns it into an inline phone-sized
 *    <video controls playsinline> player, the link kept under it as the
 *    fallback. Same-origin /web/content attachments ONLY — any other source
 *    stays a plain link.
 */

export function scHelpUrlFor(link, tab) {
    let map = {};
    try {
        map = JSON.parse(link.dataset.scHelpMap || "{}");
    } catch {
        map = {};
    }
    const base = link.dataset.scHelpBase || "";
    const key = tab ? `${base}.${tab}` : base;
    return map[key] || map[base] || link.dataset.scHelpHome || link.getAttribute("href");
}

document.addEventListener("click", (ev) => {
    const tab = ev.target.closest && ev.target.closest("[data-sc-tabs] a[data-sc-tab]");
    if (!tab) {
        return;
    }
    const link = document.querySelector(".o_sc_app a[data-sc-help]");
    if (!link || !["player", "team"].includes(link.dataset.scHelpBase)) {
        return;
    }
    const url = scHelpUrlFor(link, tab.dataset.scTab);
    if (url) {
        link.setAttribute("href", url);
        link.dataset.scHelpKey = `${link.dataset.scHelpBase}.${tab.dataset.scTab}`;
    }
});

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

export function scVideoSource(href, origin = window.location.origin) {
    return sameOrigin(href, VIDEO_PATH, origin);
}

export function scUpgradeVideoLinks(root = document) {
    let count = 0;
    for (const link of root.querySelectorAll("a.o_fc_video")) {
        if (link.dataset.scVideoDone) {
            continue;
        }
        link.dataset.scVideoDone = "1";
        const src = scVideoSource(link.getAttribute("href") || "");
        if (!src) {
            continue; // not a same-origin attachment: the link stays a link
        }
        const video = document.createElement("video");
        video.className = "o_fc_video_player";
        video.controls = true;
        video.setAttribute("playsinline", "");
        video.preload = "metadata";
        video.src = src;
        const poster = link.dataset.poster && sameOrigin(link.dataset.poster, IMAGE_PATH, window.location.origin);
        if (poster) {
            video.poster = poster;
        }
        video.style.maxWidth = "100%";
        video.style.width = "420px";
        video.style.display = "block";
        link.before(video);
        count++;
    }
    return count;
}

function onKnowledgePage() {
    return window.location.pathname.startsWith("/knowledge/article/");
}

if (onKnowledgePage()) {
    // The public article may render after load: upgrade now and on changes.
    const start = () => {
        scUpgradeVideoLinks();
        let pending = false;
        new MutationObserver(() => {
            if (!pending) {
                pending = true;
                window.requestAnimationFrame(() => {
                    pending = false;
                    scUpgradeVideoLinks();
                });
            }
        }).observe(document.body, { childList: true, subtree: true });
    };
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
