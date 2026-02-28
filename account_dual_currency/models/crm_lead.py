from odoo import api, fields, models, _


class Lead(models.Model):
    _inherit = "crm.lead"

    @api.depends('company_id')
    def _compute_company_currency(self):
        for lead in self:
            if not lead.company_id:
                lead.company_currency = self.env.company.currency_id_dif
            else:
                lead.company_currency = lead.company_id.currency_id_dif