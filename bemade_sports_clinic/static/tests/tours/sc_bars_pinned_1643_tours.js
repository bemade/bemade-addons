/*
 * Task 1643 — in the mobile BROWSER (not the installed app) the app bar and
 * the bottom tabs stay pinned while the page scrolls
 * (tests/test_bars_pinned_tours_1643.py, phone 390 px).
 *
 * The window must be the only scroller: no ancestor of the bars may scroll,
 * clip-scroll, or carry a transform / filter / contain / will-change (each
 * breaks « sticky » or re-bases « fixed »). After scrolling the window by
 * 600 px, the app bar's top is 0 and the tabs' bottom is the viewport's.
 *
 * Headless Chrome is not iOS WebKit with a collapsing address bar —
 * UNVERIFIED until the /dev-review iPhone check.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** The ancestors of ``el`` (up to <html>) that break sticky / fixed. */
function offenders(el) {
    const found = [];
    for (let node = el.parentElement; node; node = node.parentElement) {
        const style = getComputedStyle(node);
        const name = node.id ? `#${node.id}` : `${node.tagName.toLowerCase()}.${[...node.classList].join(".")}`;
        const scrolls = ["auto", "scroll", "hidden"].some(
            (v) => style.overflowY === v || style.overflowX === v
        );
        // <html> / <body> overflow propagates to the viewport: harmless.
        if (scrolls && node !== document.documentElement && node !== document.body) {
            found.push(`${name} overflow ${style.overflowX}/${style.overflowY}`);
        }
        if (node === document.body && scrolls && getComputedStyle(document.documentElement).overflowY !== "visible") {
            found.push("body overflow with html overflow: body becomes the scroller");
        }
        for (const prop of ["transform", "filter", "perspective"]) {
            if (style[prop] && style[prop] !== "none") {
                found.push(`${name} ${prop} ${style[prop]}`);
            }
        }
        if (style.contain && !["none", ""].includes(style.contain)) {
            found.push(`${name} contain ${style.contain}`);
        }
        if (style.willChange && !["auto", ""].includes(style.willChange)) {
            found.push(`${name} will-change ${style.willChange}`);
        }
    }
    return found;
}

tours.add("sc_1643_bars_pinned", {
    steps: () => [
        {
            content: "Make the page long, scroll the WINDOW, the bars stay put",
            trigger: ".o_sc_app .o_sc_appbar",
            async run() {
                const bar = document.querySelector(".o_sc_appbar");
                const tabs = document.querySelector(".o_sc_tabs");
                assert(tabs && tabs.getClientRects().length, "no bottom tabs at phone width");
                const bad = [...offenders(bar), ...offenders(tabs)];
                assert(!bad.length, `ancestors break sticky / fixed: ${[...new Set(bad)].join("; ")}`);
                const content = document.querySelector(".o_sc_content");
                content.style.paddingBottom = "4000px";
                await sleep(50);
                window.scrollTo(0, 600);
                await sleep(100);
                const root = document.scrollingElement;
                assert(root.scrollTop >= 590, `the window did not scroll: ${root.scrollTop}`);
                const wrap = document.getElementById("wrapwrap");
                assert(!wrap || wrap.scrollTop === 0, `#wrapwrap scrolls: ${wrap && wrap.scrollTop}`);
                const barRect = bar.getBoundingClientRect();
                assert(Math.abs(barRect.top) <= 1, `the app bar moved: top=${barRect.top}`);
                const tabsRect = tabs.getBoundingClientRect();
                assert(Math.abs(tabsRect.bottom - window.innerHeight) <= 1,
                    `the tabs moved: bottom=${tabsRect.bottom} / ${window.innerHeight}`);
                // The frontend layout's html / body « height: 100% » is lifted.
                for (const node of [document.documentElement, document.body]) {
                    const height = node.getBoundingClientRect().height;
                    assert(height > window.innerHeight + 500,
                        `${node.tagName} stays viewport-sized (${height}px): the window is not its scroller`);
                }
                const viewport = document.querySelector('meta[name="viewport"]');
                assert(viewport && viewport.content.includes("viewport-fit=cover"), "viewport-fit=cover missing");
                assert(document.querySelectorAll('meta[name="viewport"]').length === 1,
                    `${document.querySelectorAll('meta[name="viewport"]').length} viewport metas`);
            },
        },
    ],
});

// Task 1643 addendum: a neutralized DB's banner never covers the tabs.
tours.add("sc_1643_ribbon", {
    steps: () => [
        {
            content: "The banner is pinned at the bottom, the tabs sit right above it",
            trigger: ".o_sc_app .o_sc_tabs",
            async run() {
                const banner = document.getElementById("oe_neutralize_banner");
                assert(banner, "no neutralize banner rendered");
                await sleep(100);
                const b = banner.getBoundingClientRect();
                const t = document.querySelector(".o_sc_tabs").getBoundingClientRect();
                assert(b.height > 0 && Math.abs(b.bottom - window.innerHeight) <= 1,
                    `the banner is not at the bottom: ${b.top}-${b.bottom} / ${window.innerHeight}`);
                assert(t.bottom <= b.top + 1, `the banner covers the tabs: tabs ${t.top}-${t.bottom}, banner ${b.top}`);
                assert(t.top > 0 && t.height > 40, "the tabs are squeezed");
            },
        },
    ],
});
