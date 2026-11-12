import {registry} from "@web/core/registry";

const LINE = ".o-mail-Chatter .o-mail-NotifiedPreview";

registry.category("web_tour.tours").add("bemade_mail_notified_preview_tour", {
  steps: () => [
    {
      content: "Open Send message",
      trigger: ".o-mail-Chatter-sendMessage",
      run: "click",
    },
    {
      content: "The follower is announced under the To row",
      trigger: `${LINE}:contains('Also sent to followers: Carol Tourcontact (email)')`,
    },
    {
      content: "Add the follower as a recipient",
      trigger: ".o-mail-RecipientsInput input",
      run: "edit Carol Tour",
    },
    {
      trigger: ".o-autocomplete--dropdown-item:contains('Carol Tourcontact')",
      run: "click",
    },
    {
      content: "Nobody else is reached now",
      trigger: `${LINE}:contains('No followers will be notified')`,
    },
    {
      content: "Switch to Log note",
      trigger: ".o-mail-Chatter-logNote",
      run: "click",
    },
    {
      content: "No followers line on a log note",
      trigger: ".o-mail-Chatter:not(:has(.o-mail-NotifiedPreview))",
    },
  ],
});
