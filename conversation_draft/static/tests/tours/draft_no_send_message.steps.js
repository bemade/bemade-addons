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
    narration: "Ouvrons une conversation.",
    selector: ".o_list_renderer tr.o_data_row td[name='name']",
    containsText: "Question de livraison",
    action: "click",
  },
  {
    id: "reply",
    title: "Cliquer sur Répondre",
    narration: "Cliquons sur le bouton Répondre pour ouvrir le brouillon de réponse.",
    selector: ".o_form_statusbar button[name='action_open_draft']",
    action: "click",
  },
  {
    id: "draft-open",
    title: "Afficher le brouillon de réponse",
    narration: "Le brouillon de réponse s'ouvre, avec le texte du message à envoyer.",
    selector: ".o_field_widget[name='body']",
    action: "assert",
  },
  {
    id: "log-note-present",
    title: "Repérer le bouton de note interne",
    narration:
      "Sous le brouillon, le bouton pour ajouter une note interne est toujours là : vous pouvez commenter le brouillon avec vos collègues.",
    selector: ".o-mail-Chatter-topbar .o-mail-Chatter-logNote",
    containsText: "Log note",
    action: "assert",
  },
  {
    id: "send-message-absent",
    title: "Constater que « Envoyer un message » a disparu",
    narration:
      "Le bouton « Envoyer un message » n'est plus offert, car il n'aurait joint personne. Pour écrire aux destinataires, utilisez le bouton Envoyer du brouillon.",
    selector:
      ".o-mail-Chatter-topbar:has(.o-mail-Chatter-logNote):not(:has(.o-mail-Chatter-sendMessage))",
    action: "assert",
  },
];
