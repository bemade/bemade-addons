export default [
  {
    id: "open_cog",
    title: "Ouvrir le menu d'actions de la fiche produit",
    narration:
      "Depuis la fiche du produit, ouvrez le menu d'actions représenté par un engrenage.",
    selector: ".o_cp_action_menus .fa-cog",
    action: "click",
  },
  {
    id: "click_link_existing",
    title: "Choisir « Lier un document existant »",
    narration: "Choisissez « Lier un document existant ».",
    selector: ".o-dropdown-item.o_link_existing_document",
    action: "click",
  },
  {
    id: "pick_document",
    title: "Chercher le document à lier",
    narration:
      "Dans la fenêtre qui s'ouvre, tapez le nom d'un document déjà présent dans Documents.",
    selector: ".modal .o_field_many2many_tags input",
    action: "fill",
    value: "Fiche technique",
  },
  {
    id: "select_document",
    title: "Sélectionner le document",
    narration: "Sélectionnez le document dans la liste proposée.",
    selector: ".ui-autocomplete .ui-menu-item a",
    containsText: "Fiche technique",
    action: "click",
  },
  {
    id: "confirm_link",
    title: "Cliquer sur « Lier »",
    narration: "Cliquez sur « Lier » pour confirmer.",
    selector: ".modal-footer button.btn-primary",
    action: "click",
  },
  {
    id: "see_smart_button",
    title: "Constater le bouton « Documents »",
    narration:
      "La fiche se met à jour : le document est compté dans le bouton « Documents » en haut de la fiche.",
    selector: ".o-form-buttonbox .oe_stat_button .o_stat_value:contains('1')",
    action: "assert",
  },
  {
    id: "open_attachments",
    title: "Ouvrir la liste des pièces jointes",
    narration:
      "Cliquez sur le trombone sous la fiche pour afficher les pièces jointes.",
    selector: ".o-mail-Chatter-attachFiles",
    containsText: "1",
    action: "click",
  },
  {
    id: "see_attachments",
    title: "Constater les pièces jointes",
    narration:
      "Le document apparaît aussi dans la liste des pièces jointes de la fiche.",
    selector: ".o-mail-AttachmentBox",
    containsText: "Fiche technique",
    action: "assert",
  },
];
