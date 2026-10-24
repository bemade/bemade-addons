/*
 * Task 1660 — the guide-video link upgrade (sc_help.js), exercised on an
 * injected fragment: Knowledge itself is not installed on the addon CI.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

tours.add("sc_1660_video_links", {
    steps: () => [
        {
            content: "Same-origin attachment → inline player; anything else stays a link",
            trigger: ".o_sc_app",
            run() {
                const mod = odoo.loader.modules.get("@bemade_sports_clinic/js/sc_help");
                assert(mod && mod.scUpgradeVideoLinks, "sc_help module not loaded");
                const box = document.createElement("div");
                box.innerHTML = [
                    '<p><a class="o_fc_video" id="v_ok" href="/web/content/12345/guide.mp4">Video</a></p>',
                    '<p><a class="o_fc_video" id="v_abs" href="' + window.location.origin + '/web/content/7?download=0">Video</a></p>',
                    '<p><a class="o_fc_video" id="v_ext" href="https://evil.example.com/web/content/1/x.mp4">Video</a></p>',
                    '<p><a class="o_fc_video" id="v_js" href="javascript:alert(1)">Video</a></p>',
                    '<p><a class="o_fc_video" id="v_other" href="/my/home">Video</a></p>',
                    '<p><a id="v_plain" href="/web/content/9/x.mp4">Not marked</a></p>',
                ].join("");
                document.body.appendChild(box);
                const count = mod.scUpgradeVideoLinks(box);
                assert(count === 2, `expected 2 players, got ${count}`);
                const ok = box.querySelector("#v_ok").previousElementSibling;
                assert(ok && ok.tagName === "VIDEO" && ok.controls, "no <video controls> before the link");
                assert(ok.hasAttribute("playsinline"), "no playsinline");
                assert(ok.getAttribute("src") === "/web/content/12345/guide.mp4", ok.getAttribute("src"));
                assert(box.querySelector("#v_abs").previousElementSibling.tagName === "VIDEO", "absolute same-origin refused");
                for (const id of ["v_ext", "v_js", "v_other", "v_plain"]) {
                    const prev = box.querySelector("#" + id).previousElementSibling;
                    assert(!prev || prev.tagName !== "VIDEO", `${id} became a video`);
                }
                assert(box.querySelectorAll("video").length === 2, "stray video elements");
                // Idempotent.
                assert(mod.scUpgradeVideoLinks(box) === 0, "upgraded twice");
                box.remove();
            },
        },
    ],
});
