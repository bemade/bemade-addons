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

// Task 5566: a closed group in the portal (a reader or a poster): listed
// last under its heading with its chip; the history reads; no composer.
tours.add("pk_chat_closed_portal", {
    steps: () => [
        { content: "Open the bubble", trigger: "[data-pk-chat-toggle]", run: "click" },
        {
            content: "The closed group comes after the heading, with its chip",
            trigger:
                "[data-pk-chat-list] [data-pk-chat-closed-section] ~ [data-pk-chat-closed] [data-pk-chat-closed-chip]",
        },
        {
            content: "The open group comes before the heading",
            trigger: "[data-pk-chat-list] [data-pk-chat-open]:not([data-pk-chat-closed]) ~ [data-pk-chat-closed-section]",
        },
        { content: "Open the closed group", trigger: "[data-pk-chat-list] [data-pk-chat-closed]", run: "click" },
        {
            content: "The history reads",
            trigger: "[data-pk-chat-window] .o_pk_chat_msg:contains(Last practice of the season)",
        },
        { content: "The chip in the header", trigger: "[data-pk-chat-window] header [data-pk-chat-closed-chip]:visible" },
        { content: "A closed note", trigger: "[data-pk-chat-window] [data-pk-chat-closed-note]:visible" },
        { content: "No composer", trigger: "[data-pk-chat-window] [data-pk-chat-composer]:not(:visible)" },
        {
            content: "No « Reply »",
            trigger: "[data-pk-chat-window] [data-pk-chat-messages]:not(:has([data-pk-chat-reply]))",
        },
    ],
});

// Task 5566: the same group, closed, in the back end's Discuss.
tours.add("pk_chat_closed_discuss", {
    steps: () => [
        { content: "The history reads", trigger: ".o-mail-Message:contains(Last practice of the season)" },
        { content: "The chip in the header", trigger: ".o-mail-DiscussContent-header [data-pk-chat-closed-chip]" },
        { content: "No composer", trigger: ".o-mail-DiscussContent:not(:has(.o-mail-Composer))" },
    ],
});

// Task 5566: reopened, Discuss has its composer back and no chip.
tours.add("pk_chat_reopened_discuss", {
    steps: () => [
        { content: "The history reads", trigger: ".o-mail-Message:contains(Last practice of the season)" },
        { content: "The composer is back", trigger: ".o-mail-DiscussContent .o-mail-Composer-input" },
        {
            content: "No chip",
            trigger: ".o-mail-DiscussContent-header:not(:has([data-pk-chat-closed-chip]))",
        },
    ],
});
