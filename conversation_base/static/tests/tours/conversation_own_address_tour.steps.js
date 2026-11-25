// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
//
// A mail was sent to the team's own address and to two outside people. The
// conversation lists the sender and the two outside people, never the team.
export default [
  {
    id: "open-conversation",
    title: "Ouvrir la conversation",
    narration: "Ouvrons la conversation reçue par l'équipe.",
    // Exact subject: other modules' demo data has conversations whose
    // subject also starts with "Soumission".
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip='Soumission']) td[name='name']",
    action: "click",
  },
  {
    id: "open-participants",
    title: "Ouvrir l'onglet Participants",
    narration: "Ouvrons l'onglet des participants.",
    selector: ".o_notebook .nav-link[name='participants']",
    action: "click",
  },
  {
    id: "outside-people-listed",
    title: "Voir les personnes de l'extérieur",
    narration:
      "Les deux personnes de l'extérieur à qui le courriel était adressé figurent dans la liste.",
    selector: ".o_field_one2many td[name='email']",
    containsText: "marie@example.org",
    action: "assert",
  },
  {
    id: "team-address-absent",
    title: "Vérifier l'absence de l'adresse de l'équipe",
    narration:
      "L'adresse de l'équipe n'y figure pas : elle n'apparaîtra donc pas parmi les destinataires d'une réponse.",
    // Exactly three rows: the sender and the two outside people. The row
    // after the third is not a data row (the Python test names them).
    selector: ".o_field_one2many tr.o_data_row:nth-child(3) + tr:not(.o_data_row)",
    action: "assert",
  },
];
