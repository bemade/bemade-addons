/*
 * Task 1728 — the in-app daily digest reads in both themes
 * (tests/test_digest_dark_mode_tours_1728.py, phone 390 px). Every muted
 * line of the digest (training recommendation, « Retour prévu » and its
 * « · Dépassé », injury meta lines, « Show details », the snapshot line)
 * must reach 4.5:1 against its own background. Language-independent
 * triggers only.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");
const MIN = 4.5;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function rgb(value) {
    const m = (value || "").match(/rgba?\(([^)]+)\)/);
    if (!m) {
        return null;
    }
    const [r, g, b, a] = m[1].split(",").map((v) => parseFloat(v));
    return { r, g, b, a: a === undefined ? 1 : a };
}

// Alpha-composite the backgrounds up the tree onto the page (opaque) one.
function background(el) {
    const layers = [];
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
        const c = rgb(getComputedStyle(node).backgroundColor);
        if (c && c.a > 0) {
            layers.push(c);
            if (c.a >= 1) {
                break;
            }
        }
    }
    let out = { r: 255, g: 255, b: 255 };
    for (const c of layers.reverse()) {
        out = {
            r: c.r * c.a + out.r * (1 - c.a),
            g: c.g * c.a + out.g * (1 - c.a),
            b: c.b * c.a + out.b * (1 - c.a),
        };
    }
    return out;
}

// The text colour composited onto its background (rgba muted greys).
function foreground(el, bg) {
    const c = rgb(getComputedStyle(el).color);
    return {
        r: c.r * c.a + bg.r * (1 - c.a),
        g: c.g * c.a + bg.g * (1 - c.a),
        b: c.b * c.a + bg.b * (1 - c.a),
    };
}

function luminance({ r, g, b }) {
    const lin = (v) => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(el) {
    const bg = background(el);
    const fg = luminance(foreground(el, bg));
    const lb = luminance(bg);
    return (Math.max(fg, lb) + 0.05) / (Math.min(fg, lb) + 0.05);
}

function checkAll(root) {
    const groups = {
        "training recommendation": ".team-digest .card-body > .text-muted .fa-heartbeat + span",
        "Retour prévu": ".team-digest .card-body > .text-muted .fa-clock-o + span",
        "Dépassé": ".team-digest .o_sc_overdue",
        "Show details": ".team-digest .o_sc_card_summary .o_sc_summary_more",
        "injury meta": ".team-digest .o_sc_injury_detail .text-muted",
        "snapshot line": '[data-sc-section="digest.snapshot"]',
    };
    const failures = [];
    for (const [label, selector] of Object.entries(groups)) {
        const nodes = [...root.querySelectorAll(selector)];
        assert(nodes.length, `nothing matched for ${label} (${selector})`);
        for (const node of nodes) {
            const ratio = contrast(node);
            if (ratio < MIN) {
                failures.push(
                    `${label}: ${ratio.toFixed(2)}:1 (${getComputedStyle(node).color} on ${JSON.stringify(background(node))})`
                );
            }
        }
    }
    assert(!failures.length, `low contrast — ${failures.join(" | ")}`);
}

const OPEN_DETAILS = (root) =>
    root.querySelectorAll("details.o_sc_card_detail").forEach((d) => (d.open = true));

tours.add("sc_1728_digest_contrast", {
    steps: () => [
        {
            content: "The day's digest renders in the shell",
            trigger: '.o_sc_app [data-sc-section="digest.body"] .team-digest .card',
            run() {
                const root = document.querySelector(".o_sc_app");
                OPEN_DETAILS(root);
                checkAll(root);
            },
        },
    ],
});

const ROW = '[data-sc-section="digest.history"] details[data-sc-digest-row]';

tours.add("sc_1728_digest_history_contrast", {
    steps: () => [
        {
            content: "History: the first date expands in place",
            trigger: `${ROW}:first-child > summary`,
            run: "click",
        },
        {
            content: "The inline body reads in the dark theme",
            trigger: `${ROW}[open] .o_sc_lazy_body .team-digest .card`,
            run() {
                const row = document.querySelector(`${ROW}[open]`);
                OPEN_DETAILS(row);
                checkAll(row);
            },
        },
    ],
});
