// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
//
// `containsText` is the English name the tour user sees; the French demo
// replays the same steps with the French names (see the flow config).
export default [
  {
    id: "open-filters",
    title: "Ouvrir le menu des filtres",
    narration: "Dans la liste des conversations, ouvrons le menu des filtres.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "favorite-unread",
    title: "Repérer le favori « Non lues »",
    narration: "Dans la section Favoris, un favori s'appelle « Non lues ».",
    selector: ".o_favorite_menu .o_favorite_item",
    containsText: "Unread",
    action: "assert",
  },
  {
    id: "favorite-unanswered",
    title: "Repérer le favori « Sans réponse »",
    narration: "Un autre s'appelle « Sans réponse ».",
    selector: ".o_favorite_menu .o_favorite_item",
    containsText: "Unanswered",
    action: "assert",
  },
  {
    id: "favorite-oldest",
    title: "Repérer le favori « Sans réponse, les plus anciennes d'abord »",
    narration:
      "Un autre trie les conversations sans réponse, les plus anciennes d'abord.",
    selector: ".o_favorite_menu .o_favorite_item",
    containsText: "Oldest unanswered first",
    action: "assert",
  },
  {
    id: "favorite-mine",
    title: "Repérer le favori « Assignées à moi »",
    narration: "Le dernier montre les conversations qui vous sont assignées.",
    selector: ".o_favorite_menu .o_favorite_item",
    containsText: "Mine",
    action: "assert",
  },
  {
    id: "apply-unread",
    title: "Appliquer le favori « Non lues »",
    narration:
      "Appliquons le favori « Non lues » pour voir qu'il fonctionne comme avant.",
    selector: ".o_favorite_menu .o_favorite_item",
    containsText: "Unread",
    action: "click",
  },
  {
    id: "facet-shown",
    title: "Voir le favori dans la barre de recherche",
    narration: "Le favori apparaît dans la barre de recherche et la liste est filtrée.",
    selector: ".o_searchview_facet",
    containsText: "Unread",
    action: "assert",
  },
];
