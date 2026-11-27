import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("bemade_mail_signature_tour", {
  steps: () => [
    {
      content: "Open the « Send message » composer",
      trigger: ".o-mail-Chatter-sendMessage",
      run: "click",
    },
    {
      content: "The signature is shown as it will be sent",
      trigger:
        ".o_bemade_mail_signature_preview .o_bemade_mail_signature:contains(Example Widgets Inc.)",
    },
    {
      content: "Switch to « Log note »",
      trigger: ".o-mail-Chatter-logNote",
      run: "click",
    },
    {
      content: "No signature on a note",
      trigger: ".o-mail-Composer:not(:has(.o_bemade_mail_signature_preview))",
    },
    {
      content: "Back to « Send message »",
      trigger: ".o-mail-Chatter-sendMessage",
      run: "click",
    },
    {
      content: "Type the message",
      trigger: ".o-mail-Composer-input",
      run: "edit Tour hello",
    },
    {
      content: "Send",
      trigger: ".o-mail-Composer-send:enabled",
      run: "click",
    },
    {
      content: "The message is logged with its signature folded under « … »",
      trigger: ".o-mail-Message:contains(Tour hello) .o-mail-ellipsis",
    },
    {
      content: "Unfold it",
      trigger: ".o-mail-Message:contains(Tour hello) .o-mail-ellipsis",
      run: "click",
    },
    {
      content: "The signature is now shown in the message",
      trigger:
        ".o-mail-Message:contains(Tour hello) .o_bemade_mail_signature:contains(Example Widgets Inc.)",
    },
  ],
});
