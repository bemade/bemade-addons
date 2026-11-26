/*
 * Task 5516 — the ONE floating conversation window of the portal chat.
 *
 * Host: [data-pk-chat-window] (inside .o_pk_main, next to the toast host):
 * a header (back arrow to the list, the title, minimise, close) and the
 * thread host [data-pk-chat-thread-host]. Picking another conversation
 * swaps the window's thread. Docked bottom-right from 992 px, a full-screen
 * sheet below (pk_chat.scss).
 *
 * The open conversation and the minimised state are kept in
 * sessionStorage (PK_CHAT_OPEN_KEY, PK_CHAT_MIN_KEY): the window follows
 * the user from page to page.
 */
import { ChatThread, chatApi, chatTexts } from "@bemade_portal_kit_chat/js/pk_chat_client";

export const PK_CHAT_OPEN_KEY = "pk_chat_open:v1";
export const PK_CHAT_MIN_KEY = "pk_chat_min:v1";

function storageGet(key) {
    try {
        return window.sessionStorage.getItem(key);
    } catch {
        return null;
    }
}

function storageSet(key, value) {
    try {
        if (value === null || value === undefined) {
            window.sessionStorage.removeItem(key);
        } else {
            window.sessionStorage.setItem(key, String(value));
        }
    } catch {
        // Private mode: the window simply does not follow the user.
    }
}

export class ChatWindow {
    /**
     * @param {HTMLElement} host [data-pk-chat-window]
     * @param {Object} options api, texts, onBack (show the list), onRead(count)
     */
    constructor(host, options = {}) {
        this.host = host;
        this.api = options.api || chatApi;
        this.texts = options.texts || chatTexts();
        this.onBack = options.onBack || (() => {});
        this.onRead = options.onRead || (() => {});
        this.titleEl = host.querySelector("[data-pk-chat-title]");
        this.threadHost = host.querySelector("[data-pk-chat-thread-host]");
        this.thread = null;
        this.channelId = null;
        host.addEventListener("click", (ev) => {
            if (ev.target.closest("[data-pk-chat-close]")) {
                this.close();
            } else if (ev.target.closest("[data-pk-chat-min]")) {
                this.setMinimised(!this.minimised);
            } else if (ev.target.closest("[data-pk-chat-back]")) {
                this.close();
                this.onBack();
            } else if (ev.target.closest("[data-pk-chat-head]") && this.minimised) {
                this.setMinimised(false);
            }
        });
    }

    get minimised() {
        return this.host.dataset.pkChatMinimised === "1";
    }

    setMinimised(value) {
        if (value) {
            this.host.dataset.pkChatMinimised = "1";
        } else {
            delete this.host.dataset.pkChatMinimised;
        }
        storageSet(PK_CHAT_MIN_KEY, value ? "1" : null);
    }

    /** Open (or swap to) conversation ``channelId``. */
    async open(channelId, { title, minimised = false } = {}) {
        channelId = parseInt(channelId, 10);
        if (!channelId) {
            return null;
        }
        if (this.channelId !== channelId || !this.thread) {
            this.channelId = channelId;
            this.thread = new ChatThread(this.threadHost, channelId, {
                api: this.api,
                texts: this.texts,
                onRead: (count) => this.onRead(count),
                onTitle: (text) => this.setTitle(text),
            });
        }
        if (title) {
            this.setTitle(title);
        }
        this.host.hidden = false;
        this.host.dataset.pkChatOpen = String(channelId);
        storageSet(PK_CHAT_OPEN_KEY, channelId);
        this.setMinimised(minimised);
        try {
            await this.thread.load();
        } catch {
            // Not a member any more (404): the window closes.
            this.close();
        }
        return this.thread;
    }

    setTitle(text) {
        if (this.titleEl) {
            this.titleEl.textContent = text || "";
        }
    }

    close() {
        this.host.hidden = true;
        delete this.host.dataset.pkChatOpen;
        this.setMinimised(false);
        this.threadHost.innerHTML = "";
        this.thread = null;
        this.channelId = null;
        storageSet(PK_CHAT_OPEN_KEY, null);
    }

    /** The window as it was on the previous page (sessionStorage). */
    async restore() {
        const id = parseInt(storageGet(PK_CHAT_OPEN_KEY), 10);
        if (id) {
            return this.open(id, { minimised: storageGet(PK_CHAT_MIN_KEY) === "1" });
        }
        return null;
    }

    /** A change in ``channelId`` (bus notice, poll): refresh if shown. */
    async notify(channelId) {
        if (this.thread && (!channelId || parseInt(channelId, 10) === this.channelId)) {
            await this.thread.refresh();
        }
    }
}
