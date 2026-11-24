import {registry} from "@web/core/registry";

const TEAM_ADDRESS = "sac-test@";

registry.category("web_tour.tours").add("mail_company_signature_helpdesk_preview", {
  steps: () => [
    {
      content: "Open the inline message composer of the ticket",
      trigger: ".o-mail-Chatter-sendMessage",
      run: "click",
    },
    {
      content: "The signature preview shows the team address",
      trigger: `.o-mail-Composer-signaturePreview:contains('${TEAM_ADDRESS}')`,
    },
    {
      content: "The team address line is visible, not clipped by the preview box",
      trigger: ".o-mail-Composer-signaturePreview .o-mail-Composer-signatureBlock",
      run() {
        const block = this.anchor;
        const line = [...block.querySelectorAll("*")]
          .reverse()
          .find((el) => el.textContent.includes(TEAM_ADDRESS));
        const box = block.getBoundingClientRect();
        const lineBox = line.getBoundingClientRect();
        if (lineBox.bottom > box.bottom + 1 || block.scrollHeight > block.clientHeight + 1) {
          throw new Error(
            `signature clipped: line bottom ${lineBox.bottom} > box bottom ${box.bottom}, ` +
              `scrollHeight ${block.scrollHeight} > clientHeight ${block.clientHeight}`
          );
        }
      },
    },
    {
      content: "No personal address in the preview",
      trigger: ".o-mail-Composer:not(:has(.o-mail-Composer-signaturePreview:contains('desk.agent@')))",
    },
    {
      content: "Type the message",
      trigger: ".o-mail-Composer-input",
      run: "edit Preview check",
    },
    {
      content: "Open the full composer",
      trigger: "[name='open-full-composer']",
      run: "click",
    },
    {
      content: "The signature inserted in the editor shows the team address",
      trigger: `.o_mail_composer_form .note-editable:contains('${TEAM_ADDRESS}')`,
    },
    {
      content: "And not the personal address",
      trigger: ".o_mail_composer_form .note-editable:not(:contains('desk.agent@'))",
    },
    {
      content: "Close the dialog",
      trigger: ".modal-header .btn-close",
      run: "click",
    },
    {content: "Dialog closed", trigger: "body:not(:has(.modal))"},
  ],
});
