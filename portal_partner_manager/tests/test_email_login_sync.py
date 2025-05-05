from odoo.tests.common import SavepointCase

class TestEmailLoginSync(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super(TestEmailLoginSync, cls).setUpClass()
        
        # Create a parent company
        cls.parent_company = cls.env['res.partner'].create({
            'name': 'Test Company',
            'is_company': True,
            'allow_portal_parent_edit': True,
        })
        
        # Create a contact
        cls.contact = cls.env['res.partner'].create({
            'name': 'Test Contact',
            'email': 'test@example.com',
            'parent_id': cls.parent_company.id,
        })
        
        # Create a portal user for the contact
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Test Portal User',
            'login': 'test@example.com',
            'email': 'test@example.com',
            'partner_id': cls.contact.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
    
    def test_email_login_sync(self):
        """Test that changing a contact's email also updates their login"""
        # Change the contact's email
        new_email = 'updated@example.com'
        self.contact.write({'email': new_email})
        
        # Check that the user's login was updated
        self.assertEqual(self.portal_user.login, new_email, 
                         "User login should be updated when contact email changes")
        self.assertEqual(self.portal_user.email, new_email, 
                         "User email should match contact email")
