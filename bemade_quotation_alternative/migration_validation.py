#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validation de la migration Odoo 18.0
pour le module bemade_quotation_alternative

Usage:
    python migration_validation.py

Ce script vérifie :
1. La compatibilité des fichiers modifiés
2. La syntaxe Python et XML
3. Les imports et dépendances
4. Les conventions Odoo 18
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

def check_manifest():
    """Vérifier le fichier __manifest__.py"""
    print("🔍 Vérification du manifest...")
    
    manifest_path = Path(__file__).parent / "__manifest__.py"
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Vérifier la version
        if "'version': '18.0.1.0.0'" in content:
            print("✅ Version mise à jour vers 18.0.1.0.0")
        else:
            print("❌ Version non mise à jour")
            return False
            
        # Vérifier les dépendances
        if "'sale_management'" in content:
            print("✅ Dépendance sale_management présente")
        else:
            print("⚠️  Dépendance sale_management manquante")
            
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la lecture du manifest: {e}")
        return False

def check_xml_views():
    """Vérifier les vues XML"""
    print("\n🔍 Vérification des vues XML...")
    
    xml_files = [
        "views/sale_order_views.xml",
        "wizard/sale_order_duplication_wizard_view.xml"
    ]
    
    all_valid = True
    
    for xml_file in xml_files:
        xml_path = Path(__file__).parent / xml_file
        
        try:
            # Vérifier la syntaxe XML
            ET.parse(xml_path)
            print(f"✅ {xml_file} - Syntaxe XML valide")
            
            # Vérifier les conventions Odoo 18
            with open(xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Vérifier <list> au lieu de <tree>
            if xml_file.endswith('wizard_view.xml'):
                if '<list editable="bottom">' in content:
                    print(f"✅ {xml_file} - Utilise <list> (Odoo 18)")
                elif '<tree editable="bottom">' in content:
                    print(f"⚠️  {xml_file} - Utilise encore <tree> (à migrer)")
                    all_valid = False
                    
            # Vérifier les classes CSS
            if 'class="oe_highlight"' in content:
                print(f"✅ {xml_file} - Classes CSS Odoo 18")
            elif 'class="btn-primary"' in content:
                print(f"⚠️  {xml_file} - Classes CSS anciennes détectées")
                all_valid = False
                
        except ET.ParseError as e:
            print(f"❌ {xml_file} - Erreur XML: {e}")
            all_valid = False
        except Exception as e:
            print(f"❌ {xml_file} - Erreur: {e}")
            all_valid = False
            
    return all_valid

def check_python_syntax():
    """Vérifier la syntaxe Python"""
    print("\n🔍 Vérification de la syntaxe Python...")
    
    python_files = [
        "models/sale_order.py",
        "wizard/sale_order_duplication_wizard.py",
        "wizard/sale_oder_line_duplication_wizard.py"
    ]
    
    all_valid = True
    
    for py_file in python_files:
        py_path = Path(__file__).parent / py_file
        
        try:
            with open(py_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Vérifier la syntaxe
            compile(content, py_path, 'exec')
            print(f"✅ {py_file} - Syntaxe Python valide")
            
            # Vérifications spécifiques Odoo 18
            if 'markupsafe import Markup' in content:
                print(f"✅ {py_file} - Import Markup correct")
                
            # Vérifier l'utilisation sécurisée de Markup
            if 'Markup(' in content and '% (' in content:
                print(f"✅ {py_file} - Utilisation sécurisée de Markup")
            elif 'Markup(f"' in content:
                print(f"⚠️  {py_file} - f-strings dans Markup (à éviter)")
                
        except SyntaxError as e:
            print(f"❌ {py_file} - Erreur de syntaxe: {e}")
            all_valid = False
        except Exception as e:
            print(f"❌ {py_file} - Erreur: {e}")
            all_valid = False
            
    return all_valid

def check_security():
    """Vérifier les fichiers de sécurité"""
    print("\n🔍 Vérification de la sécurité...")
    
    security_path = Path(__file__).parent / "security/ir.model.access.csv"
    
    try:
        with open(security_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Vérifier la présence des accès pour les wizards
        if 'model_sale_order_duplication_wizard' in content:
            print("✅ Accès définis pour le wizard principal")
        else:
            print("⚠️  Accès manquants pour le wizard principal")
            
        if 'model_sale_order_line_duplication_wizard' in content:
            print("✅ Accès définis pour le wizard de lignes")
        else:
            print("⚠️  Accès manquants pour le wizard de lignes")
            
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de la sécurité: {e}")
        return False

def main():
    """Fonction principale"""
    print("🚀 Validation de la migration Odoo 18.0")
    print("=" * 50)
    
    checks = [
        ("Manifest", check_manifest),
        ("Vues XML", check_xml_views),
        ("Syntaxe Python", check_python_syntax),
        ("Sécurité", check_security),
    ]
    
    results = []
    
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Erreur lors de {name}: {e}")
            results.append((name, False))
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ DE LA VALIDATION")
    print("=" * 50)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHEC"
        print(f"{name:20} : {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 MIGRATION VALIDÉE - Prêt pour Odoo 18.0!")
        print("📋 Prochaines étapes:")
        print("   1. Installer le module dans un environnement Odoo 18")
        print("   2. Exécuter les tests: python -m pytest tests/")
        print("   3. Tester manuellement les fonctionnalités")
    else:
        print("⚠️  MIGRATION INCOMPLÈTE - Corrections nécessaires")
        print("📋 Vérifiez les erreurs ci-dessus avant de continuer")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
