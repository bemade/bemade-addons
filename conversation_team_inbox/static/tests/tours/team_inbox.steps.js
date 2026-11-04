// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "mount",
    title: "Ouvrir une nouvelle équipe de conversation",
    narration: "Voici le formulaire d'une nouvelle équipe de conversation.",
    selector: ".o_form_view .o_field_widget[name='name']",
    action: "assert",
  },
  {
    id: "name",
    title: "Nommer l'équipe",
    narration: "On donne d'abord un nom à l'équipe, par exemple Ventes.",
    selector: ".o_field_widget[name='name'] input",
    action: "fill",
    value: "Ventes",
  },
  {
    id: "from-address",
    title: "Indiquer l'adresse d'expédition",
    narration:
      "Dans la section Boîte de réception d'équipe, on indique l'adresse d'expédition de l'équipe. Les réponses partiront de cette adresse, sans autre configuration.",
    selector: ".o_field_widget[name='from_address'] input",
    action: "fill",
    value: "ventes@exemple.com",
  },
  {
    id: "alias-name",
    title: "Choisir le nom de l'adresse de groupe",
    narration:
      "Puis on choisit le nom de l'adresse de groupe : les courriels qui y sont envoyés créent une conversation pour l'équipe.",
    selector: ".o_field_widget[name='alias_name'] input",
    action: "fill",
    value: "ventes",
  },
  {
    id: "save",
    title: "Enregistrer l'équipe",
    narration: "On enregistre l'équipe.",
    selector: ".o_form_button_save",
    action: "click",
  },
  {
    id: "saved",
    title: "Constater que l'équipe est enregistrée",
    narration: "L'équipe est maintenant enregistrée.",
    selector: ".o_breadcrumb .active",
    containsText: "Ventes",
    action: "assert",
  },
  {
    id: "alias-shown",
    title: "Vérifier l'adresse complète de l'équipe",
    narration:
      "L'adresse complète de l'équipe s'affiche : c'est celle que vos clients utilisent pour vous écrire.",
    selector: ".o_field_widget[name='alias_email']",
    containsText: "ventes@",
    action: "assert",
  },
];
