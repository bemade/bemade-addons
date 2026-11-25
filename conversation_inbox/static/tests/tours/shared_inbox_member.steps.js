// A team member without the "Delete shared mail" permission in the inbox
// viewer: archive is there, Delete is not on the shared account, and Delete
// is there on their own personal account.
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
    id: "no_delete_on_shared",
    title: "L'icône Supprimer n'est pas offerte, mais Archiver l'est",
    narration:
      "Sans la permission de supprimer le courrier partagé, vous voyez Marquer comme lu et Archiver, mais pas l'icône Supprimer.",
    selector:
      ".o_conversation_inbox_list .o_inbox_row_actions:not(:has(.o_inbox_delete)):has(.o_inbox_mark_read) .o_inbox_archive",
    action: "assert",
  },
  {
    id: "archive_shared",
    title: "Archiver le courriel",
    narration: "Vous pouvez archiver le courriel dans la boîte partagée.",
    selector: ".o_conversation_inbox_list .o_inbox_row_actions .o_inbox_archive",
    action: "click",
  },
  {
    id: "shared_archived",
    title: "Le courriel quitte la liste",
    narration: "Le courriel archivé disparaît de la liste.",
    selector: ".o_conversation_inbox:contains('No messages on this page.')",
    action: "assert",
  },
  {
    id: "pick_personal",
    title: "Choisir votre boîte personnelle",
    narration: "Vous passez à votre propre boîte personnelle.",
    selector: "#o_conversation_inbox_transport",
    action: "selectByLabel",
    value: "Tour Personal Mailbox",
  },
  {
    id: "see_personal",
    title: "Repérer un courriel de votre boîte personnelle",
    narration: "Vous repérez un courriel de votre boîte personnelle.",
    selector: ".o_conversation_inbox_list .card-header",
    action: "assert",
    containsText: "Personal Message",
  },
  {
    id: "delete_on_personal",
    title: "L'icône Supprimer est offerte sur votre boîte personnelle",
    narration:
      "Sur votre boîte personnelle, l'icône Supprimer reste disponible : c'est vous qui décidez.",
    selector: ".o_conversation_inbox_list .o_inbox_row_actions .o_inbox_delete",
    action: "assert",
  },
];
