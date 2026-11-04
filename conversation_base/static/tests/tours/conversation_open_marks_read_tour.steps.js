// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
//
// The flow never relies on what else the default list holds or on the
// order of the two conversations: it first narrows the list to them with
// a name search, then checks the form pager lands on the other one.
export default [
  {
    id: "search",
    title: "Rechercher les conversations",
    narration:
      "Dans la barre de recherche, tapons « suivi lecture » pour trouver nos deux conversations.",
    selector: ".o_searchview_input",
    action: "fill",
    value: "suivi lecture",
  },
  {
    id: "search-apply",
    title: "Lancer la recherche",
    narration: "Lançons la recherche sur le nom de la conversation.",
    selector: ".o_searchview_autocomplete .o-dropdown-item.focus",
    action: "click",
  },
  {
    id: "search-applied",
    title: "Voir le critère de recherche",
    narration: "Le critère de recherche est appliqué à la liste.",
    selector: ".o_searchview_facet",
    containsText: "suivi lecture",
    action: "assert",
  },
  {
    id: "both-unread",
    title: "Repérer deux conversations non lues",
    narration: "Deux conversations sont en gras : vous ne les avez pas encore lues.",
    selector:
      ".o_list_renderer:not(:has(tr.o_data_row:nth-child(3))):has(tr.o_data_row.fw-bold td[name='name'][data-tooltip^='Psi']) tr.o_data_row.fw-bold:has(td[name='name'][data-tooltip^='Omega'])",
    action: "assert",
  },
  {
    id: "open-omega",
    title: "Ouvrir la conversation Omega",
    narration: "Ouvrons la conversation Omega depuis la liste.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Omega']) td[name='name']",
    action: "click",
  },
  {
    id: "form-opens",
    title: "Voir la conversation et son fil",
    narration: "La conversation s'ouvre avec son fil de discussion.",
    selector: ".o_control_panel .o_last_breadcrumb_item.active",
    containsText: "Omega",
    action: "assert",
  },
  {
    id: "next-record",
    title: "Passer à l'autre conversation",
    narration:
      "Avec la flèche suivante de la fiche, nous passons à l'autre conversation sans retourner à la liste.",
    selector: ".o_pager_next",
    action: "click",
  },
  {
    id: "second-record",
    title: "Voir la conversation Psi",
    narration: "La conversation Psi est maintenant ouverte.",
    selector: ".o_control_panel .o_last_breadcrumb_item.active",
    containsText: "Psi",
    action: "assert",
  },
  {
    id: "back-to-list",
    title: "Revenir à la liste",
    narration: "Retournons à la liste des conversations.",
    selector: ".o_control_panel .breadcrumb-item:not(.active) a",
    action: "click",
  },
  {
    id: "now-read",
    title: "Vérifier que les conversations sont lues",
    narration:
      "Les deux conversations ne sont plus en gras : elles sont lues pour vous, peu importe comment vous les avez ouvertes. Vos collègues les voient toujours comme non lues.",
    selector:
      ".o_list_renderer:not(:has(tr.o_data_row.fw-bold)) tr.o_data_row:has(td[name='name'][data-tooltip^='Psi'])",
    action: "assert",
  },
];
