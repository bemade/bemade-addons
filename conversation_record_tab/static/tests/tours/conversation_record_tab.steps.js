// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "open-record",
    title: "Ouvrir la fiche du client",
    narration: "Ouvrons la fiche d'un client auquel des courriels ont été liés.",
    selector: ".o_data_row td.o_data_cell",
    containsText: "Industries Tremblay",
    action: "click",
  },
  {
    id: "tab",
    title: "Repérer l'onglet Conversations pertinentes",
    narration:
      "Dans le fil de discussion, l'onglet Conversations pertinentes apparaît, avec le nombre de conversations liées à cette fiche.",
    selector: ".o-mail-Chatter .o_relevant_conversations_toggle",
    containsText: "2",
    action: "assert",
  },
  {
    id: "list",
    title: "Voir les conversations liées",
    narration:
      "La liste montre chaque conversation avec son statut, la personne assignée et la date de la dernière activité, la plus récente en premier.",
    selector: ".o_relevant_conversations .o_relevant_conversation",
    containsText: "Retard de livraison",
    action: "assert",
  },
  {
    id: "done-stays",
    title: "Retrouver aussi les conversations terminées",
    narration: "Une conversation terminée reste visible, avec son statut.",
    selector: ".o_relevant_conversations .o_relevant_conversation",
    containsText: "Soumission Q-1042",
    action: "assert",
  },
  {
    id: "open-conversation",
    title: "Ouvrir une conversation",
    narration: "Un clic sur une conversation l'ouvre directement.",
    selector: ".o_relevant_conversations .o_relevant_conversation",
    containsText: "Retard de livraison",
    action: "click",
  },
  {
    id: "conversation-form",
    title: "Lire la conversation",
    narration:
      "La conversation s'ouvre, et le fil d'Ariane permet de revenir à la fiche du client.",
    selector: ".o_breadcrumb .active",
    containsText: "Retard de livraison",
    action: "assert",
  },
];
