# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.portal.models.portal_mixin import PortalMixin


class VendorRequest(models.Model):
    _name = 'vendor.request'
    _description = 'Request to become a vendor'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin', 'website.published.mixin']
    
    # Temporary solution to add is_frontend_multilang attribute
    is_frontend_multilang = fields.Boolean(default=False)
    _order = 'create_date desc'

    name = fields.Char(
        string="Reference", 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: _('New Request')
    )
    partner_id = fields.Many2one(
        'res.partner', 
        string="Contact", 
        required=True, 
        readonly=True,
        default=lambda self: self.env.user.partner_id,
        index=True
    )
    user_id = fields.Many2one(
        'res.users', 
        string="User", 
        compute='_compute_user_id',
        store=True,
        readonly=True
    )
    
    @api.depends('partner_id')
    def _compute_user_id(self):
        for request in self:
            # Find the user associated with this partner (if exists)
            user = self.env['res.users'].search([('partner_id', '=', request.partner_id.id)], limit=1)
            request.user_id = user.id if user else False
    
    # Company information
    company_name = fields.Char(
        string="Company Name", 
        required=True
    )
    company_street = fields.Char(string="Street")
    company_street2 = fields.Char(string="Address Complement")
    company_zip = fields.Char(string="Zip Code")
    company_city = fields.Char(string="City")
    company_state_id = fields.Many2one('res.country.state', string="State/Province")
    company_country_id = fields.Many2one(
        'res.country',
        string="Country",
        default=lambda self: self.env.ref('base.ca').id if self.env.ref('base.ca', False) else False
    )  # Canada by default but modifiable if other countries are proposed
    company_email = fields.Char(string="Company Email")
    company_phone = fields.Char(string="Company Phone")
    company_website = fields.Char(string="Company Website")
    company_vat = fields.Char(string="VAT/Tax ID")
    
    # Additional information
    description = fields.Text(
        string="Description", 
        help="Describe your company and the products you want to sell"
    )
    company_partner_id = fields.Many2one(
        'res.partner',
        string="Created Company",
        readonly=True,
        help="Company created when the request is approved"
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string="Status", default='draft', tracking=True)
    rejection_reason = fields.Text(
        string="Rejection Reason", 
        tracking=True
    )
    approved_date = fields.Datetime(
        string="Approval Date", 
        readonly=True
    )
    
    # Additional documents (attachments)
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        'vendor_request_attachment_rel', 
        'request_id', 
        'attachment_id', 
        string="Documents"
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Prevents creating vendor requests from the backend (outside the portal) and automatically submits the request upon creation."""
        # If the user is not in portal mode, block
        if not self.env.context.get('from_portal') and not self.env.user.has_group('base.group_portal'):
            raise UserError(_('Creating vendor requests is only allowed from the customer portal.'))
        for vals in vals_list:
            if vals.get('name', _('New Request')) == _('New Request'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vendor.request') or _('New Request')
            # All new requests are directly pending
            vals['state'] = 'pending'
        requests = super(VendorRequest, self).create(vals_list)
        # For each created request, trigger the notification logic
        for request in requests:
            # Notify administrators
            admin_group = request.env.ref('base.group_system')
            admin_partners = admin_group.users.mapped('partner_id')
            if admin_partners:
                request.message_subscribe(partner_ids=admin_partners.ids)
                request.message_post(
                    body=_("A new request to become a vendor has been submitted by %s") % request.user_id.name,
                    partner_ids=admin_partners.ids,
                    subtype_xmlid='mail.mt_note'
                )
            # Send an acknowledgement to the user
            template = request.env.ref('st_laurent_portal_vendor.mail_template_vendor_request_ack', raise_if_not_found=False)
            if template:
                template.send_mail(request.id, force_send=True)
        return requests
    
    def action_approve(self):
        """
        Approves the request, sets the user as a vendor, and creates the company.
        Automatically adds the user to the St-Laurent vendor group, creates the user if necessary,
        logs the reviewer, and sends an enriched notification.
        """
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("Only pending requests can be approved."))
        
        # If the partner already has a parent, use this parent as the company
        existing_parent = self.partner_id.parent_id if self.partner_id.parent_id and self.partner_id.parent_id != self.partner_id else None
        if existing_parent:
            company_partner = existing_parent
            # Optional: update the existing company's information with the request data
            company_partner.write({
                'name': self.company_name,
                'street': self.company_street,
                'street2': self.company_street2,
                'zip': self.company_zip,
                'city': self.company_city,
                'state_id': self.company_state_id.id if self.company_state_id else False,
                'country_id': self.company_country_id.id if self.company_country_id else False,
                'email': self.company_email,
                'phone': self.company_phone,
                'website': self.company_website,
                'vat': self.company_vat,
                'vendor_status': 'yes',
                'is_company': True,
            })
        else:
            # Create the company (partner of type company)
            company_partner = self.env['res.partner'].create({
                'name': self.company_name,
                'company_type': 'company',
                'street': self.company_street,
                'street2': self.company_street2,
                'zip': self.company_zip,
                'city': self.company_city,
                'state_id': self.company_state_id.id if self.company_state_id else False,
                'country_id': self.company_country_id.id if self.company_country_id else False,
                'email': self.company_email,
                'phone': self.company_phone,
                'website': self.company_website,
                'vat': self.company_vat,
                'vendor_status': 'yes',
                'is_company': True,
            })
            # Associate the user's partner with the company
            self.partner_id.write({
                'parent_id': company_partner.id,
            })
        # Update the request
        self.write({
            'state': 'approved',
            'approved_date': fields.Datetime.now(),
            'company_partner_id': company_partner.id,
        })
        
        # Automatically create the shop upon approval
        VendorShop = self.env['vendor.shop'].sudo()
        VendorShop.create_shop_for_vendor(company_partner)
        
        # Automatically add the user to the vendor group
        user = self.user_id
        if not user:
            # Create the user if non-existent
            user = self.env['res.users'].sudo().create({
                'login': self.partner_id.email,
                'name': self.partner_id.name,
                'partner_id': self.partner_id.id,
                'email': self.partner_id.email,
            })
            self.user_id = user.id
        seller_group = self.env.ref('st_laurent_portal_vendor.group_seller', raise_if_not_found=False)
        if seller_group and user and user not in seller_group.users:
            seller_group.sudo().write({'users': [(4, user.id)]})
        
        # Notify the user
        self.message_post(
            body=_("Your request to become a vendor has been approved. Your company %s was created by %s.") % (self.company_name, self.env.user.display_name),
            partner_ids=[self.partner_id.id],
            subtype_xmlid='mail.mt_note'
        )
        # Traceability: log the action in the chatter
        self.message_post(
            body=_("Request approved by %s.") % self.env.user.display_name,
            subtype_xmlid='mail.mt_note'
        )
        # Custom email notification (example)
        template = self.env.ref('st_laurent_portal_vendor.mail_template_vendor_request_approved', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        
        return True
    
    def action_reject(self):
        """
        Rejects the request, logs the reviewer, and sends an enriched notification.
        """
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("Only pending requests can be rejected."))
        # Traceability: log the action in the chatter
        self.message_post(
            body=_("Request rejected by %s.") % self.env.user.display_name,
            subtype_xmlid='mail.mt_note'
        )
        # Custom email notification (rejection)
        template = self.env.ref('st_laurent_portal_vendor.mail_template_vendor_request_rejected', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        # Open a wizard to enter the rejection reason
        return {
            'name': _('Rejection Reason'),
            'type': 'ir.actions.act_window',
            'res_model': 'vendor.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id}
        }
    
    def action_reset_to_draft(self):
        """Resets the request to draft state."""
        self.ensure_one()
        if self.state in ['approved', 'rejected']:
            self.state = 'draft'
        return True
