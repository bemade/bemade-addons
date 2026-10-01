export default [
  {
    id: "see-list",
    title: "Ouvrir la liste des conversations",
    narration: "La liste affiche les conversations ouvertes, les plus récentes en premier.",
    selector: ".o_data_row .o_conversation_name",
    containsText: "Flow Alpha",
    action: "assert",
  },
  {
    id: "handle-alpha",
    title: "Cliquer sur Traitée pour la conversation Flow Alpha",
    narration:
      "Un clic sur Traitée retire la conversation de votre liste, sans la fermer pour le reste de l'équipe.",
    selector: ".o_data_row:first-child .o_conversation_action_handle",
    action: "click",
  },
  {
    id: "done-bravo",
    title: "Cliquer sur Terminée pour la conversation Flow Bravo",
    narration:
      "Terminée clôt la conversation pour toute l'équipe. Elle reste retrouvable dans le filtre Terminées.",
    selector: ".o_data_row:first-child .o_conversation_action_done",
    action: "click",
  },
  {
    id: "charlie-remains",
    title: "Vérifier que Flow Charlie est toujours dans la liste",
    narration: "Les autres conversations restent à leur place, prêtes à être traitées.",
    selector: ".o_data_row .o_conversation_name",
    containsText: "Flow Charlie",
    action: "assert",
  },
];
