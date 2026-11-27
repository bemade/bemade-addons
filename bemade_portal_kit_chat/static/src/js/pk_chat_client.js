/*
 * Task 5516 — the portal chat's client: the kit routes (the portal UI's
 * ONLY API) and the thread (messages + composer) shared by the floating
 * window and the inline block.
 *
 * Plain DOM, no OWL Store. The texts come from the server-rendered
 * [data-pk-chat-texts] span (translated by QWeb).
 *
 * Markup written: .o_pk_chat_thread[data-pk-chat-thread], its
 * [data-pk-chat-messages] list of [data-pk-chat-msg] items (o_pk_chat_msg_own,
 * a reply's .o_pk_chat_quote, [data-pk-chat-reply] buttons when the
 * conversation allows replies), [data-pk-chat-members] (posters only) and
 * the composer form[data-pk-chat-composer] (hidden for a reader of a
 * managed channel until « Reply » opens it with the quoted parent).
 *
 * Task 5566: a closed conversation (``closed`` in the thread payload) has
 * no composer and no « Reply »: a note [data-pk-chat-closed-note] instead,
 * and its chip [data-pk-chat-closed-chip] (the window shows it in its
 * header through ``onClosed``; a block, at the top of the thread).
 *
 * Task 5520: a reader of a managed group gets no Discuss broadcast of it,
 * only ``pk_chat.ping`` {channel_id, message_id} (content-free); both it
 * and ``discuss.channel/new_message`` mean « refetch channel X »
 * (subscribeChatBus).
 */
import { pkFetch } from "@bemade_portal_kit/js/pk_fetch";
import { pkChatPushPrompt } from "@bemade_portal_kit_chat/js/pk_chat_push_prompt";

export const PK_CHAT_EVENT = "pk:chat-changed";
export const PK_CHAT_PING = "pk_chat.ping";
export const PK_CHAT_NEW_MESSAGE = "discuss.channel/new_message";
export const PK_CHAT_JOINED = "discuss.channel/joined";

/**
 * Task 5520: listen to the bus for the chat. ``onChanged(channelId)`` on a
 * new message (Discuss's own notification for a poster or a direct chat,
 * the kit's ``pk_chat.ping`` for a reader: only its channel id is used),
 * ``onJoined()`` when the user is added to a conversation. Returns the
 * unsubscribe function.
 */
export function subscribeChatBus(bus, { onChanged, onJoined }) {
    const changed = (payload) => onChanged(payload && (payload.channel_id || payload.id));
    const joined = () => onJoined();
    bus.subscribe(PK_CHAT_NEW_MESSAGE, changed);
    bus.subscribe(PK_CHAT_PING, changed);
    bus.subscribe(PK_CHAT_JOINED, joined);
    return () => {
        bus.unsubscribe(PK_CHAT_NEW_MESSAGE, changed);
        bus.unsubscribe(PK_CHAT_PING, changed);
        bus.unsubscribe(PK_CHAT_JOINED, joined);
    };
}

/** The kit routes. Every call goes through pkFetch (no toast: the chat
 * shows its own state). Tests replace it with a stub of the same shape. */
export const chatApi = {
    conversations: () => pkFetch("/my/app/chat/conversations", { toast: false }),
    unread: () => pkFetch("/my/app/chat/unread", { toast: false }),
    messages: (id, { before, after } = {}) => {
        const params = new URLSearchParams();
        if (before) {
            params.set("before", before);
        }
        if (after) {
            params.set("after", after);
        }
        const query = params.toString();
        return pkFetch(`/my/app/chat/${id}/messages${query ? "?" + query : ""}`, { toast: false });
    },
    post: (id, body, parentId) =>
        pkFetch(`/my/app/chat/${id}/post`, {
            method: "POST",
            data: { body, parent_id: parentId || "" },
            toast: false,
        }),
    read: (id) => pkFetch(`/my/app/chat/${id}/read`, { method: "POST", toast: false }),
    contacts: (q) =>
        pkFetch(`/my/app/chat/contacts?q=${encodeURIComponent(q || "")}`, { toast: false }),
    start: (partnerId) =>
        pkFetch("/my/app/chat/start", {
            method: "POST",
            data: { partner_id: partnerId },
            toast: false,
        }),
};

const DEFAULT_TEXTS = {
    reply: "Reply",
    send: "Send",
    placeholder: "Write a message…",
    replyingTo: "Replying to %s",
    cancel: "Cancel",
    readerHint: "Reply to a message to answer.",
    members: "Members",
    poster: "Poster",
    reader: "Reader",
    empty: "No messages yet.",
    error: "The message could not be sent.",
    older: "Older messages",
    closed: "This conversation is closed.",
};

