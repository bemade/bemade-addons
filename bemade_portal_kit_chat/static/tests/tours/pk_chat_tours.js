/*
 * Task 5516 — browser tours of the portal chat (run by
 * tests/test_pk_chat_tours.py). Language-independent triggers only.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

tours.add("pk_chat_start_and_send", {
    steps: () => [
        { content: "Open the bubble", trigger: "[data-pk-chat-toggle]", run: "click" },
        { content: "The dropdown is open", trigger: "[data-pk-chat-menu]:not([hidden])" },
        { content: "New conversation", trigger: "[data-pk-chat-new]", run: "click" },
        {
            content: "Type the contact's name",
            trigger: "[data-pk-chat-picker] .o_pk_picker_input",
            run: "edit Dana",
        },
        {
            content: "Pick the contact",
            trigger: "[data-pk-chat-picker] .o_pk_picker_option:contains(Dana Staffperson)",
            run: "click",
        },
        { content: "The window opens on the chat", trigger: "[data-pk-chat-window][data-pk-chat-open]:not([hidden])" },
        { content: "Its title is the other person", trigger: "[data-pk-chat-title]:contains(Dana Staffperson)" },
        {
            content: "Write a message",
            trigger: "[data-pk-chat-window] [data-pk-chat-composer]:not([hidden]) textarea",
            run: "edit Hello from the tour",
        },
        { content: "Send", trigger: "[data-pk-chat-window] [data-pk-chat-send]", run: "click" },
        {
            content: "The message is shown as mine",
            trigger: "[data-pk-chat-window] .o_pk_chat_msg_own:contains(Hello from the tour)",
        },
        { content: "The back arrow", trigger: "[data-pk-chat-window] [data-pk-chat-back]", run: "click" },
        {
            content: "closes the window and shows the list (it stays open)",
            trigger: "[data-pk-chat-menu]:not([hidden]) [data-pk-chat-list] [data-pk-chat-kind=direct]",
        },
    ],
});

tours.add("pk_chat_reply_announcement", {
    steps: () => [
        { content: "Open the bubble", trigger: "[data-pk-chat-toggle]", run: "click" },
        {
            content: "Open the announcement group",
            trigger: "[data-pk-chat-list] [data-pk-chat-kind=group]",
            run: "click",
        },
        {
            content: "A reader has no composer, a hint instead",
            trigger: "[data-pk-chat-window] [data-pk-chat-reader-hint]:not([hidden])",
        },
        {
            content: "A reader sees no member list",
            trigger: "[data-pk-chat-window] [data-pk-chat-members]:not(:visible)",
        },
        {
            content: "Reply to the announcement",
            trigger: "[data-pk-chat-window] .o_pk_chat_msg:contains(Practice moved) [data-pk-chat-reply]",
            run: "click",
        },
        {
            content: "Write the reply",
            trigger: "[data-pk-chat-window] [data-pk-chat-composer]:not([hidden]) textarea",
            run: "edit We will be there",
        },
        { content: "Send", trigger: "[data-pk-chat-window] [data-pk-chat-send]", run: "click" },
        {
            // It answers the message just above it, so it carries no quote.
            content: "The reply shows, without repeating the message above",
            trigger: "[data-pk-chat-window] .o_pk_chat_msg_own:contains(We will be there):not(:has(.o_pk_chat_quote))",
        },
        {
            content: "Back to a reader's composer: hidden again",
            trigger: "[data-pk-chat-window] [data-pk-chat-composer]:not(:visible)",
        },
    ],
});

tours.add("pk_chat_window_follows", {
    steps: () => [
        { content: "Open the bubble", trigger: "[data-pk-chat-toggle]", run: "click" },
        {
            content: "Open the direct chat",
            trigger: "[data-pk-chat-list] [data-pk-chat-kind=direct]",
            run: "click",
        },
        {
            content: "The window shows it; go to another page",
            trigger: "[data-pk-chat-window][data-pk-chat-open]:not([hidden]) .o_pk_chat_msg:contains(Hello again)",
            run() {
                window.location.assign("/my/app/settings");
            },
            expectUnloadPage: true,
        },
        {
            content: "The next page restores the window",
            trigger: "#pk_done_buttons",
        },
        {
            content: "with the conversation",
            trigger: "[data-pk-chat-window][data-pk-chat-open]:not([hidden]) .o_pk_chat_msg:contains(Hello again)",
        },
    ],
});
