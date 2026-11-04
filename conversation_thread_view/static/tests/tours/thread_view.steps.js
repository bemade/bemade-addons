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
    narration: "Ouvrons une conversation : c'est le formulaire habituel qui s'affiche.",
    selector: ".o_list_renderer tr.o_data_row td[name='name']",
    containsText: "Retard de livraison",
    action: "click",
  },
  {
    id: "click-thread-view",
    title: "Cliquer sur Vue fil de discussion",
    narration:
      "Le bouton Vue fil de discussion ouvre la même conversation présentée comme un fil de courriels.",
    selector: ".o_form_view button[name='action_open_thread_view']",
    action: "click",
  },
  {
    id: "thread-header",
    title: "Voir le sujet et l'état en haut du fil",
    narration:
      "Le sujet, l'état, la personne assignée, l'équipe et les étiquettes restent visibles en haut.",
    selector: ".o-conversationThreadView-subject",
    containsText: "Retard de livraison",
    action: "assert",
  },
  {
    id: "thread-header-team",
    title: "Voir l'équipe et les étiquettes",
    narration: "L'équipe et les étiquettes sont affichées sous le sujet.",
    selector: ".o-conversationThreadView-team",
    containsText: "Expédition",
    action: "assert",
  },
  {
    id: "oldest-first",
    title: "Lire le message le plus ancien en premier",
    narration:
      "Les messages se suivent du plus ancien en haut au plus récent en bas, avec l'expéditeur, la date et le contenu.",
    selector: ".o-conversationThreadView .o-mail-Message[data-thread-view-kind='mail']",
    containsText: "Client Dubois",
    action: "assert",
  },
  {
    id: "note-last",
    title: "Repérer la note interne à la fin",
    narration:
      "La note interne arrive après, clairement identifiée comme note interne.",
    selector:
      ".o-conversationThreadView .o-mail-Message[data-thread-view-kind='mail'] ~ .o-mail-Message[data-thread-view-kind='note']",
    containsText: "Note interne",
    action: "assert",
  },
  {
    id: "note-badge",
    title: "Voir le badge Note interne",
    narration: "Un badge distingue la note interne du courriel reçu.",
    selector: ".o-conversationThreadView-noteBadge",
    containsText: "Internal note",
    action: "assert",
  },
  {
    id: "reply-on-email",
    title: "Cliquer sur Répondre sous le courriel",
    narration: "Chaque courriel a son propre bouton Répondre.",
    selector:
      ".o-conversationThreadView .o-mail-Message[data-thread-view-kind='mail'] .o-mail-Message-actions button[title='Reply']",
    action: "click",
  },
  {
    id: "dialog-open",
    title: "Voir le brouillon dans une fenêtre",
    narration:
      "Le brouillon de réponse s'ouvre dans une fenêtre par-dessus le fil : vous ne le quittez pas.",
    selector: ".modal .o_field_widget[name='body'] blockquote",
    containsText: "Quand ma commande arrive-t-elle ?",
    action: "assert",
  },
  {
    id: "close-dialog",
    title: "Fermer la fenêtre sans envoyer",
    narration: "Fermons la fenêtre : nous sommes toujours sur le fil.",
    selector: ".modal-footer button",
    containsText: "Close",
    action: "click",
  },
  {
    id: "back-on-thread",
    title: "Constater qu'on reste sur le fil",
    narration: "Le fil est toujours là, sans rechargement.",
    selector: "body:not(:has(.modal)) .o-conversationThreadView-subject",
    action: "assert",
  },
  {
    id: "forward-on-email",
    title: "Cliquer sur Transférer sous le courriel",
    narration: "Transférer ouvre l'assistant de transfert pour ce message précis.",
    selector:
      ".o-conversationThreadView .o-mail-Message[data-thread-view-kind='mail'] .o-mail-Message-actions button[title='Forward']",
    action: "click",
  },
  {
    id: "forward-message-mode",
    title: "Voir le transfert d'un seul message",
    narration: "L'assistant est réglé sur ce message.",
    selector:
      ".modal .o_field_widget[name='forward_mode'] input[data-value='message']:checked",
    action: "assert",
  },
  {
    id: "cancel-forward",
    title: "Annuler le transfert",
    narration: "Annulons : rien n'est envoyé.",
    selector: ".modal-footer button",
    containsText: "Cancel",
    action: "click",
  },
  {
    id: "bottom-reply",
    title: "Cliquer sur Répondre au bas du fil",
    narration: "Au bas du fil, Répondre ouvre le brouillon partagé de la conversation.",
    selector: ".o-conversationThreadView-bottom .o-conversationThreadView-reply",
    action: "click",
  },
  {
    id: "type-reply",
    title: "Écrire la réponse",
    narration: "Écrivons notre réponse.",
    selector: ".modal .o_field_widget[name='body'] .odoo-editor-editable",
    action: "fill",
    value: "Bonjour, votre commande part vendredi.",
  },
  {
    id: "send",
    title: "Envoyer la réponse",
    narration: "Envoyons la réponse.",
    selector: ".modal-footer button[name='action_send']",
    action: "click",
  },
  {
    id: "sent-at-bottom",
    title: "Voir la réponse à la fin du fil",
    narration:
      "La fenêtre se ferme et la réponse apparaît à la fin du fil, sans recharger la page.",
    selector:
      "body:not(:has(.modal)) .o-conversationThreadView .o-mail-Message[data-thread-view-kind='note'] ~ .o-mail-Message[data-thread-view-kind='mail']",
    containsText: "Bonjour, votre commande part vendredi.",
    action: "assert",
  },
  {
    id: "bottom-forward",
    title: "Cliquer sur Transférer au bas du fil",
    narration: "Au bas du fil, Transférer concerne toute la conversation.",
    selector: ".o-conversationThreadView-bottom .o-conversationThreadView-forward",
    action: "click",
  },
  {
    id: "forward-conversation-mode",
    title: "Voir le transfert de toute la conversation",
    narration: "L'assistant est réglé sur la conversation entière.",
    selector:
      ".modal .o_field_widget[name='forward_mode'] input[data-value='conversation']:checked",
    action: "assert",
  },
  {
    id: "cancel-forward-2",
    title: "Annuler le transfert",
    narration: "Annulons de nouveau.",
    selector: ".modal-footer button",
    containsText: "Cancel",
    action: "click",
  },
  {
    id: "click-form-view",
    title: "Cliquer sur Vue formulaire",
    narration:
      "Le bouton Vue formulaire nous ramène au formulaire de la même conversation.",
    selector: "body:not(:has(.modal)) .o-conversationThreadView-formView",
    action: "click",
  },
  {
    id: "form-is-back",
    title: "Retrouver le formulaire",
    narration: "Nous voilà de retour sur le formulaire habituel.",
    selector: ".o_form_view button[name='action_open_thread_view']",
    action: "assert",
  },
];
