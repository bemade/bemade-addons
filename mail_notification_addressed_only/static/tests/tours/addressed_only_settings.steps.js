export default [
  {
    id: "see_setting",
    title:
      "Dans la section Discussion des paramètres généraux, repérez « Courriel seulement si adressé »",
    narration:
      "Dans la section Discussion des paramètres généraux, ce réglage liste les types de documents pour lesquels les abonnés internes ne reçoivent un courriel que lorsque le message leur est adressé.",
    selector: "#addressed_only_setting",
    action: "assert",
  },
  {
    id: "add_model",
    title: "Ajoutez un type de document à la liste",
    narration:
      "Tapez le nom d'un type de document, puis choisissez-le dans la liste proposée.",
    selector: "#addressed_only_setting .o_field_many2many_tags input",
    action: "fill",
    value: "Contact",
  },
  {
    id: "pick_model",
    title: "Choisissez le type de document dans la liste",
    narration: "Sélectionnez le type de document proposé.",
    selector: ".o-autocomplete--dropdown-item a",
    action: "click",
    containsText: "Contact",
  },
  {
    id: "see_tag",
    title: "Vérifiez que le type de document est ajouté",
    narration: "Le type de document apparaît maintenant dans la liste.",
    selector: "#addressed_only_setting .o_tag",
    action: "assert",
    containsText: "Contact",
  },
  {
    id: "save",
    title: "Enregistrez les paramètres",
    narration:
      "Enregistrez : dès le prochain message, le comportement réduit s'applique à ce type de document.",
    selector: "button.o_form_button_save",
    action: "click",
    navigates: true,
  },
  {
    id: "saved",
    title: "Vérifiez que le type de document est resté dans la liste",
    narration:
      "Après l'enregistrement, le type de document est toujours dans la liste.",
    selector: "#addressed_only_setting .o_tag",
    action: "assert",
    containsText: "Contact",
  },
];
