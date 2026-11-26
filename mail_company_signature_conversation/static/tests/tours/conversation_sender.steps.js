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
    title: "Ouvrir la conversation",
    narration:
      "Ouvrons une conversation à laquelle nous avons déjà répondu, depuis la boîte du soutien.",
    selector: ".o_list_renderer tr.o_data_row td[name='name']",
    containsText: "Demande de prix",
    action: "click",
  },
  {
    id: "sent-reply",
    title: "Repérer notre réponse dans le fil",
    narration:
      "Notre réponse est dans le fil. Notre adresse d'envoi est celle de l'équipe des ventes, mais la réponse est partie de la boîte du soutien.",
    selector: ".o-mail-Message .o-mail-Message-content",
    containsText: "Votre devis est prêt",
    action: "click",
  },
  {
    id: "reply-to-sent",
    title: "Répondre à notre propre message",
    narration: "Répondons à ce message pour le citer dans un nouveau brouillon.",
    selector: ".o-mail-Message-actions button[title='Reply']:visible",
    action: "click",
  },
  {
    id: "quoted-sender",
    title: "Lire l'expéditeur dans la citation",
    narration:
      "La citation indique l'expéditeur réel : la boîte du soutien, celle que le client a vue, et non l'adresse des ventes.",
    selector: ".modal .o_field_widget[name='body'] blockquote",
    containsText: "soutien@example.com",
    action: "assert",
  },
];
