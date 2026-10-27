// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "open-list",
    title: "Afficher la liste des conversations",
    narration: "Voici la liste de vos conversations.",
    selector: ".o_list_renderer",
    action: "assert",
  },
  {
    id: "open-conversation",
    title: "Ouvrir une conversation",
    narration: "Ouvrons une conversation qui n'est pas traitée par une boîte d'équipe.",
    selector: ".o_list_renderer tr.o_data_row td[name='name']",
    containsText: "Question de livraison",
    action: "click",
  },
  {
    id: "reply",
    title: "Cliquer sur Répondre",
    narration: "Cliquons sur le bouton Répondre.",
    selector: ".o_form_statusbar button[name='action_open_draft']",
    action: "click",
  },
  {
    id: "signature-shown",
    title: "Repérer la signature dans le texte de la réponse",
    narration:
      "Votre signature est déjà dans le texte de la réponse, sous une ligne vide prête pour votre message. C'est du texte ordinaire : vous pouvez la modifier ou l'effacer avant d'envoyer.",
    selector: ".o_field_widget[name='body'] .odoo-editor-editable",
    containsText: "Cordialement",
    action: "assert",
  },
  {
    id: "send",
    title: "Envoyer la réponse",
    narration:
      "Envoyons la réponse. Rien n'est ajouté au moment de l'envoi : le destinataire reçoit exactement ce que vous voyez, avec votre signature une seule fois.",
    selector: ".o_form_statusbar button[name='action_send']",
    action: "click",
    navigates: true,
  },
  {
    id: "sent",
    title: "Constater que la réponse est envoyée",
    narration: "La réponse est envoyée et ne peut plus être modifiée.",
    selector: ".o_form_statusbar:not(:has(button[name='action_send']))",
    action: "assert",
  },
];
