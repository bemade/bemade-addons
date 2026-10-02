// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "mount",
    title: "Afficher la liste de triage",
    narration: "Voici la liste de triage de vos conversations.",
    selector: ".o_list_renderer",
    action: "assert",
  },
  {
    id: "alpha-row",
    title: "Repérer la conversation non lue",
    narration:
      "Une conversation non lue apparaît en gras, avec un aperçu du dernier message et l'enregistrement lié.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha']).fw-bold",
    containsText: "Snippet for Alpha",
    action: "assert",
  },
  {
    id: "alpha-linked",
    title: "Voir l'enregistrement lié",
    narration: "L'enregistrement lié apparaît sur la ligne.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha'])",
    containsText: "Tour Linked Co",
    action: "assert",
  },
  {
    id: "alpha-time",
    title: "Voir l'heure relative",
    narration: "Et l'heure relative du dernier message.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha']) .o_conversation_time",
    containsText: "hours ago",
    action: "assert",
  },
  {
    id: "mark-read",
    title: "Marquer comme lue",
    narration: "Marquons-la comme lue d'un clic.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha']) button[name='action_triage_mark_read']",
    action: "click",
  },
  {
    id: "alpha-read",
    title: "Vérifier qu'elle n'est plus en gras",
    narration: "Elle n'est plus en gras, mais reste dans la liste.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha']):not(.fw-bold)",
    action: "assert",
  },
  {
    id: "hide",
    title: "Masquer la conversation",
    narration:
      "Masquons-la : elle quitte seulement votre liste, pas celle de vos collègues.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha']) button[name='action_triage_hide']",
    action: "click",
  },
  {
    id: "alpha-gone",
    title: "Vérifier qu'elle a quitté la liste",
    narration: "La conversation a disparu de votre liste.",
    selector: ".o_list_renderer:not(:has(td[name='name'][data-tooltip^='Alpha']))",
    action: "assert",
  },
  {
    id: "hidden-open-filters",
    title: "Ouvrir le menu des filtres",
    narration: "Ouvrons le menu des filtres.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "hidden-toggle",
    title: "Basculer le filtre « Hidden by me »",
    narration: "Activons ou désactivons le filtre « Hidden by me ».",
    selector: ".o_filter_menu .o_menu_item",
    containsText: "Hidden by me",
    action: "click",
  },
  {
    id: "hidden-close-filters",
    title: "Fermer le menu des filtres",
    narration: "Refermons le menu.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "unhide",
    title: "Réafficher la conversation",
    narration: "On la retrouve dans les conversations masquées; réaffichons-la.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha']) button[name='action_triage_unhide']",
    action: "click",
  },
  {
    id: "hidden-off-open-filters",
    title: "Ouvrir le menu des filtres",
    narration: "Ouvrons le menu des filtres.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "hidden-off-toggle",
    title: "Basculer le filtre « Hidden by me »",
    narration: "Activons ou désactivons le filtre « Hidden by me ».",
    selector: ".o_filter_menu .o_menu_item",
    containsText: "Hidden by me",
    action: "click",
  },
  {
    id: "hidden-off-close-filters",
    title: "Fermer le menu des filtres",
    narration: "Refermons le menu.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "alpha-back",
    title: "Vérifier son retour",
    narration: "Elle est de retour dans votre liste.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Alpha'])",
    action: "assert",
  },
  {
    id: "done",
    title: "Terminer la conversation",
    narration: "Terminons la conversation Beta : elle est close pour toute l'équipe.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Beta']) button[name='action_triage_done']",
    action: "click",
  },
  {
    id: "beta-gone",
    title: "Vérifier qu'elle a quitté la liste",
    narration: "Elle quitte la liste.",
    selector: ".o_list_renderer:not(:has(td[name='name'][data-tooltip^='Beta']))",
    action: "assert",
  },
  {
    id: "done-open-filters",
    title: "Ouvrir le menu des filtres",
    narration: "Ouvrons le menu des filtres.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "done-toggle",
    title: "Basculer le filtre « Done »",
    narration: "Activons ou désactivons le filtre « Done ».",
    selector: ".o_filter_menu .o_menu_item",
    containsText: "Done",
    action: "click",
  },
  {
    id: "done-close-filters",
    title: "Fermer le menu des filtres",
    narration: "Refermons le menu.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "reopen",
    title: "Rouvrir la conversation",
    narration: "Dans les conversations terminées, on peut la rouvrir.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Beta']) button[name='action_triage_reopen']",
    action: "click",
  },
  {
    id: "done-off-open-filters",
    title: "Ouvrir le menu des filtres",
    narration: "Ouvrons le menu des filtres.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "done-off-toggle",
    title: "Basculer le filtre « Done »",
    narration: "Activons ou désactivons le filtre « Done ».",
    selector: ".o_filter_menu .o_menu_item",
    containsText: "Done",
    action: "click",
  },
  {
    id: "done-off-close-filters",
    title: "Fermer le menu des filtres",
    narration: "Refermons le menu.",
    selector: ".o_control_panel .o_searchview_dropdown_toggler",
    action: "click",
  },
  {
    id: "beta-back",
    title: "Vérifier qu'elle est rouverte",
    narration: "Elle est de nouveau ouverte.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Beta'])",
    action: "assert",
  },
  {
    id: "snooze",
    title: "Reporter la conversation",
    narration: "Reportons la conversation Gamma à plus tard.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Gamma']) button[name='action_triage_open_snooze_wizard']",
    action: "click",
  },
  {
    id: "snooze-apply",
    title: "Appliquer le report par défaut (demain)",
    narration: "Gardons le choix par défaut, demain matin, et appliquons.",
    selector: ".modal button[name='action_apply']",
    action: "click",
  },
  {
    id: "gamma-gone",
    title: "Vérifier qu'elle a quitté la liste",
    narration: "Elle reviendra d'elle-même à l'heure choisie.",
    selector: ".o_list_renderer:not(:has(td[name='name'][data-tooltip^='Gamma']))",
    action: "assert",
  },
  {
    id: "assign",
    title: "Assigner la conversation",
    narration: "Assignons la conversation Delta à un collègue.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Delta']) button[name='action_triage_open_assign_wizard']",
    action: "click",
  },
  {
    id: "assign-fill",
    title: "Chercher le collègue",
    narration: "Choisissons le collègue.",
    selector: ".modal div[name='user_id'] input",
    action: "fill",
    value: "Tour Colleague",
  },
  {
    id: "assign-pick",
    title: "Sélectionner le collègue",
    narration: "Sélectionnons-le dans la liste.",
    selector: ".o-autocomplete--dropdown-item",
    containsText: "Tour Colleague",
    action: "click",
  },
  {
    id: "assign-apply",
    title: "Appliquer l'assignation",
    narration: "Appliquons l'assignation.",
    selector: ".modal button[name='action_apply']",
    action: "click",
  },
  {
    id: "delta-assigned",
    title: "Vérifier l'assignation",
    narration: "Le nom du collègue apparaît sur la ligne.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Delta'])",
    containsText: "Tour Colleague",
    action: "assert",
  },
  {
    id: "select-epsilon",
    title: "Cocher une première conversation",
    narration: "Pour agir sur plusieurs conversations, cochons-en une première.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Epsilon']) .o_list_record_selector input",
    action: "click",
  },
  {
    id: "select-zeta",
    title: "Cocher une deuxième conversation",
    narration: "Puis une deuxième.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Zeta']) .o_list_record_selector input",
    action: "click",
  },
  {
    id: "bulk-done",
    title: "Terminer la sélection",
    narration: "Terminons-les toutes d'un seul clic.",
    selector: ".o_control_panel button[name='action_triage_done']",
    action: "click",
  },
  {
    id: "epsilon-gone",
    title: "Vérifier la première",
    narration: "La première a quitté la liste.",
    selector: ".o_list_renderer:not(:has(td[name='name'][data-tooltip^='Epsilon']))",
    action: "assert",
  },
  {
    id: "zeta-gone",
    title: "Vérifier la deuxième",
    narration: "La deuxième aussi.",
    selector: ".o_list_renderer:not(:has(td[name='name'][data-tooltip^='Zeta']))",
    action: "assert",
  },
  {
    id: "eta-stays",
    title: "Vérifier que les autres restent",
    narration: "Les conversations non sélectionnées restent en place.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Eta']):not(.o_data_row_selected):not(:has(.o_list_record_selector input:checked))",
    action: "assert",
  },
  {
    id: "open-eta",
    title: "Ouvrir une conversation",
    narration: "Cliquons sur une ligne pour ouvrir la conversation.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Eta']) td[name='name']",
    action: "click",
  },
  {
    id: "form-opens",
    title: "Voir la conversation et son fil",
    narration: "La conversation s'ouvre avec son fil de discussion.",
    selector: ".o_form_view .o-mail-Chatter",
    action: "assert",
  },
];
