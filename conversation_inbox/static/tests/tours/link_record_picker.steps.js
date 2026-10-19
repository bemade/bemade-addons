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
    id: "expand_item",
    title: "Ouvrir un courriel",
    narration: "Vous ouvrez le courriel que vous voulez classer.",
    selector: ".o_conversation_inbox_list .card-header",
    action: "click",
    containsText: "Link Picker Message",
  },
  {
    id: "click_link",
    title: "Cliquer sur « Lier à un dossier »",
    narration: "Vous cliquez sur le bouton « Lier à un dossier ».",
    selector: ".o_conversation_inbox_list .card-body button.btn-secondary",
    action: "click",
    containsText: "Link to Record",
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
    narration: "Vous cliquez sur « Capturer » pour lier le courriel à cet enregistrement.",
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
