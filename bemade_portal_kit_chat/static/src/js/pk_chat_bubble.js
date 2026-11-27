/*
 * Task 5516 — the app bar's chat bubble: the unread badge, the dropdown
 * of conversations, « New conversation » (a contact picker: the kit's
 * pk_picker), the floating window, the inline blocks, and the live updates.
 *
 * Live: Odoo's bus_service is only a « something changed in channel X »
 * signal (discuss.channel/new_message, discuss.channel/joined); the client
 * then refetches from the kit routes. The bus is started here (a portal
 * page does not start it). While it is not connected, a poll (the
 * pk_live_count style: 20 s, backoff on errors, paused while the tab is
 * hidden) refreshes the badge and the open thread.
 *
 * Markers: [data-pk-chat-bubble], -toggle, -badge, -menu, -list, -new,
 * -picker; [data-pk-chat-window] (pk_chat_window.js); [data-pk-chat-block]
 * (pk_chat_block.js, the same thread inline).
 */
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";
import { enhance } from "@bemade_portal_kit/js/pk_picker";

import { PK_CHAT_EVENT, ChatThread, chatApi, chatTexts } from "@bemade_portal_kit_chat/js/pk_chat_client";
import { ChatWindow } from "@bemade_portal_kit_chat/js/pk_chat_window";

const POLL_MS = 20000;
const MAX_BACKOFF = 300000;

/** The badge: the count, hidden at 0. */
export function applyBadge(badge, count) {
    const value = Number.isInteger(count) ? count : 0;
    badge.textContent = value > 99 ? "99+" : String(value);
    badge.hidden = value <= 0;
}

/** The dropdown's rows. */
export function renderConversations(list, rows, texts) {
    list.innerHTML = "";
    if (!rows.length) {
        const empty = document.createElement("p");
        empty.className = "o_pk_chat_empty";
        empty.textContent = texts.noConversations || "";
        list.append(empty);
        return;
    }
    for (const row of rows) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `o_pk_chat_row${row.unread ? " o_pk_chat_row_unread" : ""}`;
        button.dataset.pkChatOpen = String(row.id);
        button.dataset.pkChatKind = row.kind;
        const avatar = document.createElement("img");
        avatar.className = "o_pk_chat_avatar";
        avatar.alt = "";
        avatar.src = row.avatar_url;
        avatar.loading = "lazy";
        const text = document.createElement("span");
        text.className = "o_pk_chat_row_text";
        const title = document.createElement("strong");
        title.className = "o_pk_chat_row_title";
        title.textContent = row.title;
        const preview = document.createElement("span");
        preview.className = "o_pk_chat_row_preview";
        preview.textContent = row.preview;
        text.append(title, preview);
        const meta = document.createElement("span");
        meta.className = "o_pk_chat_row_meta";
        const when = document.createElement("time");
        when.textContent = row.when;
        meta.append(when);
        if (row.unread) {
            const count = document.createElement("span");
            count.className = "o_pk_chat_badge";
            count.textContent = String(row.unread);
            meta.append(count);
        }
        button.append(avatar, text, meta);
        list.append(button);
    }
}

export class PkChatBubble extends Interaction {
    static selector = ".o_pk_app [data-pk-chat-bubble]";

    setup() {
        this.api = chatApi;
        this.texts = chatTexts();
        this.texts.noConversations = this.el.dataset.pkChatEmpty || "";
        this.toggleEl = this.el.querySelector("[data-pk-chat-toggle]");
        this.badge = this.el.querySelector("[data-pk-chat-badge]");
        this.menu = this.el.querySelector("[data-pk-chat-menu]");
        this.list = this.el.querySelector("[data-pk-chat-list]");
        this.pickerHost = this.el.querySelector("[data-pk-chat-picker]");
        const host = document.querySelector("[data-pk-chat-window]");
        this.window = host
            ? new ChatWindow(host, {
                  api: this.api,
                  texts: this.texts,
                  onBack: () => this.openMenu(),
                  onRead: (count) => this.setCount(count),
              })
            : null;
        this.blocks = [];
        this.interval = POLL_MS;
        this.timer = null;
        this.busConnected = false;
    }

    start() {
        this.addListener(this.toggleEl, "click", () => (this.menu.hidden ? this.openMenu() : this.closeMenu()));
        this.addListener(this.list, "click", (ev) => {
            const row = ev.target.closest("[data-pk-chat-open]");
            if (row) {
                this.closeMenu();
                this.openConversation(row.dataset.pkChatOpen).catch(() => {});
            }
        });
        this.addListener(this.el.querySelector("[data-pk-chat-new]"), "click", () =>
            this.showPicker().catch(() => {})
        );
        this.addListener(document, "click", (ev) => {
            // A click in the window (its back arrow opens this menu) is not
            // a click outside.
            if (!this.menu.hidden && !this.el.contains(ev.target) && !ev.target.closest("[data-pk-chat-window]")) {
                this.closeMenu();
            }
        });
        this.addListener(document, "keydown", (ev) => {
            if (ev.key === "Escape" && !this.menu.hidden) {
                this.closeMenu();
            }
        });
        this.addListener(document, PK_CHAT_EVENT, () => this.refreshCount());
        this.addListener(window, "pagehide", () => {
            this.leaving = true;
            clearTimeout(this.timer);
        });
        this.addListener(document, "visibilitychange", () => {
            if (document.visibilityState === "visible") {
                this.schedule(0);
            }
        });
        for (const blockEl of document.querySelectorAll(".o_pk_app [data-pk-chat-block]")) {
            const thread = new ChatThread(blockEl, parseInt(blockEl.dataset.pkChatBlock, 10), {
                api: this.api,
                texts: this.texts,
                onRead: (count) => this.setCount(count),
            });
            this.blocks.push(thread);
            thread.load().catch(() => {});
        }
        this.startBus();
        this.refreshCount();
        if (this.window) {
            this.window.restore().catch(() => {});
        }
        this.schedule();
    }

