# coding: utf-8
from odoo import fields, models, api


class AccountWhMunicipalDocs(models.Model):
    _name = 'account.wh.municipal.docs'
    _description = 'Documentos de retención municipal'

    name = fields.Char('Número de Retención', required=True)

    partner_id = fields.Many2one('res.partner', string='Proveedor', required=True)
    date = fields.Date('Fecha', required=True)
    amount_total = fields.Monetary('Total retenido', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Realizado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', default='draft', required=True)

    type = fields.Selection([
        ('in_invoice', 'Facturas de Proveedor'),
        ('out_invoice', 'Facturas de Cliente'),
    ], string='Tipo', required=True)

    @api.depends('name', 'partner_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} - {rec.partner_id.name}"

    