/** The texts of the page (server-rendered), the kit's English otherwise. */
export function chatTexts(root = document) {
    const el = root.querySelector("[data-pk-chat-texts]");
    const texts = { ...DEFAULT_TEXTS };
    if (el) {
        for (const key of Object.keys(DEFAULT_TEXTS)) {
            const value = el.dataset[`pkChat${key[0].toUpperCase()}${key.slice(1)}`];
            if (value) {
                texts[key] = value;
            }
        }
    }
    return texts;
}

/** A desktop keyboard (Enter sends) or a phone (the send button). */
export function isDesktop() {
    return window.matchMedia ? window.matchMedia("(min-width: 992px)").matches : true;
}

function el(tag, className, attrs = {}) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    for (const [key, value] of Object.entries(attrs)) {
        if (value !== undefined && value !== null && value !== false) {
            node.setAttribute(key, value === true ? "1" : value);
        }
    }
    return node;
}

/**
 * One message item. ``bodyHtml`` is the server's sanitised body.
 * ``prevId``: the message shown just above; a reply to it carries no quote,
 * which would only repeat what the reader just read.
 */
export function renderMessage(msg, texts, { canReply, prevId = 0 }) {
    const item = el("li", `o_pk_chat_msg${msg.own ? " o_pk_chat_msg_own" : ""}`, {
        "data-pk-chat-msg": String(msg.id),
    });
    if (msg.parent && msg.parent.id !== prevId) {
        const quote = el("blockquote", "o_pk_chat_quote", {
            "data-pk-chat-quote": String(msg.parent.id),
        });
        const who = el("strong");
        who.textContent = msg.parent.author_name;
        quote.append(who, document.createTextNode(` ${msg.parent.excerpt}`));
        item.append(quote);
    }
    const head = el("div", "o_pk_chat_msg_head");
    const author = el("span", "o_pk_chat_author");
    author.textContent = msg.author_name;
    const when = el("time", "o_pk_chat_when");
    when.textContent = msg.when;
    head.append(author, when);
    const body = el("div", "o_pk_chat_msg_body");
    body.innerHTML = msg.body_html;
    item.append(head, body);
    if (canReply && msg.can_reply) {
        const reply = el("button", "o_pk_chat_reply", {
            type: "button",
            "data-pk-chat-reply": String(msg.id),
        });
        reply.textContent = texts.reply;
        item.append(reply);
    }
    return item;
}

