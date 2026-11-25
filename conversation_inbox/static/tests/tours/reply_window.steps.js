// Replying from the inbox: the Reply window opens at once, already filled in
// (recipient, subject, quoted message), with the attachments control in the
// footer. The speed is asserted server-side; this flow guards that the window
// is unchanged.
export default [
  {
    id: "open_inbox",
    title: "Ouvrir la boîte de réception",
    narration: "Vous ouvrez la boîte de réception de Conversations.",
    selector: ".o_conversation_inbox",
    action: "assert",
  },
  {
    id: "see_item",
    title: "Repérer le courriel",
    narration:
      "Vous repérez le courriel auquel vous voulez répondre : pas besoin de l'ouvrir.",
    selector: ".o_conversation_inbox_list .card-header",
    action: "assert",
    containsText: "Reply Window Message",
  },
  {
    id: "click_reply",
    title: "Cliquer sur l'icône « Répondre »",
    narration: "Vous cliquez sur l'icône « Répondre » de la ligne.",
    selector: ".o_inbox_row_actions .o_inbox_reply",
    action: "click",
  },
  {
    id: "window_open",
    title: "La fenêtre de réponse s'ouvre",
    narration:
      "La fenêtre de réponse s'ouvre aussitôt, prête à être modifiée, sans longue attente.",
    selector: ".modal .o_form_view .o_field_widget[name='body']",
    action: "assert",
  },
  {
    id: "prefilled_subject",
    title: "L'objet est déjà rempli",
    narration: "L'objet est déjà rempli, précédé de « Re : ».",
    selector: ".modal .o_field_widget[name='subject'] input",
    action: "assert",
  },
  {
    id: "prefilled_quote",
    title: "Le message d'origine est cité",
    narration: "Le message d'origine est cité dans le corps, que vous pouvez modifier.",
    selector: ".modal .o_field_widget[name='body']",
    action: "assert",
    containsText: "Here is the quote you asked for",
  },
  {
    id: "attachments_footer",
    title: "Joindre des fichiers",
    narration:
      "Le bouton pour joindre des fichiers se trouve en bas de la fenêtre, comme avant.",
    selector: ".modal footer .o_field_widget[name='attachment_ids']",
    action: "assert",
  },
  {
    id: "cancel",
    title: "Cliquer sur « Annuler »",
    narration: "Vous fermez la fenêtre en cliquant sur « Annuler ».",
    selector: ".modal footer button",
    action: "click",
    containsText: "Cancel",
  },
];
