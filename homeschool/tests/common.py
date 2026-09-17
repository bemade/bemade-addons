# -*- coding: utf-8 -*-
"""Shared fixtures for the homeschool use-case tests.

Everything here is synthetic: the CSV shapes mirror the family repository's files
(headers are exact), the content is invented.
"""
import os
import shutil
import tempfile

from odoo import fields
from odoo.tests import TransactionCase

PDA_ITEMS_CSV = """pda_id,matiere,cycle,annee,competence,section,libelle,m1,m2,m3,m4,m5,m6,statut_3e,noyau,parent_id,source_ref,page,annee_cible,priorite,notes,projets
FLE-E-SYN-C-E,francais,3,cycle,Écrire,Syntaxe,La phrase de base,,,,,,,anchor,,,PDA-FLE-2011 p.40,,,,,
FLE-E-SYN-C-E.2.a.i,francais,3,5e-6e,Écrire,Syntaxe,Encadrement du sujet par C'est… qui,,,,,,,,1,FLE-E-SYN-C-E,PDA-FLE-2011 p.41,41,5e,core,,
MATH-MES-G.1,mathematique,3,5e,Mesurer,Temps,Estimer et mesurer le temps,,,,,,,,,,PDA-MATH-2009 p.12,12,5e,core,,P-TEST
US-C1-1820,univers_social,3,cycle,C1,,La société canadienne vers 1820,,,,,,,anchor,,,PDA-US-2009 p.8-9,,,,Kingston,
ST-MAT-D.4.a,science_technologie,3,5e-6e,Univers matériel,Mécanismes,Machines simples,,,,,,,,,,PDA-ST-2009 p.6,6,5e-6e,reinvest,,
"""

ITEMS_INTERNES_CSV = """item_id,domaine,exposition,projection,libelle,section,m1,m2,m3,m4,m5,m6,statut_3e,source_ref,page,notes
K1-ENGAGE,interne,internal,,Engagement spontané dans les blocs,K,,,,,,,,inventaire v1,,
ELA-CONV-A,anglais_ela,projected,PA-1.3,English conventions (section),A,,,,,,,,inventaire v1,,
"""

COVERS_CSV = """internal_id,covers_id,basis,note
ELA-CONV-A,FLE-E-SYN-C-E,[C],section → items it evidences
"""

DEPS_CSV = """from_id,to_id,basis,mode,note
# Prerequisite edges: from_id must come before to_id.
FLE-E-SYN-C-E,FLE-E-SYN-C-E.2.a.i,[P],hard,section first
MATH-MES-G.1,NOPE-1,[C],soft,dangling on purpose
"""

PROJETS_CSV = """projet_id,titre,type,saison,description,porte
P-TEST,Test project,projet,toute l'année,"a project, with a comma",ST;MATH
"""

TRACES_CSV = """trace_id,date,title,matieres,pda_ids,artifact_path,diffusion,notes
TR-2026-01-05-a,2026-01-05,First trace,MATH,MATH-MES-G.1;FLE-E-SYN-C-E.2.a.i,tracking/traces/TR-2026-01-05-a.pdf,INTERNAL,note one
TR-2026-01-05-b,2026-01-05,Second trace,US,US-C1-1820,,INSTITUTIONAL,
"""

HOURS_CSV = """date,block,activity,matieres,minutes_total,minutes_adult_present,notes
2026-01-05,bloc-fle,Segment 1 French,FLE,45,45,
2026-01-05,bloc-math,Segment 2 Math,MATH,45,30,
2026-01-05,lecture,Reading alone,FLE,20,0,
2026-01-06,bonus-st,Unplanned science session,ST,30,30,spontaneous
2026-01-07,journee,No school today,,0,0,day off
2026-01-08,teacher,Outside teacher 9-11,FLE;MATH,120,120,
"""

COVERAGE_CSV = """pda_id,status,evidence_refs,date_updated,notes
FLE-E-SYN-C-E,not_started,,2026-01-01,
FLE-E-SYN-C-E.2.a.i,not_started,,2026-01-01,
MATH-MES-G.1,not_started,,2026-01-01,
US-C1-1820,planned,,2026-01-01,Kingston trip
ST-MAT-D.4.a,not_started,,2026-01-01,
"""

INDIC_DEFS_CSV = """id,porte,libelle,unite,cadence,sens,seuil,source,notes
R1-ADULTE,R1 / D5,Heures de présence adulte (semaine),h/sem,hebdo,baisse,-25 % à 6 mois,hours,computed
R3-CONFLITS,R3 / I2,Conflits liés à la conformité (événements),n/sem,hebdo,baisse,,journal,
K1-ENGAGE,K1,Engagement spontané (jours sur 4),j/sem,hebdo,hausse,4/4,journal,
"""

