#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)

class PortalPartnerController(CustomerPortal):
    
    def _log_portal_activity(self, record, action, details, user_id=None):
        """
        Méthode utilitaire pour journaliser les activités du portail avec l'adresse IP
        
        :param record: Enregistrement sur lequel journaliser l'activité
        :param action: Type d'action (view, edit, create, etc.)
        :param details: Détails de l'action
        :param user_id: ID de l'utilisateur (par défaut, l'utilisateur connecté)
        :return: L'entrée de journal créée
        """
        if not user_id:
            user_id = request.env.user.id
            
        # Récupérer l'adresse IP
        ip = request.httprequest.remote_addr
        
        return record.sudo().log_portal_activity(
            user_id=user_id,
            action=action,
            details=details,
            ip=ip
        )

    def _prepare_portal_layout_values(self):
        """
        Add values to the portal layout
        """
        values = super(PortalPartnerController, self)._prepare_portal_layout_values()
        
        # Get the connected user's partner
        partner = request.env.user.partner_id
        
        # Add a variable to know if the user has a parent company
        values['has_company'] = bool(partner.parent_id)
        
        # Check if the partner has a parent company
        parent_company = partner.parent_id
        if parent_company and parent_company.is_company:
            values['parent_company'] = parent_company
            
            # Count the number of contacts
            contact_count = len(parent_company.get_portal_children())
            values['contact_count'] = contact_count
            
            Partner = request.env['res.partner']
            
        return values
    
    @http.route(['/my/company'], type='http', auth="user", website=True)
    def portal_my_company(self, **kw):
        """
        Display the parent company information
        """
        values = self._prepare_portal_layout_values()
        
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to edit the company
        can_edit = parent_company.allow_portal_parent_edit
        values['can_edit'] = can_edit
        
        # Get the company information
        values['company'] = parent_company
        
        # Get countries for the selection fields
        countries = request.env['res.country'].sudo().search([])
        # Get ALL states (will be filtered in the template by country)
        states = request.env['res.country.state'].sudo().search([])
        # Log country for debugging
        if parent_company.country_id:
            _logger.info("%s found: %r ", parent_company.country_id.name, parent_company.country_id)
            # Also log the provinces of that country
            provinces = states.filtered(lambda s: s.country_id == parent_company.country_id)
            _logger.info("Provinces found: %r", provinces)
        values.update({
            'countries': countries,
            'states': states,
        })
        
        # Get contacts for the kanban view (including archived ones)
        Contact = request.env['res.partner']
        base_domain = [('parent_id', '=', parent_company.id)]
        
        # Include archived contacts
        base_domain = expression.AND([base_domain, ['|', ('active', '=', True), ('active', '=', False)]])
        
        # Get contacts (type='contact')
        contact_domain = expression.AND([base_domain, [('type', '=', 'contact')]])
        contacts = Contact.search(contact_domain, order='name asc')
        
        # Get other addresses (type != 'contact')
        address_domain = expression.AND([base_domain, [('type', '!=', 'contact')]])
        addresses = Contact.search(address_domain, order='name asc')
        
        values.update({
            'contacts': contacts,
            'addresses': addresses,
        })
        
        # Journaliser l'accès à la société directement sur l'objet partenaire
        self._log_portal_activity(
            record=parent_company,
            action='view',
            details='User viewed company information via portal'
        )
        
        return request.render("portal_partner_manager.portal_my_company", values)
    
    @http.route(['/my/company/edit'], type='http', auth="user", website=True)
    def portal_my_company_edit(self, **kw):
        """
        Display the parent company edit form
        """
        values = self._prepare_portal_layout_values()
        
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to edit the company
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/company')
            
        # Get the company information
        values['company'] = parent_company
        
        # Get countries for the selection fields
        countries = request.env['res.country'].sudo().search([])
        # Get ALL states (will be filtered in the template by country)
        states = request.env['res.country.state'].sudo().search([])
        # Log country for debugging
        if parent_company.country_id:
            _logger.info("%s found: %r ", parent_company.country_id.name, parent_company.country_id)
            # Also log the provinces of that country
            provinces = states.filtered(lambda s: s.country_id == parent_company.country_id)
            _logger.info("Provinces found: %r", provinces)
        values.update({
            'countries': countries,
            'states': states,
        })
        
        return request.render("portal_partner_manager.portal_my_company_edit", values)
    
    @http.route(['/my/company/update'], type='http', auth="user", methods=['POST'], website=True)
    def portal_my_company_update(self, **kw):
        """
        Update the parent company information
        """
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to edit the company
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/company')
            
        # Prepare the values to update
        vals = {}
        allowed_fields = parent_company._get_portal_allowed_fields()
        
        for field in allowed_fields:
            if field in kw:
                # Special handling for many2one fields
                if field in ['state_id', 'country_id']:
                    if kw[field] and kw[field].isdigit():
                        vals[field] = int(kw[field])
                else:
                    vals[field] = kw[field]
        
        # Update the company
        try:
            parent_company.write(vals)
            
            # Journaliser la modification directement sur l'objet partenaire
            details = ', '.join([f"{field}: {vals[field]}" for field in vals])
            self._log_portal_activity(
                record=parent_company,
                action='edit',
                details=f"Company information updated: {', '.join([f'{field}: {vals[field]}' for field in vals])}"
            )
            
            return request.redirect('/my/company?update=success')
        except Exception as e:
            _logger.error("Error while updating company: %s", str(e))
            return request.redirect('/my/company/edit?error=1')
    
    @http.route(['/my/contacts', '/my/contacts/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_contacts(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """
        Display the list of contacts for the parent company
        """
        values = self._prepare_portal_layout_values()
        
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Get contacts (including archived ones)
        Contact = request.env['res.partner']
        domain = [('parent_id', '=', parent_company.id)]
        
        # Include archived contacts
        domain = expression.AND([domain, ['|', ('active', '=', True), ('active', '=', False)]])
        
        # Count the total number of contacts
        contact_count = Contact.search_count(domain)
        
        # Pagination
        pager = portal_pager(
            url="/my/contacts",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=contact_count,
            page=page,
            step=self._items_per_page
        )
        
        # Sorting
        if sortby == 'name':
            order = 'name asc'
        elif sortby == 'date':
            order = 'create_date desc'
        else:
            order = 'name asc'
        
        # Search contacts with pagination
        contacts = Contact.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager['offset']
        )
        
        values.update({
            'contacts': contacts,
            'page_name': 'contacts',
            'pager': pager,
            'default_url': '/my/contacts',
            'sortby': sortby,
            'can_add_contact': parent_company.allow_portal_parent_edit,
        })
        
        return request.render("portal_partner_manager.portal_my_contacts", values)
    
    @http.route(['/my/contacts/add'], type='http', auth="user", website=True)
    def portal_my_contacts_add(self, **kw):
        """
        Display the form to add a new contact
        """
        values = self._prepare_portal_layout_values()
        
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to add contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
            
        # Get countries for selection fields
        countries = request.env['res.country'].sudo().search([])
        
        # Get only Canadian provinces
        canada = request.env['res.country'].sudo().search([('code', '=', 'CA')], limit=1)
        _logger.info('Canada found: %s', canada)
        canadian_provinces = request.env['res.country.state'].sudo().search([('country_id', '=', canada.id)])
        _logger.info('Provinces found: %s', canadian_provinces)
        
        values.update({
            'countries': countries,
            'canadian_provinces': canadian_provinces,
            'company': parent_company,
        })
        
        return request.render("portal_partner_manager.portal_my_contacts_add", values)
    
    @http.route(['/my/contacts/create'], type='http', auth="user", methods=['POST'], website=True)
    def portal_my_contacts_create(self, **kw):
        """
        Create a new contact for the parent company
        """
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to add contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
            
        # Check if email is provided
        if not kw.get('email'):
            return request.redirect('/my/contacts/add?error=email_required')
            
        # Prepare values for creation
        vals = {}
        allowed_fields = parent_company._get_portal_allowed_fields()
        
        for field in allowed_fields:
            if field in kw:
                # Special handling for many2one fields
                if field in ['state_id', 'country_id']:
                    if kw[field] and kw[field].isdigit():
                        vals[field] = int(kw[field])
                else:
                    vals[field] = kw[field]
        
        # Handle contact type
        if 'type' in kw and kw.get('type') in ['contact', 'invoice', 'delivery', 'origin', 'other']:
            vals['type'] = kw.get('type')
        else:
            vals['type'] = 'contact'  # Default type
        
        # Validate email for contact type
        if vals.get('type') == 'contact' and not vals.get('email'):
            return request.redirect('/my/company?error_message=' + _('Email is required for Contact type'))
            
        # Create the contact
        try:
            new_contact = parent_company.create_portal_contact(parent_company.id, vals)
            
            # Journaliser l'ajout directement sur la société parente
            details = f"New contact: {new_contact.name} ({new_contact.email})"
            self._log_portal_activity(
                record=parent_company,
                action='create',
                details=details
            )
            
            # Journaliser également sur le nouveau contact
            self._log_portal_activity(
                record=new_contact,
                action='create',
                details=f"Contact created under {parent_company.name}"
            )
            
            return request.redirect('/my/company?create=success')
        except Exception as e:
            _logger.error("Error while creating contact: %s", str(e))
            return request.redirect('/my/contacts/add?error=1')
    
    @http.route(['/my/contacts/edit/<int:contact_id>'], type='http', auth="user", website=True)
    def portal_my_contacts_edit(self, contact_id, **kw):
        """
        Display the form to edit an existing contact
        """
        values = self._prepare_portal_layout_values()
        
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to edit contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
            
        # Get the contact to edit
        Contact = request.env['res.partner']
        contact = Contact.sudo().browse(contact_id)
        
        # Check that the contact belongs to the parent company
        if not contact.exists() or contact.parent_id.id != parent_company.id:
            return request.redirect('/my/contacts')
            
        # Get countries for selection fields
        countries = request.env['res.country'].sudo().search([])
        
        # Get only Canadian provinces
        canada = request.env['res.country'].sudo().search([('code', '=', 'CA')], limit=1)
        _logger.info('Canada found: %s', canada)
        canadian_provinces = request.env['res.country.state'].sudo().search([('country_id', '=', canada.id)])
        _logger.info('Provinces found: %s', canadian_provinces)
        
        values.update({
            'contact': contact,
            'countries': countries,
            'canadian_provinces': canadian_provinces,
            'company': parent_company,
        })
        
        return request.render("portal_partner_manager.portal_my_contacts_edit", values)
    
    # Helper method to check contact management rights
    def _check_contact_management_rights(self):
        """Check if the user has the right to manage contacts"""
        partner = request.env.user.partner_id
        parent_company = partner.commercial_partner_id
        
        if not parent_company.allow_portal_parent_edit:
            return False
        return parent_company
    
    @http.route(['/my/contacts/grant_access/<int:contact_id>'], type='http', auth="user", website=True)
    def portal_my_contacts_grant_access(self, contact_id=None, **kw):
        """Grant portal access to a contact"""
        if not contact_id:
            return request.redirect('/my/company')
            
        # Check management rights
        parent_company = self._check_contact_management_rights()
        if not parent_company:
            return request.redirect('/my/company?error_message=' + _('You do not have permission to manage contacts'))
            
        contact = request.env['res.partner'].sudo().browse(contact_id)
        if not contact.exists() or contact.parent_id != request.env.user.partner_id.commercial_partner_id:
            return request.redirect('/my/company')
            
        # Check if this is a contact (not an address)
        if contact.type != 'contact':
            return request.redirect('/my/company?error_message=' + _('Only contacts can be granted portal access'))
            
        # Check if user already has portal access
        if contact.user_ids:
            # Reset password instead
            try:
                contact.user_ids[0].action_reset_password()
                return request.redirect('/my/company?success_message=' + _('Password reset email sent'))
            except Exception as e:
                _logger.error("Error while resetting password: %s", str(e))
                return request.redirect('/my/company?error_message=' + _('Failed to reset password'))
        
        # Create portal user
        try:
            # Generate a random password
            password = self._generate_password()
            
            # Check if a user with this email already exists
            Users = request.env['res.users']
            existing_user = Users.sudo().search([('login', '=', contact.email)], limit=1)
            archived_user = Users.sudo().search([('login', '=', contact.email), ('active', '=', False)], limit=1)
            
            if existing_user and existing_user.active:
                # Active user with same login exists
                return request.redirect('/my/company?error_message=' + _('A user with this email already exists'))
            elif archived_user:
                # Reactivate the archived user and reassign it to this partner
                user = archived_user
                user.sudo().write({
                    'active': True,
                    'partner_id': contact.id,
                    'email': contact.email,
                    'name': contact.name,
                    'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])]
                })
            else:
                # Create a new portal user
                user_values = {
                    'partner_id': contact.id,
                    'login': contact.email,
                    'email': contact.email,
                    'name': contact.name,
                    'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])]
                }
                user = Users.sudo().create(user_values)
                
            # Journaliser l'action sur le contact
            details = f"Portal access granted to: {contact.name} ({contact.email})"
            self._log_portal_activity(
                record=contact,
                action='grant_access',
                details=details
            )
            
            # Journaliser également sur la société parente
            self._log_portal_activity(
                record=parent_company,
                action='grant_access',
                details=f"Granted portal access to contact: {contact.name}"
            )
            
            # Ajouter des détails supplémentaires dans le log du contact pour inclure l'information sur l'utilisateur
            self._log_portal_activity(
                record=contact,
                action='create_user',
                details=f"Portal user {user.login} created/updated for this contact"
            )
            
            # For new users, send an invitation email
            # For reactivated users, redirect to set password page
            is_new_user = not archived_user
            
            if is_new_user:
                # Send invitation email for new users
                try:
                    user.sudo().with_context(create_user=True).action_reset_password()
                    return request.redirect('/my/contacts?success=invitation_sent')
                except Exception as e:
                    _logger.error("Error sending invitation email: %s", str(e))
                    return request.redirect('/my/contacts?error=invitation_failed')
            else:
                # Redirect to set password page for reactivated users
                return request.redirect(f'/my/contacts/set_password_form/{contact_id}')
        except Exception as e:
            _logger.error("Error while granting portal access: %s", str(e))
            return request.redirect('/my/contacts?error=grant_access')
    
    @http.route(['/my/contacts/set_password_form/<int:contact_id>'], type='http', auth="user", website=True)
    def portal_my_contacts_set_password_form(self, contact_id, **kw):
        """
        Display the form to set a password for a contact's portal user
        """
        values = self._prepare_portal_layout_values()
        
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to manage contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
            
        # Get the contact
        Contact = request.env['res.partner']
        contact = Contact.sudo().browse(contact_id)
        
        # Check that the contact belongs to the parent company
        if not contact.exists() or contact.parent_id.id != parent_company.id:
            return request.redirect('/my/contacts')
        
        # Check if the contact has a user
        if not contact.user_ids:
            return request.redirect('/my/contacts?error=no_user')
        
        values.update({
            'contact': contact,
            'company': parent_company,
        })
        
        return request.render("portal_partner_manager.portal_set_password", values)
    
    @http.route(['/my/contacts/set_password'], type='http', auth="user", methods=['POST'], website=True)
    def portal_my_contacts_set_password(self, **kw):
        """
        Set a password for a contact's portal user
        """
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to manage contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
        
        # Get the contact ID from the form
        contact_id = int(kw.get('contact_id', 0))
        if not contact_id:
            return request.redirect('/my/contacts')
        
        # Get the contact
        Contact = request.env['res.partner']
        contact = Contact.sudo().browse(contact_id)
        
        # Check that the contact belongs to the parent company
        if not contact.exists() or contact.parent_id.id != parent_company.id:
            return request.redirect('/my/contacts')
        
        # Check if the contact has a user
        if not contact.user_ids:
            return request.redirect('/my/contacts?error=no_user')
        
        # Get the passwords from the form
        password = kw.get('password')
        confirm_password = kw.get('confirm_password')
        
        # Validate the passwords
        if not password or len(password) < 8:
            return request.redirect(f'/my/contacts/set_password_form/{contact_id}?error=password_too_short')
        
        if password != confirm_password:
            return request.redirect(f'/my/contacts/set_password_form/{contact_id}?error=password_mismatch')
        
        try:
            # Set the password
            user = contact.user_ids[0]
            user.sudo().write({'password': password})
            
            # Journaliser l'action sur le contact
            self._log_portal_activity(
                record=contact,
                action='edit',
                details=f"Password set for associated user account"
            )
            
            return request.redirect('/my/contacts?password_set=success')
        except Exception as e:
            _logger.error("Error while setting password: %s", str(e))
            return request.redirect(f'/my/contacts/set_password_form/{contact_id}?error=general')
    
    @http.route(['/my/contacts/change_status/<int:contact_id>'], type='http', auth="user", website=True)
    def portal_my_contacts_change_status(self, contact_id, status=None, **kw):
        """
        Change the status of a contact (Portal Access, No Access, Archived)
        
        :param contact_id: ID of the contact to change status
        :param status: New status (portal, no_access, archived)
        """
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to manage contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
            
        # Get the contact
        Contact = request.env['res.partner']
        contact = Contact.sudo().browse(contact_id)
        
        # Check that the contact belongs to the parent company
        if not contact.exists() or contact.parent_id.id != parent_company.id:
            return request.redirect('/my/contacts')
        
        # Validate the requested status
        if status not in ['portal', 'no_access', 'archived']:
            return request.redirect('/my/contacts')
        
        try:
            # Handle the status change based on the requested status
            # Initialize variables for action details and redirect parameters
            action_details = ""
            redirect_params = ""
            
            if status == 'portal':
                # Grant portal access if not already granted
                if not contact.user_ids:
                    # Check if email is available
                    if not contact.email:
                        return request.redirect('/my/contacts?error=email_required')
                    
                    # Check if a user with this email already exists
                    Users = request.env['res.users']
                    existing_user = Users.sudo().search([('login', '=', contact.email)], limit=1)
                    if existing_user:
                        return request.redirect('/my/contacts?error=user_exists')
                    
                    # Create the portal user
                    user_values = {
                        'partner_id': contact.id,
                        'login': contact.email,
                        'email': contact.email,
                        'name': contact.name,
                        'groups_id': [(6, 0, [request.env.ref('base.group_portal').id])]
                    }
                    user = Users.sudo().create(user_values)
                    
                    # Always send an invitation email for new portal users
                    try:
                        user.sudo().with_context(create_user=True).action_reset_password()
                        redirect_params = "status_change=portal_granted&invitation_sent=true"
                    except Exception as e:
                        _logger.error("Error sending invitation email: %s", str(e))
                        redirect_params = "status_change=portal_granted&invitation_failed=true"
                
                # Ensure the contact is active
                if not contact.active:
                    contact.sudo().write({'active': True})
                
                # Log the action
                action_details = "Portal access granted"
                if not redirect_params:
                    redirect_params = "status_change=portal_granted"
            
            elif status == 'no_access':
                # Remove portal access if granted
                if contact.user_ids:
                    # Only handle portal users, not internal users
                    portal_users = contact.sudo().user_ids.filtered(
                        lambda u: u.has_group('base.group_portal') and not u.has_group('base.group_user'))
                    if portal_users:
                        # Deactivate the users instead of deleting them to preserve history
                        portal_users.sudo().write({'active': False})
                
                # Ensure the contact is active
                if not contact.active:
                    contact.sudo().write({'active': True})
                
                # Log the action
                action_details = "Portal access removed"
                redirect_params = "status_change=access_removed"
            
            elif status == 'archived':
                # Check if the contact has active users
                if contact.user_ids:
                    active_users = contact.sudo().user_ids.filtered(lambda u: u.active)
                    if active_users:
                        # Deactivate the users
                        portal_users = active_users.filtered(
                            lambda u: u.has_group('base.group_portal') and not u.has_group('base.group_user'))
                        if portal_users:
                            portal_users.sudo().write({'active': False})
                
                # Archive the contact
                contact.sudo().write({'active': False})
                
                # Log the action
                action_details = "Contact archived"
                redirect_params = "status_change=archived"
            
            # Journaliser l'action sur le contact
            details = f"{action_details}: {contact.name} ({contact.email})"
            self._log_portal_activity(
                record=contact,
                action=status,
                details=details
            )
            
            # Journaliser également sur la société parente
            self._log_portal_activity(
                record=parent_company,
                action=status,
                details=f"Contact status changed: {contact.name} to {status}"
            )
            
            # Si le statut est 'archived', vérifier et journaliser la désactivation des utilisateurs du portail
            if status == 'archived':
                # Rechercher directement les utilisateurs du portail qui ont été affectés
                # sans dépendre de la variable portal_users définie ailleurs
                affected_users = contact.sudo().user_ids.filtered(
                    lambda u: not u.active and u.has_group('base.group_portal') and not u.has_group('base.group_user')
                )
                
                # Journaliser pour chaque utilisateur affecté
                for affected_user in affected_users:
                    contact.sudo().log_portal_activity(
                        user_id=request.env.user.id,
                        action='archive',
                        details=f"User {affected_user.name} deactivated due to contact archival"
                    )
            
            return request.redirect(f'/my/contacts?{redirect_params}')
        
        except Exception as e:
            _logger.error("Error while changing contact status: %s", str(e))
            return request.redirect('/my/contacts?error=status_change')
    
    @http.route(['/my/contacts/archive/<int:contact_id>'], type='http', auth="user", website=True)
    def portal_my_contacts_archive(self, contact_id, archive_user=None, **kw):
        """
        Archive or unarchive a contact (Legacy route, redirects to change_status)
        """
        # Redirect to the new change_status route
        if archive_user == '1':
            return request.redirect(f'/my/contacts/change_status/{contact_id}?status=archived')
        else:
            # Check the current status to determine the redirect
            Contact = request.env['res.partner']
            contact = Contact.sudo().browse(contact_id)
            
            if contact.exists():
                if contact.active:
                    return request.redirect(f'/my/contacts/change_status/{contact_id}?status=archived')
                else:
                    return request.redirect(f'/my/contacts/change_status/{contact_id}?status=no_access')
            
            return request.redirect('/my/contacts')
    
    @http.route(['/my/contacts/update'], type='http', auth="user", methods=['POST'], website=True)
    def portal_my_contacts_update(self, **kw):
        """
        Update an existing contact
        """
        # Check if the user has a parent company
        partner = request.env.user.partner_id
        parent_company = partner.parent_id
        
        if not parent_company or not parent_company.is_company:
            return request.redirect('/my')
            
        # Check if the user has the right to edit contacts
        if not parent_company.allow_portal_parent_edit:
            return request.redirect('/my/contacts')
            
        # Get the ID of the contact to update
        contact_id = kw.get('contact_id')
        if not contact_id or not contact_id.isdigit():
            return request.redirect('/my/contacts')
            
        contact_id = int(contact_id)
        Contact = request.env['res.partner']
        contact = Contact.sudo().browse(contact_id)
        
        # Check that the contact belongs to the parent company
        if not contact.exists() or contact.parent_id.id != parent_company.id:
            return request.redirect('/my/contacts')
            
        # Prepare the values to update
        vals = {}
        allowed_fields = parent_company._get_portal_allowed_fields()
        
        for field in allowed_fields:
            if field in kw:
                # Special handling for many2one fields
                if field in ['state_id', 'country_id']:
                    if kw[field] and kw[field].isdigit():
                        vals[field] = int(kw[field])
                else:
                    vals[field] = kw[field]
        
        # Handle contact type
        if 'type' in kw and kw.get('type') in ['contact', 'invoice', 'delivery', 'origin', 'other']:
            vals['type'] = kw.get('type')
        else:
            vals['type'] = 'contact'  # Default type
        
        # Check if email is being updated
        old_email = contact.email
        email_changed = 'email' in vals and vals['email'] != old_email
        
        # Validate email for contact type
        if vals.get('type') == 'contact' and not vals.get('email'):
            return request.redirect('/my/company?error_message=' + _('Email is required for Contact type'))
            
        # Update the contact
        try:
            contact.write(vals)
            
            # If email changed and contact has a portal user, update the login
            if email_changed and contact.user_ids:
                for user in contact.sudo().user_ids:
                    # Only update users in the portal group (not internal users)
                    if user.has_group('base.group_portal') and not user.has_group('base.group_user'):
                        user.sudo().write({'login': vals['email']})
                        _logger.info(f"Updated login for user {user.id} from {old_email} to {vals['email']}")
            
            # Journaliser la modification directement sur le contact
            details = ', '.join([f"{field}: {vals[field]}" for field in vals])
            contact.sudo().log_portal_activity(
                user_id=request.env.user.id,
                action='edit',
                details=f"Contact updated via portal: {details}"
            )
            
            # Si l'email a changé et qu'un utilisateur a été mis à jour, journaliser l'action pour les utilisateurs affectés
            if email_changed and contact.user_ids:
                # Récupérer tous les utilisateurs du portail associés à ce contact
                portal_users = contact.sudo().user_ids.filtered(
                    lambda u: u.has_group('base.group_portal') and not u.has_group('base.group_user')
                )
                # Pour chaque utilisateur affecté, créer une entrée de log sur le contact
                for portal_user in portal_users:
                    contact.sudo().log_portal_activity(
                        user_id=request.env.user.id,
                        action='edit_user',
                        details=f"Portal user login updated from {old_email} to {vals['email']} for user {portal_user.name}"
                    )
            
            return request.redirect('/my/company?update=success')
        except Exception as e:
            _logger.error("Error while updating contact: %s", str(e))
            return request.redirect(f'/my/contacts/edit/{contact_id}?error=1')
    

    
    def _generate_password(self, length=12):
        """Generate a random password"""
        import random
        import string
        chars = string.ascii_letters + string.digits + '!@#$%^&*()'  
        return ''.join(random.choice(chars) for _ in range(length))
