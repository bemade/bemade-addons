/*
 * Task 1660 / 5200 (kit P5) — in-app help: the app bar « ? »
 * (a[data-pk-help], rendered by the layout from the page's help values,
 * portal.kit.help) follows the page's segmented tab.
 *
 * The link carries the page's help key (data-pk-help-key), its base key
 * (data-pk-help-base), the guide home (data-pk-help-home) and the mapping of
 * the available articles (data-pk-help-map, JSON {key: url}). When the page's
 * key is refined by its tab (data-pk-help-tabbed="1": the base is one of
 * portal.kit._pk_help_tabbed()), a tab switch points the link at the
 * article of « <base>.<tab> », else « <base> », else the guide home.
 */

export function pkHelpUrlFor(link, tab) {
    let map = {};
    try {
        map = JSON.parse(link.dataset.pkHelpMap || "{}");
    } catch {
        map = {};
    }
    const base = link.dataset.pkHelpBase || "";
    const key = tab ? `${base}.${tab}` : base;
    return map[key] || map[base] || link.dataset.pkHelpHome || link.getAttribute("href");
}

document.addEventListener("click", (ev) => {
    const tab = ev.target.closest && ev.target.closest("[data-pk-tabs] a[data-pk-tab]");
    if (!tab) {
        return;
    }
    const link = document.querySelector(".o_pk_app a[data-pk-help]");
    if (!link || !link.dataset.pkHelpTabbed) {
        return;
    }
    const url = pkHelpUrlFor(link, tab.dataset.pkTab);
    if (url) {
        link.setAttribute("href", url);
        link.dataset.pkHelpKey = `${link.dataset.pkHelpBase}.${tab.dataset.pkTab}`;
    }
});
