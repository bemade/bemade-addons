"""UC-CAT-10 (extended) — JOB_AID markdown → structured cbet.job.aid.

AC1: recto H2 blocks → sections typed from their heading token (ppe / tools /
     stop / data / photos / custom); " · "-joined items and bullets → lines; a
     leading :token: → cbet.icon.
AC2: verso H2 → phase sections; "- [ ]" items → lines; a markdown table in a
     section → note_html.
AC3: the "variante:" meta names the variant; one job aid per (competency,
     variant); unknown tokens warn, the line is kept without an icon; a legacy
     layout (no RECTO/VERSO markers) imports as one custom block + warning.
AC4: re-import of the same job aid is a no-op (rows kept); a changed one is
     rebuilt; EN edition = source text when aligned, else French in both.
"""
from odoo.tests.common import tagged

from .common import CbetCommon
from .test_cat_10_import import EVAL, FICHE

JOB_AID = """<!-- job-aid | competence: XIM-01 | statut: Pré-publication | version: Pré-publication | icones: CATALOGUE_GRAPHIQUE -->

<!-- ============================== RECTO ============================== -->
# Compétence exemple d'import — `XIM-01`

## :epi-lunettes: EPI
:epi-lunettes: lunettes · :epi-chaussures: chaussures *(banc sous pression)*

## :outil-cles: Outils
:outil-cles: clés · **coupe de démonstration** du banc · :outil-formulaire: formulaire `UNI-02`

## :sev-stop: STOP — escalader
- :sev-securite: Banc **sous pression** — pointer, ne pas toucher
- Anomalie observée → **signaler**, jamais corriger
- :sev-critique: Composante **mal nommée** = échec

## :act-donnees: Données à prendre (`UNI-02`)
Pression **entrée / sortie** · **débit** · :act-temperature: température

## :act-photo: Photos
État final du banc

<!-- ============================== VERSO ============================== -->
<div class="pb"></div>

# Procédure — checklist

## 1. Énoncer le principe
- [ ] **Point de lecture** — défini à voix haute
- [ ] :item-sel: **Sel = régénérant** nommé
  - sous-étape seulement si indispensable

## 2. Pointer les composantes
- [ ] **Réservoir** pointé
- [ ] :act-eau: Cheminement suivi

## Vérifier avant de quitter
- [ ] :sev-securite: **Rien touché, rien ouvert**
- [ ] :act-donnees: Données consignées

| Repère | Règle |
| --- | --- |
| Unité | **kPa** — lecture entrée |
"""

JOB_AID_EN = """<!-- job-aid | competence: XIM-01 | statut: Pre-release | version: Pre-release | icones: CATALOGUE_GRAPHIQUE -->

<!-- ============================== RECTO ============================== -->
# Import example competency — `XIM-01`

## :epi-lunettes: PPE
:epi-lunettes: goggles · :epi-chaussures: safety shoes *(pressurised bench)*

## :outil-cles: Tools
:outil-cles: wrenches · **demonstration cutaway** of the bench · :outil-formulaire: form `UNI-02`

## :sev-stop: STOP — escalate
- :sev-securite: Bench **under pressure** — point, do not touch
- Anomaly observed → **report**, never fix
- :sev-critique: Component **misnamed** = fail

## :act-donnees: Data to record (`UNI-02`)
Pressure **in / out** · **flow** · :act-temperature: temperature

## :act-photo: Photos
Final state of the bench

<!-- ============================== VERSO ============================== -->
<div class="pb"></div>

# Procedure — checklist

## 1. State the principle
- [ ] **Reading point** — defined out loud
- [ ] :item-sel: **Salt = regenerant** named
  - sub-step only when essential

## 2. Point out the components
- [ ] **Tank** pointed out
- [ ] :act-eau: Water path followed

## Check before leaving
- [ ] :sev-securite: **Nothing touched, nothing opened**
- [ ] :act-donnees: Data recorded

| Marker | Rule |
| --- | --- |
| Unit | **kPa** — inlet reading |
"""

JOB_AID_VARIANT = JOB_AID.replace(
    "competence: XIM-01 |", "competence: XIM-01 | variante: BANC |"
).replace("# Compétence exemple d'import — `XIM-01`",
          "# Compétence exemple d'import — Banc — `XIM-01`")

LEGACY = """<!-- job-aid | competence: XIM-01 | statut: Pilote | icones: LEGENDE_JOB_AIDS -->
# Compétence exemple d'import — `XIM-01`

## 🦺 EPI
🥽 lunettes · 👟 chaussures

## 🛑 STOP — escalader
- Banc sous pression

<div class="pb"></div>

# Procédure — checklist

## Préparer 🔒
- [ ] Isoler le banc
"""


