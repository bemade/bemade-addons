// Linking an inbox email to a record by name: the "Link to a Record" dialog
// offers a searchable picker instead of a database id box.
export default [
  {
    id: "open_inbox",
    title: "Ouvrir la boîte de réception",
    narration: "Vous ouvrez la boîte de réception de Conversations.",
    selector: ".o_conversation_inbox",
    action: "assert",
  },
  {
    id: "see_item",
    title: "Repérer le courriel",
    narration:
      "Vous repérez le courriel que vous voulez classer : pas besoin de l'ouvrir.",
    selector: ".o_conversation_inbox_list .card-header",
    action: "assert",
    containsText: "Link Picker Message",
  },
  {
    id: "click_link",
    title: "Cliquer sur l'icône « Lier à un dossier »",
    narration: "Vous cliquez sur l'icône « Lier à un dossier » de la ligne.",
    selector: ".o_conversation_inbox_list .o_inbox_row_actions .o_inbox_link_record",
    action: "click",
  },
  {
    id: "type_model",
    title: "Chercher le type d'enregistrement",
    narration:
      "Dans la fenêtre qui s'ouvre, vous cherchez le type d'enregistrement, par exemple un contact.",
    selector: ".modal div[name='res_model'] input",
    action: "fill",
    value: "Contact",
  },
  {
    id: "pick_model",
    title: "Choisir le type d'enregistrement",
    narration: "Vous choisissez le type d'enregistrement dans la liste.",
    selector: ".o_select_menu_item",
    action: "click",
    containsText: "Contact",
  },
  {
    id: "search_record",
    title: "Taper une partie du nom",
    narration:
      "Vous tapez une partie du nom de l'enregistrement : pas besoin de connaître son numéro interne.",
    selector: ".modal div[name='res_id'] input",
    action: "fill",
    value: "Zed",
  },
  {
    id: "choose_record",
    title: "Choisir l'enregistrement dans la liste",
    narration: "Vous choisissez l'enregistrement voulu dans la liste qui apparaît.",
    selector: ".o-autocomplete--dropdown-item a",
    action: "click",
    containsText: "Zed Industries",
  },
  {
    id: "capture",
    title: "Cliquer sur « Capturer »",
    narration:
      "Vous cliquez sur « Capturer » pour lier le courriel à cet enregistrement.",
    selector: ".modal footer button[name='action_capture']",
    action: "click",
  },
  {
    id: "conversation_opened",
    title: "La conversation s'ouvre",
    narration: "La conversation créée s'ouvre, liée à l'enregistrement choisi.",
    selector: ".o_form_view .o_form_sheet",
    action: "assert",
  },
];
