/*
 * Task 1660 — the guide-video link upgrade (sc_guide_video.js).
 *
 * sc_1660_video_links: exercised on an injected fragment (runs without
 * Knowledge, e.g. on the addon CI); the attachment ids come from the start
 * URL (?video=<id>&text=<id>).
 * sc_1660_knowledge_video: the real /knowledge/article/<id> page, logged out
 * (public frontend layout) or as a portal user (Knowledge's portal web
 * client) — runs only where website_knowledge is installed.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function isPlayer(el) {
    return Boolean(
        el &&
            el.tagName === "VIDEO" &&
            el.classList.contains("o_fc_video_player") &&
            el.controls &&
            el.hasAttribute("playsinline")
    );
}

tours.add("sc_1660_video_links", {
    steps: () => [
        {
            content: "Same-origin video attachment → inline player; anything else stays a link",
            trigger: ".o_sc_app",
            async run() {
                const mod = odoo.loader.modules.get("@bemade_sports_clinic/js/sc_guide_video");
                assert(mod && mod.scUpgradeVideoLinks, "sc_guide_video module not loaded");
                const params = new URLSearchParams(window.location.search);
                const video = params.get("video");
                const text = params.get("text");
                assert(video && text, "start URL without ?video=&text=");
                const origin = window.location.origin;
                const box = document.createElement("div");
                box.innerHTML = [
                    `<p><a class="o_fc_video" id="v_ok" href="/web/content/${video}">Video</a></p>`,
                    `<p><a class="o_fc_video" id="v_abs" href="${origin}/web/content/${video}?download=0">Video</a></p>`,
                    `<p><a class="o_fc_video" id="v_text" href="/web/content/${text}">Not a video</a></p>`,
                    `<p><a class="o_fc_video" id="v_ext" href="https://evil.example.com/web/content/${video}">Video</a></p>`,
                    '<p><a class="o_fc_video" id="v_js" href="javascript:alert(1)">Video</a></p>',
                    '<p><a class="o_fc_video" id="v_other" href="/my/home">Video</a></p>',
                    `<p><a id="v_plain" href="/web/content/${video}">Not marked</a></p>`,
                    `<div contenteditable="true"><a class="o_fc_video" id="v_edit" href="/web/content/${video}">Being edited</a></div>`,
                ].join("");
                document.body.appendChild(box);
                const count = await mod.scUpgradeVideoLinks(box);
                assert(count === 2, `expected 2 players, got ${count}`);
                const okLink = box.querySelector("#v_ok");
                const ok = okLink.previousElementSibling;
                assert(isPlayer(ok), "no <video controls playsinline> before the link");
                assert(ok.getAttribute("src") === `/web/content/${video}`, ok.getAttribute("src"));
                assert(okLink.hidden, "the link is not hidden under the player");
                assert(isPlayer(box.querySelector("#v_abs").previousElementSibling), "absolute same-origin refused");
                for (const id of ["v_text", "v_ext", "v_js", "v_other", "v_plain", "v_edit"]) {
                    const link = box.querySelector("#" + id);
                    const prev = link.previousElementSibling;
                    assert(!prev || prev.tagName !== "VIDEO", `${id} became a video`);
                    assert(!link.hidden, `${id} was hidden`);
                }
                assert(box.querySelectorAll("video").length === 2, "stray video elements");
                // Idempotent.
                assert((await mod.scUpgradeVideoLinks(box)) === 0, "upgraded twice");
                box.remove();
            },
        },
    ],
});

tours.add("sc_1660_knowledge_video", {
    steps: () => [
        {
            content: "The guide article's video link became an inline player",
            trigger: "video.o_fc_video_player",
            run() {
                const players = document.querySelectorAll("video.o_fc_video_player");
                assert(players.length === 1, `expected 1 player, got ${players.length}`);
                const player = players[0];
                assert(isPlayer(player), "not a <video controls playsinline>");
                const link = player.nextElementSibling;
                assert(link && link.id === "fc_vid_ok", "the player is not before the video link");
                assert(player.getAttribute("src") === link.getAttribute("href"), "player src");
                assert(link.hidden, "the link is not hidden under the player");
                for (const id of ["fc_vid_text", "fc_vid_ext"]) {
                    const other = document.getElementById(id);
                    assert(other, `${id} missing from the article`);
                    const prev = other.previousElementSibling;
                    assert(!prev || prev.tagName !== "VIDEO", `${id} became a video`);
                    assert(!other.hidden, `${id} was hidden`);
                }
            },
        },
    ],
});
