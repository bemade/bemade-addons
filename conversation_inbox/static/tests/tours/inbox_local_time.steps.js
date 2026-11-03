// Reading the date of an email on the Inbox screen: the time shown is the
// time where you work, in the same format as the rest of Odoo. The message
// below was sent at 18:10 Toronto time, which is 23:10 UTC.
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
    narration: "Vous repérez le courriel dans la liste.",
    selector: ".o_conversation_inbox_list .card-header",
    action: "assert",
    containsText: "Local Time Message",
  },
  {
    id: "see_local_time",
    title: "Lire l'heure du courriel",
    narration:
      "L'heure affichée à droite de la ligne est la vôtre : le courriel envoyé à 18 h 10, heure de Toronto, s'affiche à 18 h 10, et non plus à 23 h 10, l'heure universelle.",
    selector: ".o_inbox_row_date",
    action: "assert",
    containsText: "18:10",
  },
];
