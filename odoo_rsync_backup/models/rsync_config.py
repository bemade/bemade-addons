import logging
import os
import subprocess

from odoo import models, fields, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class DbBackupConfigInherit(models.Model):
    """
    Extend db.backup.configure to add rsync functionality
    """
    _inherit = 'db.backup.configure'

    # Rsync configuration fields
    enable_rsync = fields.Boolean(
        string='RSync the filestore',
        help='Enable rsync backup for filestore when using dump format'
    )

    remote_host = fields.Char(string='Remote Host')
    remote_user = fields.Char(string='Remote User')
    remote_port = fields.Integer(string='SSH Port', default=22)
    ssh_key_path = fields.Char(
        string='SSH Key Path', 
        default='/home/odoo/.ssh/id_rsa',
        help='Path to the SSH private key file'
    )
    filestore_dest_path = fields.Char(
        string='Filestore Destination Path',
        help='Remote path where filestore will be backed up'
    )


    def _sync_filestore_with_rsync(self):
        """
        Synchronize filestore directory using rsync after backup is completed
        """
        if not (self.enable_rsync and self.backup_format == 'dump'):
            return

        try:
            # Get filestore path
            filestore_path = os.path.join(tools.config['data_dir'], 'filestore', self.env.cr.dbname)

            # Build rsync command
            filestore_cmd = [
                'rsync', '-avz', '-e',
                f'ssh -p {self.remote_port} -i {self.ssh_key_path}',
                filestore_path + '/',  # Add trailing slash to sync contents
                f'{self.remote_user}@{self.remote_host}:{self.filestore_dest_path}'
            ]

            # Execute rsync command
            subprocess.run(filestore_cmd, check=True)

            _logger.info('Rsync backup completed successfully')
            return True

        except subprocess.CalledProcessError as e:
            _logger.error('Rsync backup failed: %s', str(e))
            raise UserError(_('Rsync backup failed. Check the logs for details.'))
        except Exception as e:
            _logger.error('Unexpected error during rsync backup: %s', str(e))
            raise UserError(_('Unexpected error during rsync backup. Check the logs for details.'))

    def _schedule_auto_backup(self, frequency):
        """
        Override _schedule_auto_backup to add rsync synchronization after backup
        """
        res = super(DbBackupConfigInherit, self)._schedule_auto_backup(frequency)
        self._sync_filestore_with_rsync()
        return res

    name = fields.Char(
        string='Name', 
        required=True
    )

    remote_host = fields.Char(
        string='Remote Host', 
        required=True
    )

    remote_user = fields.Char(
        string='Remote User', 
        required=True
    )

    remote_port = fields.Integer(
        string='SSH Port', 
        default=22
    )

    ssh_key_path = fields.Char(
        string='SSH Key Path', 
        default='/home/odoo/.ssh/id_rsa',
        help='Path to the SSH private key file'
    )

    filestore_dest_path = fields.Char(
        string='Filestore Destination Path', 
        required=True,
        help='Remote path where filestore will be backed up'
    )

    config_dest_path = fields.Char(
        string='Config Destination Path', 
        required=True,
        help='Remote path where odoo.conf will be backed up'
    )

    active = fields.Boolean(
        default=True
    )

    last_backup = fields.Datetime(
        string='Last Backup', 
        readonly=True
    )

    def _run_rsync_command(self, source_path, dest_path):
        """
        Execute rsync command with specified parameters
        """
        try:
            cmd = [
                'rsync',
                '-avz',
                '-e', f'ssh -p {self.remote_port} -i {self.ssh_key_path}',
                source_path,
                f'{self.remote_user}@{self.remote_host}:{dest_path}'
            ]
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            _logger.info(f'Rsync successful: {process.stdout}')
            return True
        except subprocess.CalledProcessError as e:
            _logger.error(f'Rsync failed: {e.stderr}')
            return False

    def action_backup_now(self):
        """
        Manually trigger the backup process
        """
        self.ensure_one()
        self._perform_backup()
        return True

    def _perform_backup(self):
        """
        Perform the actual backup operation for filestore and config
        """
        success = True
        
        # Get filestore path from Odoo config
        filestore_path = os.path.join(
            self.env['ir.config_parameter'].get_param('data_dir'),
            'filestore',
            self.env.cr.dbname
        )

        # Get odoo.conf path
        odoo_conf_path = os.environ.get('ODOO_RC', '/etc/odoo/odoo.conf')

        # Backup filestore
        if os.path.exists(filestore_path):
            if not self._run_rsync_command(filestore_path + '/', self.filestore_dest_path):
                success = False

        # Backup odoo.conf
        if os.path.exists(odoo_conf_path):
            if not self._run_rsync_command(odoo_conf_path, self.config_dest_path):
                success = False

        if success:
            self.write({'last_backup': fields.Datetime.now()})

        return success
