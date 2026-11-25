// A user holding the "Delete shared mail" permission: Delete is offered on
// the shared account and moves the mail to the mailbox Trash.
export default [
  {
    id: "open_inbox",
    title: "Ouvrir la boîte de réception",
    narration: "Vous ouvrez la boîte de réception de Conversations.",
    selector: ".o_conversation_inbox",
    action: "assert",
  },
  {
    id: "pick_shared",
    title: "Choisir la boîte partagée",
    narration: "Vous choisissez la boîte partagée de l'équipe.",
    selector: "#o_conversation_inbox_transport",
    action: "selectByLabel",
    value: "Tour Shared Mailbox",
  },
  {
    id: "see_shared",
    title: "Repérer un courriel de la boîte partagée",
    narration:
      "Vous repérez un courriel de la boîte partagée, sans avoir besoin de l'ouvrir.",
    selector: ".o_conversation_inbox_list .card-header",
    action: "assert",
    containsText: "Shared Message",
  },
  {
    id: "delete_offered",
    title: "Cliquer sur l'icône Supprimer",
    narration:
      "Avec la permission de supprimer le courrier partagé, l'icône Supprimer est offerte sur la ligne.",
    selector: ".o_conversation_inbox_list .o_inbox_row_actions .o_inbox_delete",
    action: "click",
  },
  {
    id: "confirm_delete",
    title: "Confirmer la suppression",
    narration:
      "Vous confirmez : le courriel est déplacé vers la corbeille de la boîte, où il reste récupérable.",
    selector: ".modal footer button:contains('Delete')",
    action: "click",
  },
  {
    id: "shared_deleted",
    title: "Le courriel quitte la liste",
    narration: "Le courriel supprimé disparaît de la liste.",
    selector:
      ".o_conversation_inbox:not(:has(.modal)):contains('No messages on this page.')",
    action: "assert",
  },
];
