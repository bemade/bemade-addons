import os
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class ModuleExtension(models.Model):
    _inherit = 'ir.module.module'

    state = fields.Selection(
        selection_add=[
            ('linkable', 'Linkable'),
            ('linked', 'Linked'),
        ],
        ondelete={
            'linkable': 'set default',
            'linked': 'cascade',
        },
    )

    @staticmethod
    def _get_base_paths():
        """Obtenir les chemins de base pour les dépôts et les addons"""
        cwd = os.getcwd()
        repos_path = os.path.join(cwd, '.repos')
        addons_path = os.path.join(cwd, 'addons')
        return repos_path, addons_path

    @api.model
    def scan_modules(self):
        """Scanner les dépôts dans .repos et mettre à jour les statuts des modules."""
        repos_path, addons_path = self._get_base_paths()

        if not os.path.exists(repos_path):
            _logger.error(f"Le répertoire {repos_path} n'existe pas.")
            return

        existing_modules = self.search([]).mapped('name')
        for repo in os.listdir(repos_path):
            repo_path = os.path.join(repos_path, repo)
            if os.path.isdir(repo_path):
                for module in os.listdir(repo_path):
                    module_path = os.path.join(repo_path, module)
                    if os.path.isdir(module_path):
                        module_record = self.search([('name', '=', module)], limit=1)
                        if module_record:
                            if module_record.state == 'uninstalled':
                                module_record.write({'state': 'linkable'})
                        else:
                            self.create({
                                'name': module,
                                'state': 'linkable',
                                'repo_path': module_path,
                            })

    def toggle_link(self):
        """Créer ou supprimer le lien symbolique pour un module."""
        repos_path, addons_path = self._get_base_paths()

        for module in self:
            symlink_path = os.path.join(addons_path, module.name)
            if module.state == 'linkable':
                # Créer un lien symbolique et marquer comme 'linked'
                if os.path.exists(module.repo_path):
                    os.symlink(module.repo_path, symlink_path)
                    module.write({'state': 'linked'})
                    _logger.info(f"Lien symbolique créé pour le module {module.name}.")
                else:
                    _logger.error(f"Le chemin {module.repo_path} n'existe pas.")
            elif module.state == 'linked':
                # Supprimer le lien symbolique et repasser en 'linkable'
                if os.path.islink(symlink_path):
                    os.unlink(symlink_path)
                    module.write({'state': 'linkable'})
                    _logger.info(f"Lien symbolique supprimé pour le module {module.name}.")