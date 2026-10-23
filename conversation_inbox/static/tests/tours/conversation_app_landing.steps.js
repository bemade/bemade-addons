// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "open-main-menu",
    title: "Ouvrir le menu principal",
    narration: "Ouvrez le menu principal d'Odoo, en haut à gauche.",
    selector: ".o_navbar_apps_menu button.dropdown-toggle",
    action: "click",
  },
  {
    id: "open-app",
    title: "Ouvrir l'application Conversations",
    narration:
      "Dans le menu principal d'Odoo, cliquez sur l'application Conversations.",
    selector: ".o_app[data-menu-xmlid='conversation_base.menu_mail_conversation_root']",
    action: "click",
  },
  {
    id: "list-shown",
    title: "Voir la liste des conversations",
    narration:
      "La liste des conversations s'ouvre directement, et non votre boîte de réception.",
    selector: ".o_list_renderer",
    action: "assert",
  },
  {
    id: "facet-my-list",
    title: "Retrouver votre liste",
    narration: "Le filtre « Ma liste » est déjà appliqué.",
    selector: ".o_searchview_facet",
    containsText: "My list",
    action: "assert",
  },
  {
    id: "facet-open",
    title: "Retrouver les conversations ouvertes",
    narration:
      "Le filtre « Ouvertes » l'est aussi : vous voyez ce qui reste à traiter.",
    selector: ".o_searchview_facet",
    containsText: "Open",
    action: "assert",
  },
  {
    id: "open-inbox",
    title: "Ouvrir la boîte de réception",
    narration:
      "Votre boîte de réception reste accessible en tout temps par son propre menu, dans la barre de l'application.",
    selector:
      ".o_menu_sections [data-menu-xmlid='conversation_inbox.menu_conversation_inbox']",
    action: "click",
  },
  {
    id: "inbox-shown",
    title: "Voir la boîte de réception",
    narration: "Votre boîte de réception s'affiche, comme avant.",
    selector: ".o_conversation_inbox",
    action: "assert",
  },
];
