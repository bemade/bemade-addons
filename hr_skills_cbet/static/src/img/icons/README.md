# Job-aid icon set

One SVG per `cbet.icon` token (`<token>.svg`), loaded onto the catalog rows by
`data/cbet_icon_svg_data.xml` and printed on the field job aids and the icon
legend (`static/description/icons.html` is the contact sheet).

## Style

- 24 × 24 viewBox, intrinsic `width`/`height` of 24 (wkhtmltopdf draws nothing
  for a viewBox-only SVG), `role="img"` and a `<title>`.
- Line icons (`act-`, `outil-`, `item-`, `comp-`): 1.75 px black stroke, round
  caps and joins, transparent background.
- Severity (`sev-`): filled shapes so they pop on the recto — red disc for
  `sev-stop`, triangle for `sev-critique`, padlock for `sev-securite`.
- PPE (`epi-`): ISO 7010 mandatory-sign convention — solid blue disc
  (`#005BBB`) with a white simplified pictogram.
- Every icon must stay legible printed in black and white at 5 mm: bold simple
  shapes, no detail, no text, no fonts, no raster, no external references, no
  `<style>`, no ids, explicit `fill`/`stroke` (no CSS variables, no
  `currentColor`), at most 2 KB per file.

## Licence

Original artwork, hand-authored for this module and distributed with it under
the LGPL-3. The ISO 7010 M-series signs are used as a design cue for the PPE
icons only (own simplified likeness, no copied artwork); the catalog's
`iso_ref` names the sign each one stands for.