@tagged("post_install", "-at_install")
class TestCatJobAid(CbetCommon):
    def _fr(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        return "fr_CA"

    def test_icon_catalog_is_seeded(self):
        Icon = self.env["cbet.icon"]
        self.assertEqual(Icon.search_count([]), 55)
        lunettes = Icon.search([("token", "=", "epi-lunettes")])
        self.assertEqual(lunettes.category, "epi")
        self.assertEqual(lunettes.emoji, "🥽")
        self.assertEqual(lunettes.iso_ref, "ISO 7010 M004")
        self.assertEqual(lunettes.display_name, "🥽 Safety glasses")
        # one of each category, incl. the ones without an emoji preview
        for token, cat in [("sev-stop", "sev"), ("act-isoler", "act"), ("outil-boyau", "outil"),
                           ("item-fds", "item"), ("comp-vanne", "comp")]:
            icon = Icon.search([("token", "=", token)])
            self.assertEqual(icon.category, cat, token)

    def test_icon_token_is_normalised_and_unique(self):
        Icon = self.env["cbet.icon"]
        icon = Icon.create({"token": ":xtest-chose:", "name": "Chose"})
        self.assertEqual(icon.token, "xtest-chose")
        self.assertFalse(icon.category)                 # unknown prefix
        self.assertEqual(icon.display_name, "Chose")
        from psycopg2.errors import UniqueViolation
        from odoo.tools import mute_logger
        with self.assertRaises(UniqueViolation), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            Icon.create({"token": "xtest-chose", "name": "Doublon"})

    def test_parse_recto_and_verso(self):
        parsed = self.env["cbet.competency"]._parse_job_aid_md(JOB_AID)
        self.assertIsNone(parsed["variant"])
        self.assertEqual(parsed["warnings"], [])
        recto, verso = parsed["recto"], parsed["verso"]
        self.assertEqual([s["kind"] for s in recto], ["ppe", "tools", "stop", "data", "photos"])
        self.assertEqual([s["icon"] for s in recto],
                         ["epi-lunettes", "outil-cles", "sev-stop", "act-donnees", "act-photo"])
        self.assertEqual([s["name"] for s in recto],
                         ["EPI", "Outils", "STOP — escalader", "Données à prendre (UNI-02)", "Photos"])
        # inline " · " items → lines, leading token → icon, markdown markers stripped
        self.assertEqual(recto[0]["lines"], [
            {"icon": "epi-lunettes", "text": "lunettes"},
            {"icon": "epi-chaussures", "text": "chaussures (banc sous pression)"},
        ])
        self.assertEqual(recto[1]["lines"], [
            {"icon": "outil-cles", "text": "clés"},
            {"icon": None, "text": "coupe de démonstration du banc"},
            {"icon": "outil-formulaire", "text": "formulaire UNI-02"},
        ])
        # bullets → lines
        self.assertEqual([(ln["icon"], ln["text"]) for ln in recto[2]["lines"]], [
            ("sev-securite", "Banc sous pression — pointer, ne pas toucher"),
            (None, "Anomalie observée → signaler, jamais corriger"),
            ("sev-critique", "Composante mal nommée = échec"),
        ])
        self.assertEqual(recto[3]["lines"][2], {"icon": "act-temperature", "text": "température"})
        self.assertEqual(recto[4]["lines"], [{"icon": None, "text": "État final du banc"}])
        # verso: phases, checklist items (sub-steps are lines too), table → note
        self.assertEqual([s["kind"] for s in verso], ["phase"] * 3)
        self.assertEqual([s["name"] for s in verso],
                         ["1. Énoncer le principe", "2. Pointer les composantes",
                          "Vérifier avant de quitter"])
        self.assertEqual([(ln["icon"], ln["text"]) for ln in verso[0]["lines"]], [
            (None, "Point de lecture — défini à voix haute"),
            ("item-sel", "Sel = régénérant nommé"),
            (None, "sous-étape seulement si indispensable"),
        ])
        self.assertEqual(verso[2]["lines"][0]["icon"], "sev-securite")
        self.assertIn("<table>", verso[2]["note_html"])
        self.assertIn("<strong>kPa</strong>", verso[2]["note_html"])
        self.assertFalse(verso[0]["note_html"])
        self.assertFalse(recto[0]["note_html"])

    def test_tokens_inside_headings_and_lines_never_survive_as_text(self):
        md = JOB_AID.replace(
            "## 2. Pointer les composantes\n- [ ] **Réservoir** pointé\n- [ ] :act-eau: Cheminement suivi",
            "## 2. Pointer — :sev-securite: sécuriser :act-photo:\n"
            "- [ ] **Réservoir** pointé · :act-inspection: aucun média dans le tube\n"
            "- [ ] :act-eau: Cheminement suivi :sev-critique: sans toucher")
        parsed = self.env["cbet.competency"]._parse_job_aid_md(md)
        self.assertEqual(parsed["warnings"], [])
        icons = self.env["cbet.icon"]._by_token()
        phase = parsed["verso"][1]
        # the first token of a heading is the section icon; the rest become emoji
        self.assertEqual(phase["icon"], "sev-securite")
        self.assertEqual(phase["name"], "2. Pointer — sécuriser %s" % icons["act-photo"].emoji)
        # a token inside a line's text is replaced by its emoji
        self.assertEqual(phase["lines"][0], {
            "icon": None,
            "text": "Réservoir pointé · %s aucun média dans le tube" % icons["act-inspection"].emoji})
        self.assertEqual(phase["lines"][1], {
            "icon": "act-eau",
            "text": "Cheminement suivi %s sans toucher" % icons["sev-critique"].emoji})
        # an unknown inline token warns and is dropped
        parsed = self.env["cbet.competency"]._parse_job_aid_md(
            JOB_AID.replace("- [ ] **Réservoir** pointé", "- [ ] **Réservoir** :x-y: pointé"))
        self.assertEqual(parsed["verso"][1]["lines"][0], {"icon": None, "text": "Réservoir pointé"})
        self.assertEqual(parsed["warnings"],
                         ["unknown icon token :x-y: in '2. Pointer les composantes'"])

    def test_variant_comes_from_the_meta_comment(self):
        parsed = self.env["cbet.competency"]._parse_job_aid_md(JOB_AID_VARIANT)
        self.assertEqual(parsed["variant"], "BANC")

    def test_unknown_token_warns_and_keeps_the_line(self):
        md = JOB_AID.replace("- [ ] :act-eau: Cheminement suivi",
                             "- [ ] :act-inconnu: Cheminement suivi")
        parsed = self.env["cbet.competency"]._parse_job_aid_md(md)
        line = parsed["verso"][1]["lines"][1]
        self.assertEqual(line, {"icon": None, "text": "Cheminement suivi"})
        self.assertEqual(parsed["warnings"],
                         ["unknown icon token :act-inconnu: in '2. Pointer les composantes'"])

    def test_legacy_layout_falls_back_to_one_block(self):
        parsed = self.env["cbet.competency"]._parse_job_aid_md(LEGACY)
        self.assertEqual(len(parsed["recto"]), 1)
        self.assertEqual(parsed["verso"], [])
        block = parsed["recto"][0]
        self.assertEqual(block["kind"], "custom")
        self.assertEqual(block["lines"], [])
        self.assertIn("<h2>🦺 EPI</h2>", block["note_html"])
        self.assertIn("☐ Isoler le banc", block["note_html"])
        self.assertNotIn("job-aid |", block["note_html"])          # meta comment gone
        self.assertNotIn('class="pb"', block["note_html"])
        self.assertEqual(parsed["warnings"],
                         ["legacy layout (no RECTO/VERSO markers): kept as a single block"])

    def test_import_builds_the_structure(self):
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID}]})
        self.assertTrue(comp.has_job_aid)
        aid = comp.job_aid_ids
        self.assertEqual(len(aid), 1)
        self.assertFalse(aid.variant)
        self.assertEqual(aid.name, "XIM-01 — Compétence exemple d'import")
        recto = aid.section_ids.filtered(lambda s: s.face == "recto").sorted("sequence")
        verso = aid.section_ids.filtered(lambda s: s.face == "verso").sorted("sequence")
        self.assertEqual(recto.mapped("kind"), ["ppe", "tools", "stop", "data", "photos"])
        self.assertEqual(recto[0].icon_id.token, "epi-lunettes")
        self.assertEqual(recto[0].line_ids.mapped("icon_id.token"),
                         ["epi-lunettes", "epi-chaussures"])
        self.assertEqual(recto[0].line_ids.mapped("text"),
                         ["lunettes", "chaussures (banc sous pression)"])
        self.assertEqual(verso.mapped("kind"), ["phase"] * 3)
        self.assertEqual(verso[2].line_ids[0].icon_id.token, "sev-securite")
        self.assertIn("<table>", verso[2].note_html)
        # no token text survives anywhere
        for line in aid.section_ids.line_ids:
            self.assertNotRegex(line.text, r":[a-z]+-[a-z-]+:")

    def test_variants_are_separate_job_aids(self):
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [
                {"variant": None, "md": JOB_AID},
                {"variant": "BANC", "md": JOB_AID_VARIANT},
            ]})
        aids = comp.job_aid_ids.sorted("sequence")
        self.assertEqual(len(aids), 2)
        self.assertEqual(aids.mapped("variant"), [False, "BANC"])
        self.assertEqual(aids[1].name, "XIM-01 — Compétence exemple d'import [BANC]")
        # the filename variant is the fallback when the meta has none
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": "RO", "md": JOB_AID}]})
        self.assertIn("RO", comp.job_aid_ids.mapped("variant"))

    def test_duplicate_variant_is_refused(self):
        from odoo.exceptions import ValidationError
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID}]})
        with self.assertRaises(ValidationError):
            self.env["cbet.job.aid"].create({"competency_id": comp.id})

    def test_reimport_same_job_aid_keeps_rows_changed_one_rebuilds(self):
        Comp = self.env["cbet.competency"]
        docs = {"JOB_AID": [{"variant": None, "md": JOB_AID}]}
        comp, _ = Comp._import_markdown(FICHE, EVAL, docs=docs)
        comp.with_user(self.manager).action_publish()
        ids = comp.job_aid_ids.ids
        section_ids = comp.job_aid_ids.section_ids.ids
        again, _ = Comp._import_markdown(FICHE, EVAL, docs=docs)
        self.assertEqual(again.state, "published")
        self.assertEqual(again.job_aid_ids.ids, ids)
        self.assertEqual(again.job_aid_ids.section_ids.ids, section_ids)
        changed = JOB_AID.replace("- [ ] **Réservoir** pointé", "- [ ] **Réservoir** et riser pointés")
        again, _ = Comp._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": changed}]})
        self.assertEqual(again.state, "draft")
        self.assertNotEqual(again.job_aid_ids.section_ids.ids, section_ids)
        self.assertIn("Réservoir et riser pointés", again.job_aid_ids.section_ids.line_ids.mapped("text"))

    def test_english_edition_is_the_source_text(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID, "md_en": JOB_AID_EN}]})
        recto = comp.job_aid_ids.section_ids.filtered(lambda s: s.face == "recto").sorted("sequence")
        self.assertEqual(recto[0].with_context(lang="en_US").name, "PPE")
        self.assertEqual(recto[0].with_context(lang=fr).name, "EPI")
        self.assertEqual(recto[0].line_ids[0].with_context(lang="en_US").text, "goggles")
        self.assertEqual(recto[0].line_ids[0].with_context(lang=fr).text, "lunettes")
        verso = comp.job_aid_ids.section_ids.filtered(lambda s: s.face == "verso").sorted("sequence")
        self.assertIn("inlet reading", verso[2].with_context(lang="en_US").note_html)
        self.assertIn("lecture entrée", verso[2].with_context(lang=fr).note_html)
        # the French drives the structure: icons come from it
        self.assertEqual(recto[0].line_ids.mapped("icon_id.token"), ["epi-lunettes", "epi-chaussures"])

    def test_misaligned_english_job_aid_is_ignored_with_a_warning(self):
        fr = self._fr()
        warnings = []
        short = JOB_AID_EN.replace("- [ ] :act-eau: Water path followed\n", "")
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID, "md_en": short}]},
            warnings=warnings)
        recto = comp.job_aid_ids.section_ids.filtered(lambda s: s.face == "recto").sorted("sequence")
        self.assertEqual(recto[0].with_context(lang="en_US").name, "EPI")
        self.assertEqual(recto[0].with_context(lang=fr).name, "EPI")
        self.assertIn(("XIM-01", "JOB_AID: English edition does not align with the French "
                                 "(sections/lines differ); French kept in both languages"),
                      warnings)

    def test_late_english_job_aid_applies_in_place(self):
        fr = self._fr()
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID}]})
        comp.with_user(self.manager).action_publish()
        section_ids = comp.job_aid_ids.section_ids.ids
        again, _ = Comp._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID, "md_en": JOB_AID_EN}]})
        self.assertEqual(again.state, "published")
        self.assertEqual(again.job_aid_ids.section_ids.ids, section_ids)
        recto = again.job_aid_ids.section_ids.filtered(lambda s: s.face == "recto").sorted("sequence")
        self.assertEqual(recto[0].with_context(lang="en_US").name, "PPE")
        self.assertEqual(recto[0].with_context(lang=fr).name, "EPI")

    def test_job_aid_copy_duplicates_the_chain(self):
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"JOB_AID": [{"variant": None, "md": JOB_AID}]})
        aid = comp.job_aid_ids
        dup = aid.copy({"variant": "COPIE"})
        self.assertEqual(len(dup.section_ids), len(aid.section_ids))
        self.assertEqual(len(dup.section_ids.line_ids), len(aid.section_ids.line_ids))
        self.assertEqual(dup.name, "XIM-01 — Compétence exemple d'import [COPIE]")
