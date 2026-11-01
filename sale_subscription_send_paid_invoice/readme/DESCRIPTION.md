Standard Odoo Subscriptions only emails a recurring invoice when the
subscription has **no** saved payment method. When a saved card (payment token)
pays the invoice, the customer receives a payment confirmation addressed to the
order's main contact, with no invoice attached, and the invoice itself is never
sent to the invoice address. Accounts-payable departments then never receive
the invoices they need for their books.

This module sends those invoices too. After a successful subscription payment,
whether the automatic charge made by the recurring invoicing cron or a payment
the customer makes on the portal, every posted invoice of that payment that has
not been sent yet is emailed with the subscription plan's invoice email
template, exactly as an unpaid recurring invoice would be. Because the payment
is already reconciled at that point, the email states that the invoice is paid.

Invoices already marked as sent (manually, or by an e-invoicing format) are not
sent again, and plans without an invoice email template keep the standard
behaviour.
