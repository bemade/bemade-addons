import {registry} from "@web/core/registry";

const SIGNATURE_PREVIEW = ".o-mail-Composer-signaturePreview:contains('Intégrateur')";

function openMessageComposer() {
  return [
    {
      content: "Open the inline message composer",
      trigger: ".o-mail-Chatter-sendMessage",
      run: "click",
    },
  ];
}

registry.category("web_tour.tours").add("mail_company_signature_inline_send", {
  steps: () => [
    ...openMessageComposer(),
    {content: "The signature preview is shown", trigger: SIGNATURE_PREVIEW},
    {
      content: "Type the message",
      trigger: ".o-mail-Composer-input",
      run: "edit Hello inline",
    },
    {content: "Send", trigger: ".o-mail-Composer-send:enabled", run: "click"},
    {content: "Message posted", trigger: ".o-mail-Message:contains('Hello inline')"},
  ],
});

registry.category("web_tour.tours").add("mail_company_signature_inline_remove", {
  steps: () => [
    ...openMessageComposer(),
    {content: "Preview shown", trigger: SIGNATURE_PREVIEW},
    {
      content: "Remove the signature",
      trigger: ".o-mail-Composer-signatureRemove",
      run: "click",
    },
    {content: "Restore link shown", trigger: ".o-mail-Composer-signatureRestore"},
    {
      content: "Type the message",
      trigger: ".o-mail-Composer-input",
      run: "edit No sig",
    },
    {content: "Send", trigger: ".o-mail-Composer-send:enabled", run: "click"},
    {content: "Message posted", trigger: ".o-mail-Message:contains('No sig')"},
    ...openMessageComposer(),
    {
      content: "Next message defaults back to including the signature",
      trigger: SIGNATURE_PREVIEW,
    },
  ],
});

registry.category("web_tour.tours").add("mail_company_signature_log_note", {
  steps: () => [
    {
      content: "Open the log note composer",
      trigger: ".o-mail-Chatter-logNote",
      run: "click",
    },
    {
      content: "No signature preview on internal notes",
      trigger: ".o-mail-Composer:not(:has(.o-mail-Composer-signaturePreview))",
    },
    {
      content: "Type the note",
      trigger: ".o-mail-Composer-input",
      run: "edit Internal",
    },
    {content: "Log", trigger: ".o-mail-Composer-send:enabled", run: "click"},
    {content: "Note posted", trigger: ".o-mail-Message:contains('Internal')"},
  ],
});

registry.category("web_tour.tours").add("mail_company_signature_full_composer", {
  steps: () => [
    ...openMessageComposer(),
    {content: "Preview shown", trigger: SIGNATURE_PREVIEW},
    {
      content: "Type the message",
      trigger: ".o-mail-Composer-input",
      run: "edit Via full",
    },
    {
      content: "Open the full composer",
      trigger: "[name='open-full-composer']",
      run: "click",
    },
    {
      content: "Exactly one signature in the editor",
      trigger:
        ".o_mail_composer_form .o-signature-container:not(:has(~ .o-signature-container))",
    },
    {
      content: "Close the dialog (accidental discard saves the draft)",
      trigger: ".modal-header .btn-close",
      run: "click",
    },
    {
      content: "Reopen the full composer from the restored draft",
      trigger: "[name='open-full-composer']",
      run: "click",
    },
    {
      content: "Still exactly one signature",
      trigger:
        ".o_mail_composer_form .o-signature-container:not(:has(~ .o-signature-container))",
    },
    {
      content: "Send",
      trigger: ".o_mail_send[name='action_send_mail']",
      run: "click",
    },
    {content: "Dialog closed", trigger: "body:not(:has(.modal))"},
  ],
});
