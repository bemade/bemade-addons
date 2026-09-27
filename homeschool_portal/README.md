# Homeschool Portal

The portal side of `homeschool`: what the home-schooled student and the outside teacher
(personne-ressource) see and do from their own portal login.

| URL                                          | Page                                                                                                                   |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `/my/homeschool`                             | the students the user may see (his own, or the ones he follows)                                                        |
| `/my/homeschool/<student>/day[/<date>]`      | the day: blocks, material, « liste du jour » (the student ticks), print-friendly                                       |
| `/my/homeschool/<student>/week[/<iso-week>]` | the five-day grid                                                                                                      |
| `/my/homeschool/<student>/traces`            | institutional traces + the user's own pending ones; `…/<trace>` with the portal chatter; `…/submit` to hand a trace in |
| `/my/homeschool/<student>/reading`           | the reading log; `…/<book>` with the student's daily entry form                                                        |
| `/my/homeschool/<student>/file/<attachment>` | a file of a readable trace or material, always as a download                                                           |

Reads and writes run as the portal user: the record rules, access lines and model guards
of `homeschool` decide. `sudo()` is limited to three narrow, checked places (the
student's name, attaching the files of a trace the user has just created, serving a file
of a readable record) — each a follow-up for the core module, see the manifest.

Source strings are English; `i18n/fr_CA.po` carries the French. The user's own language
drives the rendering (no `website` module).

## Tests

`HttpCase`, synthetic data only:

    odoo-bin -d <db> -i homeschool_portal --test-enable --test-tags /homeschool_portal --stop-after-init
