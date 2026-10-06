export default [
  {
    id: "open-contact",
    title: "Open a contact",
    narration:
      "Open any contact, for example one of your customers, from the Contacts list.",
    selector: ".o_kanban_record",
    action: "click",
    videoOnly: true,
  },
  {
    id: "open-composer",
    title: "Click Send message in the chatter",
    narration: "In the chatter, click Send message to write an email to the contact.",
    selector: ".o-mail-Chatter-sendMessage",
    action: "click",
  },
  {
    id: "see-signature",
    title: "Check the signature shown under the message",
    narration:
      "Under your message, you see your company signature, filled in with your own name, title and phone number. You do not have to type it.",
    selector: ".o-mail-Composer-signaturePreview",
    action: "assert",
  },
  {
    id: "type-message",
    title: "Type the message",
    narration: "Type your message as usual.",
    selector: ".o-mail-Composer-input",
    action: "fill",
    value: "Hello inline",
  },
  {
    id: "send",
    title: "Click Send",
    narration: "Click Send. The email leaves with the signature added once, at the bottom.",
    selector: ".o-mail-Composer-send:enabled",
    action: "click",
  },
  {
    id: "message-posted",
    title: "Check that the message appears in the chatter",
    narration: "The message now appears in the chatter of the contact.",
    selector: ".o-mail-Message",
    action: "assert",
    containsText: "Hello inline",
  },
];