/** The dropdown's rows (the bubble; task 5566: here, so hoot can test it). */
export function renderConversations(list, rows, texts) {
    list.innerHTML = "";
    if (!rows.length) {
        const empty = document.createElement("p");
        empty.className = "o_pk_chat_empty";
        empty.textContent = texts.noConversations || "";
        list.append(empty);
        return;
    }
    let section = false;
    for (const row of rows) {
        if (row.closed && !section) {
            section = true;
            const heading = document.createElement("h3");
            heading.className = "o_pk_chat_section";
            heading.dataset.pkChatClosedSection = "1";
            heading.textContent = texts.closedSection || "";
            list.append(heading);
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = `o_pk_chat_row${row.unread ? " o_pk_chat_row_unread" : ""}`;
        button.dataset.pkChatOpen = String(row.id);
        button.dataset.pkChatKind = row.kind;
        if (row.closed) {
            button.dataset.pkChatClosed = "1";
        }
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
        if (row.closed && row.closed_label) {
            const chip = document.createElement("span");
            chip.className = "o_pk_chip o_pk_chip_ghost o_pk_chat_closed_chip";
            chip.dataset.pkChatClosedChip = "1";
            chip.textContent = row.closed_label;
            meta.append(chip);
        }
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

/**
 * The thread of one conversation inside ``host``. ``options``: ``api``
 * (default chatApi), ``texts``, ``onRead`` (called after the conversation
 * is marked read), ``onTitle(title)``.
 */
export class ChatThread {
    constructor(host, channelId, options = {}) {
        this.host = host;
        this.channelId = channelId;
        this.api = options.api || chatApi;
        this.texts = options.texts || chatTexts();
        this.onRead = options.onRead || (() => {});
        this.onTitle = options.onTitle || (() => {});
        // Task 5566: who shows the closed chip (the window: its header).
        this.onClosed = options.onClosed || null;
        this.data = null;
        this.replyTo = null;
        this.lastId = 0;
        this.firstId = 0;
        this.sending = false;
        this.build();
    }

    build() {
        this.host.innerHTML = "";
        // Task 5546: what this thread shows, for the phone notifications
        // (a push of this conversation is not shown while it is on screen).
        this.root = el("div", "o_pk_chat_thread", {
            "data-pk-chat-thread": String(this.channelId),
            "data-pk-push-showing": `/my/app/conversations/${this.channelId}`,
        });
        this.chip = el("span", "o_pk_chip o_pk_chip_ghost o_pk_chat_closed_chip", {
            "data-pk-chat-closed-chip": "1",
            hidden: "hidden",
        });
        this.closedNote = el("p", "o_pk_chat_closed_note", { "data-pk-chat-closed-note": "1", hidden: "hidden" });
        this.closedNote.textContent = this.texts.closed;
        this.members = el("details", "o_pk_chat_members", { "data-pk-chat-members": "1", hidden: "hidden" });
        this.older = el("button", "o_pk_chat_older", {
            type: "button",
            "data-pk-chat-older": "1",
            hidden: "hidden",
        });
        this.older.textContent = this.texts.older;
        this.list = el("ol", "o_pk_chat_messages", { "data-pk-chat-messages": "1", "aria-live": "polite" });
        this.emptyNote = el("p", "o_pk_chat_empty", { "data-pk-chat-empty": "1", hidden: "hidden" });
        this.emptyNote.textContent = this.texts.empty;
        this.hint = el("p", "o_pk_chat_reader_hint", { "data-pk-chat-reader-hint": "1", hidden: "hidden" });
        this.hint.textContent = this.texts.readerHint;
        this.form = el("form", "o_pk_chat_composer", { "data-pk-chat-composer": "1", hidden: "hidden" });
        this.replying = el("div", "o_pk_chat_replying", { "data-pk-chat-replying": "1", hidden: "hidden" });
        this.replyingText = el("span");
        const cancel = el("button", "o_pk_chat_reply_cancel", {
            type: "button",
            "data-pk-chat-reply-cancel": "1",
            "aria-label": this.texts.cancel,
            title: this.texts.cancel,
        });
        cancel.textContent = "×";
        this.replying.append(this.replyingText, cancel);
        this.input = el("textarea", "o_pk_chat_input", {
            name: "body",
            rows: "1",
            placeholder: this.texts.placeholder,
            "aria-label": this.texts.placeholder,
        });
        this.send = el("button", "o_pk_chat_send", { type: "submit", "data-pk-chat-send": "1" });
        this.send.textContent = this.texts.send;
        this.form.append(this.replying, this.input, this.send);
        this.root.append(
            this.chip,
            this.members,
            this.older,
            this.list,
            this.emptyNote,
            this.hint,
            this.closedNote,
            this.form
        );
        this.host.append(this.root);

        this.list.addEventListener("click", (ev) => {
            const button = ev.target.closest("[data-pk-chat-reply]");
            if (button) {
                this.startReply(parseInt(button.dataset.pkChatReply, 10));
            }
        });
        this.older.addEventListener("click", () => this.loadOlder());
        cancel.addEventListener("click", () => this.cancelReply());
        this.form.addEventListener("submit", (ev) => {
            ev.preventDefault();
            this.submit();
        });
        this.input.addEventListener("keydown", (ev) => {
            if (ev.key === "Enter" && !ev.shiftKey && isDesktop()) {
                ev.preventDefault();
                this.submit();
            }
        });
        this.list.addEventListener("scroll", () => {
            if (this.atBottom()) {
                this.markRead();
            }
        });
    }

    get isReaderOnly() {
        return Boolean(this.data && this.data.composer === "reply");
    }

    /** Task 5566: an ended conversation, read-only for everyone. */
    get isClosed() {
        return Boolean(this.data && this.data.closed);
    }

    /** « Reply » buttons: a managed channel's messages, unless closed. */
    get canReply() {
        return !this.isClosed && (this.isReaderOnly || Boolean(this.data && this.data.managed));
    }

    atBottom() {
        const list = this.list;
        return list.scrollHeight - list.scrollTop - list.clientHeight < 24;
    }

    scrollToBottom() {
        this.list.scrollTop = this.list.scrollHeight;
    }

    async load() {
        const data = await this.api.messages(this.channelId);
        this.data = data;
        this.onTitle(data.title);
        this.list.innerHTML = "";
        this.lastId = 0;
        this.append(data.messages);
        this.firstId = data.messages.length ? data.messages[0].id : 0;
        this.older.hidden = !data.more;
        this.renderMembers(data.members);
        this.renderClosed();
        this.renderComposer();
        this.scrollToBottom();
        await this.markRead();
        return data;
    }

    async loadOlder() {
        if (!this.firstId) {
            return;
        }
        const data = await this.api.messages(this.channelId, { before: this.firstId });
        const height = this.list.scrollHeight;
        const canReply = this.canReply;
        const items = data.messages.map((msg, index) =>
            renderMessage(msg, this.texts, {
                canReply,
                prevId: index ? data.messages[index - 1].id : 0,
            })
        );
        this.list.prepend(...items);
        if (data.messages.length) {
            this.firstId = data.messages[0].id;
        }
        this.older.hidden = !data.more;
        this.list.scrollTop = this.list.scrollHeight - height;
    }

    /** New messages since the last one shown (a bus notice, a poll). */
    async refresh() {
        if (!this.data) {
            return this.load();
        }
        const stick = this.atBottom();
        const data = await this.api.messages(this.channelId, { after: this.lastId });
        this.append(data.messages);
        if (stick && data.messages.length) {
            this.scrollToBottom();
            await this.markRead();
        }
        return data;
    }

    append(messages) {
        const canReply = this.canReply;
        for (const msg of messages) {
            if (msg.id <= this.lastId) {
                continue;
            }
            this.list.append(renderMessage(msg, this.texts, { canReply, prevId: this.lastId }));
            this.lastId = msg.id;
        }
        this.emptyNote.hidden = Boolean(this.list.children.length);
    }

    renderMembers(members) {
        this.members.innerHTML = "";
        if (!members) {
            this.members.hidden = true;
            return;
        }
        const summary = el("summary");
        summary.textContent = `${this.texts.members} (${members.length})`;
        const list = el("ul");
        for (const member of members) {
            const item = el("li", "", { "data-pk-chat-member-role": member.role });
            item.textContent = `${member.name} · ${this.texts[member.role] || member.role}`;
            list.append(item);
        }
        this.members.append(summary, list);
        this.members.hidden = false;
    }

    renderClosed() {
        const label = this.isClosed ? this.data.closed_label || "" : "";
        this.chip.textContent = label;
        this.chip.hidden = !label || Boolean(this.onClosed);
        if (this.onClosed) {
            this.onClosed(label);
        }
    }

    renderComposer() {
        if (this.isClosed) {
            this.replyTo = null;
            this.form.hidden = true;
            this.hint.hidden = true;
            this.replying.hidden = true;
            this.closedNote.hidden = false;
            return;
        }
        this.closedNote.hidden = true;
        const replyOnly = this.isReaderOnly;
        this.form.hidden = replyOnly && !this.replyTo;
        this.hint.hidden = !replyOnly || Boolean(this.replyTo);
        this.replying.hidden = !this.replyTo;
        if (this.replyTo) {
            this.replyingText.textContent = this.texts.replyingTo.replace("%s", this.replyTo.author);
        }
    }

    startReply(messageId) {
        const item = this.list.querySelector(`[data-pk-chat-msg="${messageId}"]`);
        const author = item ? item.querySelector(".o_pk_chat_author").textContent : "";
        this.replyTo = { id: messageId, author };
        this.renderComposer();
        this.input.focus();
    }

    cancelReply() {
        this.replyTo = null;
        this.renderComposer();
    }

    async submit() {
        const body = this.input.value.trim();
        if (!body || this.sending || this.isClosed) {
            return;
        }
        this.sending = true;
        this.send.disabled = true;
        try {
            const result = await this.api.post(this.channelId, body, this.replyTo && this.replyTo.id);
            this.input.value = "";
            this.replyTo = null;
            this.renderComposer();
            this.append([result.message]);
            this.scrollToBottom();
            document.dispatchEvent(new CustomEvent(PK_CHAT_EVENT, { detail: { channelId: this.channelId } }));
            pkChatPushPrompt(this); // task 5546: once, after a message sent
        } catch (error) {
            // Task 5566: the conversation was closed while it was open here.
            // Reload it: its closed look (note, chip, no composer) replaces
            // the composer, and the lists move it under « Ended ».
            if (error && error.payload && error.payload.error === "closed" && (await this.reloadClosed())) {
                return;
            }
            document.dispatchEvent(
                new CustomEvent("pk:toast", { detail: { message: this.texts.error, tone: "error" } })
            );
        } finally {
            this.sending = false;
            this.send.disabled = false;
        }
    }

    /** Task 5566: true once the thread shows its closed state again. */
    async reloadClosed() {
        try {
            await this.load();
        } catch {
            return false;
        }
        if (!this.isClosed) {
            return false;
        }
        document.dispatchEvent(new CustomEvent(PK_CHAT_EVENT, { detail: { channelId: this.channelId } }));
        return true;
    }

    async markRead() {
        try {
            const result = await this.api.read(this.channelId);
            this.onRead(result && result.count);
        } catch {
            // The badge stays as it was; the next refresh retries.
        }
    }
}
