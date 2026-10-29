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
    narration: "Ouvrons une conversation qui attend une réponse.",
    selector: ".o_list_renderer tr.o_data_row td[name='name']",
    containsText: "Retard de livraison",
    action: "click",
  },
  {
    id: "reply-at-top",
    title: "Repérer le bouton Répondre en haut du fil",
    narration:
      "En haut du fil de discussion, le bouton Répondre se trouve juste avant le bouton de note interne.",
    selector: ".o-mail-Chatter-topbar .o-mail-Chatter-conversationReply",
    containsText: "Reply",
    action: "assert",
  },
  {
    id: "click-reply",
    title: "Cliquer sur Répondre",
    narration: "Cliquons sur Répondre.",
    selector: ".o-mail-Chatter-topbar .o-mail-Chatter-conversationReply",
    containsText: "Reply",
    action: "click",
  },
  {
    id: "dialog-open",
    title: "Voir le brouillon dans une fenêtre",
    narration:
      "Le brouillon de réponse s'ouvre dans une fenêtre par-dessus la conversation : vous ne la quittez pas.",
    selector: ".modal .o_field_widget[name='body']",
    action: "assert",
  },
  {
    id: "type-reply",
    title: "Écrire la réponse",
    narration: "Écrivons le début de notre réponse.",
    selector: ".modal .o_field_widget[name='body'] .odoo-editor-editable",
    action: "fill",
    value: "Bonjour, votre commande part vendredi.",
  },
  {
    id: "close-dialog",
    title: "Fermer la fenêtre sans envoyer",
    narration: "Fermons la fenêtre sans envoyer : le texte est conservé.",
    selector: ".modal-footer button",
    containsText: "Close",
    action: "click",
  },
  {
    id: "still-on-conversation",
    title: "Constater qu'on reste sur la conversation",
    narration: "La fenêtre est fermée et la conversation est toujours là.",
    selector: "body:not(:has(.modal)) .o-mail-Chatter-topbar",
    action: "assert",
  },
  {
    id: "reopen-reply",
    title: "Cliquer de nouveau sur Répondre",
    narration: "Cliquons de nouveau sur Répondre.",
    selector: ".o-mail-Chatter-topbar .o-mail-Chatter-conversationReply",
    containsText: "Reply",
    action: "click",
  },
  {
    id: "text-kept",
    title: "Retrouver le texte écrit",
    narration: "Notre texte est toujours là : le brouillon est resté en attente.",
    selector: ".modal .o_field_widget[name='body'] .odoo-editor-editable",
    containsText: "Bonjour, votre commande part vendredi.",
    action: "assert",
  },
  {
    id: "send",
    title: "Envoyer la réponse",
    narration: "Envoyons la réponse.",
    selector: ".modal-footer button[name='action_send']",
    action: "click",
  },
  {
    id: "sent-in-thread",
    title: "Voir la réponse dans le fil",
    narration:
      "La fenêtre se ferme, nous sommes toujours sur la conversation et la réponse apparaît dans le fil, sans recharger la page.",
    selector: "body:not(:has(.modal)) .o-mail-Message",
    containsText: "Bonjour, votre commande part vendredi.",
    action: "assert",
  },
  {
    id: "point-at-email",
    title: "Pointer le courriel reçu",
    narration: "Pour répondre à un courriel précis, pointons-le dans le fil.",
    selector: ".o-mail-Message .o-mail-Message-content",
    containsText: "Quand ma commande arrive-t-elle ?",
    action: "click",
  },
  {
    id: "reply-to-email",
    title: "Cliquer sur Répondre sur le courriel",
    narration: "Chaque courriel du fil a sa propre action Répondre.",
    selector: ".o-mail-Message-actions button[title='Reply']:visible",
    action: "click",
  },
  {
    id: "quoted",
    title: "Voir le courriel cité dans le brouillon",
    narration:
      "Le courriel est cité dans le brouillon, sous notre texte, et la fenêtre indique à quel courriel nous répondons.",
    selector: ".modal .o_field_widget[name='body'] blockquote",
    containsText: "Quand ma commande arrive-t-elle ?",
    action: "assert",
  },
];