    destroy() {
        clearTimeout(this.timer);
        const bus = this.services && this.services.bus_service;
        if (bus && this.onBusMessage) {
            bus.unsubscribe("discuss.channel/new_message", this.onBusMessage);
            bus.unsubscribe("discuss.channel/joined", this.onBusJoined);
        }
    }

    // ------------------------------------------------------------------
    // Live updates
    // ------------------------------------------------------------------
    startBus() {
        const bus = this.services && this.services.bus_service;
        if (!bus) {
            return;
        }
        this.onBusMessage = (payload) => this.channelChanged(payload && payload.id).catch(() => {});
        this.onBusJoined = () => this.refreshCount();
        bus.subscribe("discuss.channel/new_message", this.onBusMessage);
        bus.subscribe("discuss.channel/joined", this.onBusJoined);
        if (bus.addEventListener) {
            bus.addEventListener("BUS:CONNECT", () => (this.busConnected = true));
            bus.addEventListener("BUS:RECONNECT", () => (this.busConnected = true));
            bus.addEventListener("BUS:DISCONNECT", () => (this.busConnected = false));
        }
        Promise.resolve(bus.start && bus.start()).catch(() => {});
    }

    async channelChanged(channelId) {
        await this.refreshCount();
        if (this.window) {
            await this.window.notify(channelId);
        }
        for (const thread of this.blocks) {
            if (!channelId || thread.channelId === parseInt(channelId, 10)) {
                await thread.refresh();
            }
        }
        if (!this.menu.hidden) {
            await this.loadConversations();
        }
    }

    schedule(delay = this.interval) {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.poll(), delay);
    }

    async poll() {
        if (this.leaving || document.visibilityState === "hidden") {
            return; // resumed by visibilitychange
        }
        if (!this.busConnected) {
            try {
                await this.channelChanged(null);
                this.interval = POLL_MS;
            } catch {
                this.interval = Math.min(this.interval * 2, MAX_BACKOFF);
            }
        }
        this.schedule();
    }

    // ------------------------------------------------------------------
    // Badge, dropdown, picker
    // ------------------------------------------------------------------
    setCount(count) {
        if (Number.isInteger(count)) {
            applyBadge(this.badge, count);
            // Task 5546: the installed app's icon follows (pk_push.js).
            document.dispatchEvent(new CustomEvent("pk:app-badge", { detail: { count } }));
        }
    }

    async refreshCount() {
        try {
            const data = await this.api.unread();
            this.setCount(data && data.count);
        } catch {
            // Keep the last count.
        }
    }

    async openMenu() {
        this.menu.hidden = false;
        this.toggleEl.setAttribute("aria-expanded", "true");
        this.pickerHost.hidden = true;
        await this.loadConversations();
    }

    closeMenu() {
        this.menu.hidden = true;
        this.toggleEl.setAttribute("aria-expanded", "false");
    }

    async loadConversations() {
        try {
            const data = await this.api.conversations();
            renderConversations(this.list, data.conversations || [], this.texts);
        } catch {
            // The list stays as it was.
        }
    }

    async showPicker() {
        const data = await this.api.contacts("");
        this.pickerHost.innerHTML = "";
        const select = document.createElement("select");
        select.dataset.pkPicker = "1";
        select.dataset.pkChatContacts = "1";
        select.setAttribute("aria-label", this.el.dataset.pkChatPickLabel || "");
        const blank = document.createElement("option");
        blank.value = "";
        select.append(blank);
        for (const contact of data.contacts || []) {
            const option = document.createElement("option");
            option.value = String(contact.id);
            option.textContent = contact.name;
            select.append(option);
        }
        this.pickerHost.append(select);
        this.pickerHost.hidden = false;
        enhance(select);
        select.addEventListener("change", async () => {
            if (!select.value) {
                return;
            }
            const started = await this.api.start(select.value);
            this.closeMenu();
            await this.openConversation(started.id);
        });
    }

    async openConversation(id) {
        if (this.window) {
            await this.window.open(id);
        } else {
            window.location.assign(`/my/app/conversations/${id}`);
        }
    }
}

registry.category("public.interactions").add("bemade_portal_kit_chat.pk_chat_bubble", PkChatBubble);