INDIC_VALUES_CSV = """date,id,valeur,notes
2026-01-09,R3-CONFLITS,1,one event
"""

WEEK_MD = """# Semaine 2026-W02

## Jours

### 2026-01-05
- Ce qui a marché : French went fine.
- Ce qui a mal été : Math ended in a fight.
- Indicateurs du jour : R3-CONFLITS 1.

### 2026-01-06
- Ce qui a marché : bonus science.
"""

MATERIEL_README = """# materiel/

## Inventaire
| Pièce | Fichiers | Usage |
|---|---|---|
| Test fiche | `fiches/test-fiche.{html,pdf}` | 2 p. : a test fiche. FLE-E-SYN-C-E.2.a.i |
| Test poster | `affiches/test-poster.{html,pdf}` | wall poster. US-C1-1820 |
"""


def make_repo(root):
    """Write a synthetic family repository under ``root`` and return its path."""
    def w(rel, text):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    w("plan/curriculum/pda-items.csv", PDA_ITEMS_CSV)
    w("plan/curriculum/items-internes.csv", ITEMS_INTERNES_CSV)
    w("plan/curriculum/covers.csv", COVERS_CSV)
    w("plan/curriculum/deps-requires.csv", DEPS_CSV)
    w("plan/curriculum/projets.csv", PROJETS_CSV)
    w("tracking/traces.csv", TRACES_CSV)
    w("tracking/hours.csv", HOURS_CSV)
    w("tracking/coverage.csv", COVERAGE_CSV)
    w("tracking/indicateurs-definitions.csv", INDIC_DEFS_CSV)
    w("tracking/indicateurs.csv", INDIC_VALUES_CSV)
    w("tracking/journal/2026-W02/2026-W02.md", WEEK_MD)
    w("tracking/traces/TR-2026-01-05-a.pdf", "%PDF-1.4 fake\n")
    w("materiel/README.md", MATERIEL_README)
    w("materiel/fiches/test-fiche.pdf", "%PDF-1.4 fake\n")
    w("materiel/fiches/test-fiche.html", "<title>Test fiche</title>")
    return root


class HomeschoolCase(TransactionCase):
    """A student, a school year, the shipped subjects, a few curriculum items."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Student = cls.env["homeschool.student"]
        cls.Day = cls.env["homeschool.day"]
        cls.Block = cls.env["homeschool.block"]
        cls.Item = cls.env["homeschool.item"]
        cls.Trace = cls.env["homeschool.trace"]
        cls.partner = cls.env["res.partner"].create({"name": "Test Student"})
        cls.student = cls.Student.create({"partner_id": cls.partner.id, "birthdate": "2015-03-01"})
        cls.year = cls.env["homeschool.year"].create({
            "name": "2025-2026", "student_id": cls.student.id,
            "date_start": "2025-09-01", "date_end": "2026-06-30",
        })
        cls.fle = cls.env.ref("homeschool.subject_fle")
        cls.math = cls.env.ref("homeschool.subject_math")
        cls.us = cls.env.ref("homeschool.subject_us")
        cls.st = cls.env.ref("homeschool.subject_st")
        cls.item_fle = cls.Item.create({"code": "T-FLE-1", "name": "Sentence structure", "subject_id": cls.fle.id, "priorite": "core"})
        cls.item_math = cls.Item.create({"code": "T-MATH-1", "name": "Time measures", "subject_id": cls.math.id, "priorite": "core"})
        cls.item_internal = cls.Item.create({"code": "T-K1", "name": "Engagement", "subject_id": cls.env.ref("homeschool.subject_other").id, "kind": "internal"})
        cls.tmp = tempfile.mkdtemp(prefix="homeschool-test-")
        cls.repo = make_repo(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        super().tearDownClass()

    # helpers -----------------------------------------------------------
    def make_day(self, d, **vals):
        return self.Day.create(dict(student_id=self.student.id, date=d, **vals))

    def make_block(self, day, name, minutes, seq, **vals):
        return self.Block.create(dict(day_id=day.id, name=name, duration_planned=minutes, sequence=seq, **vals))

    def manager_user(self):
        return self.env["res.users"].create({
            "name": "Manager", "login": "hs_manager",
            "group_ids": [fields.Command.set([self.env.ref("homeschool.group_homeschool_manager").id])],
        })

    def portal_user(self, partner=None):
        return self.env["res.users"].create({
            "name": "Portal", "login": "hs_portal", "partner_id": (partner or self.partner).id,
            "group_ids": [fields.Command.set([self.env.ref("base.group_portal").id])],
        })

    def internal_user(self):
        return self.env["res.users"].create({
            "name": "Plain", "login": "hs_plain",
            "group_ids": [fields.Command.set([self.env.ref("base.group_user").id])],
        })
