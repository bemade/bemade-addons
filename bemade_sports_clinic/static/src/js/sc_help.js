/*
 * Task 1660 — in-app help.
 *
 * 1. The app bar « ? » follows the page's segmented tab: on a tab switch its
 *    href becomes the article of « <page>.<tab> », else « <page> », else the
 *    guide home (the mapping is rendered on the link, data-sc-help-map).
 * 2. Guide videos on the Knowledge pages: see sc_guide_video.js.
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
