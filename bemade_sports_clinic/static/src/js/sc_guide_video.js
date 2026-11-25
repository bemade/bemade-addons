/*
 * Task 1660 — guide videos on the Knowledge user-guide pages.
 *
 * Task 5200 (kit P5): the player is the kit's (pk_guide_video.js: the links
 * « o_pk_video » and, for the articles already written, « o_fc_video »). The
 * Knowledge pages render their article after load (the public sidebar
 * navigation, the portal web client): this starts the kit's watcher on them.
 *
 * The page a logged-in PORTAL user sees at /knowledge/article/<id> is
 * Knowledge's portal web client (bundle knowledge.webclient, built on
 * web.assets_backend) — not the public frontend layout. This file and the
 * kit's module are therefore listed in BOTH web.assets_frontend (anonymous
 * visitors) and knowledge.webclient (portal users).
 */
import { pkWatchVideoLinks } from "@bemade_portal_kit/js/pk_guide_video";

// /knowledge/… with an optional website language prefix (/fr/…, /fr_CA/…).
const KNOWLEDGE_PATH = /^(\/[a-z]{2}(_[A-Za-z]{2,4})?)?\/knowledge\//;

export function scOnKnowledgePage(pathname = window.location.pathname) {
    return KNOWLEDGE_PATH.test(pathname);
}

function start() {
    pkWatchVideoLinks(scOnKnowledgePage);
}

if (scOnKnowledgePage()) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
}
