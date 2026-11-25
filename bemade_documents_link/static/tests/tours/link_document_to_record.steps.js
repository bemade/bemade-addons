export default [
  {
    id: "select_document",
    title: "Ouvrir le document dans Documents",
    narration:
      "Dans l'application Documents, cliquez sur le document existant que vous voulez lier.",
    selector: ".o_kanban_record",
    containsText: "Procédure interne",
    action: "click",
  },
  {
    id: "click_link_to_record",
    title: "Cliquer sur « Lier à un enregistrement »",
    narration:
      "Dans la barre du haut, cliquez sur « Lier à un enregistrement ».",
    selector: "button.btn-secondary",
    containsText: "Link to Record",
    action: "click",
  },
  {
    id: "pick_model",
    title: "Choisir le type de fiche",
    narration: "Choisissez d'abord le type de fiche, par exemple un contact.",
    selector: ".modal div[name='model_id'] input",
    action: "fill",
    value: "Contact",
  },
  {
    id: "select_model",
    title: "Sélectionner le type de fiche",
    narration: "Sélectionnez le type de fiche dans la liste.",
    selector: ".ui-autocomplete .ui-menu-item a",
    containsText: "Contact",
    action: "click",
  },
  {
    id: "pick_record",
    title: "Choisir la fiche",
    narration: "Choisissez ensuite la fiche à laquelle lier le document.",
    selector: ".modal div[name='resource_ref'] input:not([readonly])",
    action: "fill",
    value: "Client demo",
  },
  {
    id: "select_record",
    title: "Sélectionner la fiche",
    narration: "Sélectionnez la fiche dans la liste proposée.",
    selector: ".ui-autocomplete .ui-menu-item a",
    containsText: "Client demo",
    action: "click",
  },
  {
    id: "confirm_link",
    title: "Cliquer sur « Lier »",
    narration: "Cliquez sur « Lier » pour confirmer.",
    selector: ".modal-footer button[name='link_to']",
    action: "click",
  },
  {
    id: "dialog_closed",
    title: "Constater que la fenêtre se ferme",
    narration:
      "La fenêtre se ferme d'elle-même et la liste des documents est à jour.",
    selector: "body:not(.modal-open) .o_kanban_record",
    containsText: "Procédure interne",
    action: "assert",
  },
];
