from odoo import models, api, fields, _
from odoo.exceptions import UserError

class ProjectTask(models.Model):
    _inherit = 'project.task'

    can_be_nuked = fields.Boolean(
        compute='_compute_can_be_nuked',
        help="Technical field to determine if task can be nuked"
    )

    @api.depends('parent_id', 'child_ids')
    def _compute_can_be_nuked(self):
        """Compute if the task can be nuked based on parent and children presence"""
        for task in self:
            task.can_be_nuked = bool(task.parent_id and task.child_ids)

    def action_nuke_task(self):
        """
        Nuke the current task:
        1. Verify the task can be nuked
        2. Get parent and children
        3. Reassign all children to the parent
        4. Update children names to include nuked task name
        5. Post messages in the chatter
        6. Delete the current task
        7. Return action to redirect to parent task
        """
        self.ensure_one()
        if not self.can_be_nuked:
            raise UserError(_("This task cannot be nuked. It must have both a parent and child tasks."))

        parent = self.parent_id
        children = self.child_ids
        nuked_name = self.name

        # Post message to parent about the upcoming changes
        parent.message_post(
            body=_(
                "The following task has been nuked: %(task)s\n"
                "%(count)d child tasks have been reassigned to this task."
            ) % {
                'task': nuked_name,
                'count': len(children)
            }
        )

        # Reassign all children to the parent, update their names and notify them
        for child in children:
            old_name = child.name
            # Update name to include nuked task's name
            child.write({
                'name': f"[{nuked_name}] {old_name}",
                'parent_id': parent.id
            })
            child.message_post(
                body=_("This task has been reassigned to %(new_parent)s due to the removal of %(old_parent)s.\nTask name updated from '%(old_name)s' to '%(new_name)s'") % {
                    'new_parent': parent.name,
                    'old_parent': nuked_name,
                    'old_name': old_name,
                    'new_name': child.name
                }
            )

        # Delete the current task
        self.unlink()

        # Return action to redirect to parent task
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': parent.id,
            'view_mode': 'form',
            'target': 'current',
        }
