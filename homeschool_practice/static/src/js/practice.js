/* Homeschool practice — the portal lesson screen (touch first, iPad).
 *
 * The server decides everything (what comes next, right or wrong, XP, quests, rewards);
 * this screen shows an item and sends back the answer with two silent timings measured
 * from the moment the item is on screen: the first touch and the submit. No clock, no
 * countdown, no speed is ever shown. Plain script (no build step), Safari on iPadOS 17+. */
(function () {
    "use strict";
    var API = "/my/homeschool/practice/api";
    var PENDING = "hp-pending-answer";
    var app = document.getElementById("app");
    var INPUT = window.matchMedia && window.matchMedia("(pointer: coarse)").matches ? "touch" : "mouse";
    var L = {};
    var state = { home: null, session: null, item: null, typed: "", shownAt: 0, firstTouch: null, hintUsed: false, busy: false };

    // ------------------------------------------------------------------ utils
    function esc(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }
    function h(html) { app.innerHTML = html; }
    function uuid() {
        if (window.crypto && crypto.randomUUID) { return crypto.randomUUID(); }
        return Date.now().toString(36) + Math.random().toString(36).slice(2);
    }
    function rpc(path, params) {
        return fetch(API + path, {
            method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} }),
        }).then(function (r) {
            if (!r.ok) { throw new Error("http " + r.status); }
            return r.json();
        }).then(function (j) {
            if (j.error) {
                var name = (j.error.data && j.error.data.name) || "";
                if (name.indexOf("SessionExpired") >= 0) { location.href = "/web/login?redirect=/my/homeschool/practice"; }
                var e = new Error(j.error.message || "error"); e.server = true; throw e;
            }
            return j.result;
        });
    }
    function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
    function banner(show) {
        var b = document.getElementById("hp-offline");
        if (show && !b) {
            b = document.createElement("div"); b.id = "hp-offline"; b.className = "hp-offline";
            b.textContent = L.offline || "…"; document.body.appendChild(b);
        } else if (!show && b) { b.remove(); }
    }
    /** Send an answer; on network failure keep it on the device and retry until it gets through
     *  (the server stores it once thanks to its client_uuid, with the device timestamp). */
    function sendAnswer(params) {
        try { localStorage.setItem(PENDING, JSON.stringify(params)); } catch (e) { /* private mode */ }
        var attempt = function (delay) {
            return rpc("/session/answer", params).then(function (res) {
                banner(false);
                try { localStorage.removeItem(PENDING); } catch (e) { /* ignore */ }
                return res;
            }, function (err) {
                if (err.server) { throw err; }
                banner(true);
                return sleep(delay).then(function () { return attempt(Math.min(delay * 2, 15000)); });
            });
        };
        return attempt(1500);
    }

    // ------------------------------------------------------------------ home
    function bar(value, max) {
        var pct = max > 0 ? Math.min(100, Math.round(100 * value / max)) : 0;
        return '<div class="hp-bar"><div class="hp-bar-fill" style="width:' + pct + '%"></div></div>';
    }
    function loadHome() {
        state.session = null;
        state.busy = false;
        return rpc("/home").then(function (data) {
            state.home = data; L = data.labels; renderHome();
        }, function () { h('<div class="hp-loading">' + esc(L.offline || "…") + "</div>"); setTimeout(loadHome, 4000); });
    }
    function renderHome() {
        var d = state.home;
        var into = d.xp - d.xp_level_start, span = d.xp_next_level - d.xp_level_start;
        var quests = d.quests.map(function (q) {
            var prog = q.target > 1 ? '<span class="hp-q-prog">' + q.progress + " / " + q.target + "</span>" : "";
            return '<button class="hp-quest' + (q.done ? " is-done" : "") + '" data-quest="' + q.id + '"' + (q.done ? " disabled" : "") + ">" +
                '<span class="hp-q-icon">' + (q.done ? "✅" : "🎯") + "</span>" +
                '<span class="hp-q-label">' + esc(q.label) + "</span>" + prog + bar(q.progress, q.target) + "</button>";
        }).join("");
        if (d.rest_day) { quests = '<p class="hp-rest">🌤️ ' + esc(L.rest_day) + "</p>"; }
        else if (!d.quests.length) { quests = '<p class="hp-rest">' + esc(L.nothing) + "</p>"; }
        var decks = d.decks.map(function (k) {
            return '<button class="hp-free" data-deck="' + k.id + '">▶ ' + esc(k.name) + "</button>";
        }).join("");
        var goals = ["day", "week", "month"].map(function (p) {
            var g = d.goals[p];
            return '<div class="hp-goal' + (g.reached ? " is-done" : "") + '"><span>' + esc(L[p]) + "</span>" +
                "<b>" + Math.min(g.value, g.target) + " / " + g.target + (g.reached ? " ✅" : "") + "</b>" + bar(g.value, g.target) + "</div>";
        }).join("");
        var bank = d.balances.length ? d.balances.map(function (b) {
            return '<div class="hp-bank-row"><span>' + esc(b.name) + "</span><b>" + fmt(b.balance) + " " + esc(b.unit) + "</b></div>";
        }).join("") : '<div class="hp-bank-row"><span>—</span></div>';
        var badges = d.badges.map(function (b) {
            return '<span class="hp-badge' + (b.new ? " is-new" : "") + '" title="' + esc(b.name) + '">' + esc(b.icon) +
                "<small>" + esc(b.name + (b.unit ? " · " + b.unit : "")) + "</small></span>";
        }).join("");
        h('<div class="hp-home">' +
            '<section class="hp-main">' +
                '<header class="hp-level"><div class="hp-level-num">' + esc(L.level) + " <b>" + d.level + "</b></div>" +
                '<div class="hp-level-xp">' + bar(into, span) + "<span>" + d.xp + " " + esc(L.xp) + "</span></div></header>" +
                "<h2>" + esc(L.quests) + "</h2>" + '<div class="hp-quests">' + quests + "</div>" +
                (decks ? '<h3>' + esc(L.free) + '</h3><div class="hp-decks">' + decks + "</div>" : "") +
            "</section>" +
            '<aside class="hp-side">' +
                '<div class="hp-card hp-bank"><h3>💰 ' + esc(L.bank) + "</h3>" + bank + "</div>" +
                '<div class="hp-card"><h3>🏁 ' + esc(L.goals) + "</h3>" + goals + "</div>" +
                '<div class="hp-card"><h3>🏅 ' + esc(L.badges) + " (" + d.badge_count + ')</h3><div class="hp-badges">' + (badges || "—") + "</div></div>" +
            "</aside></div>");
        app.querySelectorAll("[data-quest]").forEach(function (b) {
            b.addEventListener("click", function () { start({ quest_id: +b.dataset.quest }); });
        });
        app.querySelectorAll("[data-deck]").forEach(function (b) {
            b.addEventListener("click", function () {
                var deck = d.decks.filter(function (k) { return k.id === +b.dataset.deck; })[0];
                picker(deck);
            });
        });
        var fresh = d.badges.filter(function (b) { return b.new; });
        if (fresh.length) { celebrate([{ icon: fresh[0].icon, title: L.new_badge, text: fresh[0].name }]); }
    }
    function fmt(n) { return (Math.round(n * 100) / 100).toString(); }

    // ------------------------------------------------------------------ free practice: pick the units
    function picker(deck) {
        if (!deck.units || deck.units.length < 2) { start({ deck_id: deck.id }); return; }
        var key = "hp-pick-" + deck.id, ids = deck.units.map(function (u) { return u.id; }), chosen = ids.slice();
        try {
            var saved = JSON.parse(localStorage.getItem(key) || "null");
            if (saved) {
                saved = saved.filter(function (id) { return ids.indexOf(id) >= 0; });
                if (saved.length) { chosen = saved; }
            }
        } catch (e) { /* the remembered choice is a convenience only */ }
        var draw = function () {
            var all = chosen.length === ids.length;
            h('<div class="hp-pick"><header class="hp-pick-head"><button class="hp-free" id="hp-back">← ' + esc(L.home) + "</button>" +
                "<h2>" + esc(deck.name) + "</h2></header><p>" + esc(L.pick) + "</p>" +
                '<div class="hp-units"><button class="hp-unit hp-unit-all' + (all ? " is-on" : "") + '" data-all="1">' + esc(L.all) + "</button>" +
                deck.units.map(function (u) {
                    return '<button class="hp-unit' + (chosen.indexOf(u.id) >= 0 ? " is-on" : "") + '" data-unit="' + u.id + '">' + esc(u.name.charAt(0).toUpperCase() + u.name.slice(1)) + "</button>";
                }).join("") + "</div>" +
                '<button class="hp-big" id="hp-go"' + (chosen.length ? "" : " disabled") + ">" + esc(L.start) + "</button></div>");
            app.querySelectorAll("[data-unit]").forEach(function (b) {
                b.addEventListener("click", function () {
                    var id = +b.dataset.unit, at = chosen.indexOf(id);
                    if (at >= 0) { chosen.splice(at, 1); } else { chosen.push(id); }
                    draw();
                });
            });
            app.querySelector("[data-all]").addEventListener("click", function () { chosen = all ? [] : ids.slice(); draw(); });
            document.getElementById("hp-back").addEventListener("click", renderHome);
            document.getElementById("hp-go").addEventListener("click", function () {
                if (!chosen.length) { return; }
                try { localStorage.setItem(key, JSON.stringify(chosen)); } catch (e) { /* ignore */ }
                start({ deck_id: deck.id, unit_ids: chosen.slice() });
            });
        };
        draw();
    }

    // ------------------------------------------------------------------ lesson
    function start(params) {
        if (state.busy) { return; }
        state.busy = true;
        params.input_type = INPUT;
        params.device = (navigator.userAgent || "").slice(0, 120);
        params.frontend = "portal_lesson";
        rpc("/session/start", params).then(function (res) {
            state.busy = false;
            state.session = res.session_id;
            state.held = [];
            if (!res.item) { finish(); return; }
            showItem(res.item);
        }, function () { state.busy = false; });
    }
    function showItem(item) {
        state.item = item; state.typed = ""; state.firstTouch = null; state.hintUsed = false; state.busy = false;
        if (item.first_time && item.intro) {
            h('<div class="hp-intro"><div class="hp-intro-card"><h2>✨ ' + esc(L.new_unit) + "</h2><h3>" + esc(item.unit) + "</h3><p>" +
                esc(item.intro) + '</p><button class="hp-big" id="hp-intro-ok">' + esc(L.got_it) + "</button></div></div>");
            document.getElementById("hp-intro-ok").addEventListener("click", function () { item.first_time = false; showItem(item); });
            return;
        }
        var dots = "";
        for (var i = 1; i <= item.total; i++) { dots += '<i class="' + (i < item.index ? "is-past" : i === item.index ? "is-now" : "") + '"></i>'; }
        var pad;
        if (item.answer_mode === "choices") {
            pad = '<div class="hp-choices">' + item.choices.map(function (c) {
                return '<button class="hp-choice" data-choice="' + esc(c) + '">' + esc(c) + "</button>";
            }).join("") + "</div>";
        } else {
            var keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "✓"];
            pad = '<div class="hp-keypad">' + keys.map(function (k) {
                var cls = k === "✓" ? "hp-key is-ok" : k === "⌫" ? "hp-key is-erase" : "hp-key";
                var label = k === "✓" ? esc(L.check) : k === "⌫" ? "⌫" : k;
                return '<button class="' + cls + '" data-key="' + k + '" aria-label="' + (k === "⌫" ? esc(L.erase) : label) + '">' + label + "</button>";
            }).join("") + "</div>";
        }
        h('<div class="hp-lesson">' +
            '<header class="hp-top"><button class="hp-close" id="hp-quit" aria-label="' + esc(L.home) + '">✕</button><div class="hp-dots">' + dots + "</div></header>" +
            '<div class="hp-stage">' +
                '<div class="hp-question"><div class="hp-prompt">' + esc(item.prompt) + "</div>" +
                    (item.answer_mode === "keypad" ? '<div class="hp-typed" id="hp-typed">&nbsp;</div>' : "") +
                    (item.hint ? '<button class="hp-hint" id="hp-hint">💡 ' + esc(L.hint) + "</button>" : "") +
                    '<div class="hp-hint-text" id="hp-hint-text"></div>' +
                "</div>" + '<div class="hp-input">' + pad + "</div>" +
            "</div>" + '<div class="hp-feedback" id="hp-feedback"></div></div>');
        var input = app.querySelector(".hp-input");
        input.addEventListener("pointerdown", function () {
            if (state.firstTouch === null && state.shownAt) { state.firstTouch = Math.round(performance.now() - state.shownAt); }
        }, { capture: true });
        app.querySelectorAll("[data-key]").forEach(function (b) {
            b.addEventListener("click", function () { key(b.dataset.key); });
        });
        app.querySelectorAll("[data-choice]").forEach(function (b) {
            b.addEventListener("click", function () { submit(b.dataset.choice, b); });
        });
        var hb = document.getElementById("hp-hint");
        if (hb) {
            hb.addEventListener("click", function () {
                state.hintUsed = true; hb.disabled = true;
                document.getElementById("hp-hint-text").textContent = item.hint;
            });
        }
        document.getElementById("hp-quit").addEventListener("click", quit);
        state.shownAt = 0;
        requestAnimationFrame(function () { requestAnimationFrame(function () { state.shownAt = performance.now(); }); });
    }
    function key(k) {
        if (state.busy) { return; }
        if (k === "⌫") { state.typed = state.typed.slice(0, -1); }
        else if (k === "✓") { if (state.typed) { submit(state.typed); } return; }
        else if (state.typed.length < 6) { state.typed += k; }
        document.getElementById("hp-typed").innerHTML = state.typed ? esc(state.typed) : "&nbsp;";
    }
    function submit(given, btn) {
        if (state.busy) { return; }
        state.busy = true;
        var now = performance.now();
        var item = state.item;
        var submitMs = state.shownAt ? Math.round(now - state.shownAt) : 0;
        if (state.firstTouch === null) { state.firstTouch = submitMs; }
        if (btn) { btn.classList.add("is-picked"); }
        sendAnswer({
            session_id: state.session, item_id: item.item_id, given: given, hint_used: state.hintUsed,
            first_touch_ms: state.firstTouch, submit_ms: submitMs,
            client_ts: new Date().toISOString(), client_uuid: uuid(),
        }).then(function (res) { feedback(res); }, function () { state.busy = false; });
    }
    function eventsToCelebrations(res) {
        var out = [];
        (res.quests_done || []).forEach(function (q) { out.push({ icon: "🎯", title: L.quest_done, text: q }); });
        (res.goals_reached || []).forEach(function (p) { out.push({ icon: "🏁", title: L["goal_" + p], text: "" }); });
        (res.rewards || []).forEach(function (r) { out.push({ icon: "💰", title: L.reward, text: "+" + fmt(r.amount) + " " + r.unit + " · " + r.name }); });
        if (res.level_up) { out.push({ icon: "⬆️", title: L.level_up, text: L.level + " " + res.level_up.to }); }
        (res.units_unlocked || []).forEach(function (u) { out.push({ icon: "🔓", title: L.unit_unlocked, text: u }); });
        (res.badges || []).forEach(function (b) { out.push({ icon: b.icon, title: L.new_badge, text: b.name + (b.unit ? " · " + b.unit : "") }); });
        return out;
    }
    function feedback(res) {
        if (res.error === "stale") {
            if (res.done || !res.item) { finish(); } else { showItem(res.item); }
            return;
        }
        var fb = document.getElementById("hp-feedback");
        var xp = res.xp ? '<span class="hp-xp">+' + res.xp + " " + esc(L.xp) + "</span>" : "";
        // Celebrations earned mid-lesson are held for the end of the lesson: nothing interrupts the practice.
        hold(eventsToCelebrations(res));
        var next = function () {
            if (res.done) { summary(res.summary); } else { showItem(res.next); }
        };
        if (res.correct) {
            fb.className = "hp-feedback is-good";
            fb.innerHTML = "<b>" + esc(L.great) + "</b>" + xp;
            setTimeout(next, 650);
        } else {
            fb.className = "hp-feedback is-miss";
            fb.innerHTML = "<div><b>" + esc(L.almost) + "</b> " + esc(L.answer_is) + " <strong>" + esc(res.expected) + "</strong>" +
                (res.hint ? '<div class="hp-fb-hint">💡 ' + esc(res.hint) + "</div>" : "") + "</div>" + xp +
                '<button class="hp-big" id="hp-next">' + esc(L.continue) + "</button>";
            document.getElementById("hp-next").addEventListener("click", next);
        }
    }
    function hold(list) {
        state.held = state.held || [];
        list.forEach(function (c) {
            var dup = state.held.some(function (o) { return o.title === c.title && o.text === c.text; });
            if (!dup) { state.held.push(c); }
        });
    }
    function release() {
        var list = state.held || []; state.held = [];
        return celebrate(list);
    }
    function celebrate(list) {
        if (!list.length) { return Promise.resolve(); }
        return new Promise(function (resolve) {
            var i = 0;
            var layer = document.createElement("div"); layer.className = "hp-celebrate"; document.body.appendChild(layer);
            var show = function () {
                if (i >= list.length) { layer.remove(); resolve(); return; }
                var c = list[i++];
                var bits = "";
                for (var k = 0; k < 18; k++) { bits += '<i style="--x:' + (Math.random() * 100) + "%;--d:" + (Math.random() * 0.6) + "s;--r:" + Math.round(Math.random() * 360) + 'deg"></i>'; }
                layer.innerHTML = '<div class="hp-confetti">' + bits + '</div><div class="hp-cel-card"><div class="hp-cel-icon">' + esc(c.icon) + "</div><h2>" + esc(c.title) + "</h2><p>" + esc(c.text) + '</p><button class="hp-big">' + esc(L.continue) + "</button></div>";
                layer.querySelector("button").addEventListener("click", show);
            };
            show();
        });
    }
    function summary(s) {
        s = s || {};
        h('<div class="hp-summary"><div class="hp-cel-icon">🎉</div><h1>' + esc(L.session_done) + "</h1>" +
            "<p>" + esc(L.well_done) + "</p>" +
            '<div class="hp-sum-stats"><div><b>' + (s.answers || 0) + "</b><span>" + esc(L.answers) + "</span></div>" +
            "<div><b>" + (s.correct || 0) + "</b><span>" + esc(L.correct) + "</span></div>" +
            "<div><b>+" + (s.xp_session || 0) + "</b><span>" + esc(L.xp) + "</span></div></div>" +
            '<button class="hp-big" id="hp-home">' + esc(L.home) + "</button></div>");
        hold(eventsToCelebrations(s));
        release();
        document.getElementById("hp-home").addEventListener("click", loadHome);
    }
    function finish() {
        rpc("/session/finish", { session_id: state.session }).then(function (res) { summary(res.summary); }, loadHome);
    }
    function quit() {
        var home = function () { release().then(loadHome); };
        if (state.session) { rpc("/session/finish", { session_id: state.session }).then(home, home); } else { home(); }
    }

    // ------------------------------------------------------------------ boot
    document.addEventListener("gesturestart", function (e) { e.preventDefault(); });
    var pending = null;
    try { pending = JSON.parse(localStorage.getItem(PENDING) || "null"); } catch (e) { pending = null; }
    if (pending) {
        sendAnswer(pending).then(loadHome, loadHome);
    } else {
        loadHome();
    }
})();
