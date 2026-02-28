# -*- coding: utf-8 -*-
from odoo import fields, models, tools
import datetime

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    currency_id_dif = fields.Many2one("res.currency",
                                     string="Divisa de Referencia",
                                     default=lambda self: self.env.company.currency_id_dif )
    unit_cost_usd = fields.Monetary('Valor unitario $', readonly=True, default=0,currency_field='currency_id_dif')
    value_usd = fields.Monetary('Valor Total $', readonly=True, default=0,currency_field='currency_id_dif')

    remaining_value_usd = fields.Monetary('Valor Restante $', readonly=True, default=0,currency_field='currency_id_dif')

    tasa = fields.Float('Tasa de Referencia', readonly=True, force_save=True, digits='Dual_Currency_rate')

    def write(self, vals):
        #print('entra en write', vals)
        company = self.company_id
        if not 'unit_cost_usd' in vals and not 'value_usd' in vals:
            if not 'quantity' in vals and self.stock_move_id:
                new_rate = company.currency_id_dif.rate
                for rec in self:
                    if rec.stock_move_id:
                        picking_id = rec.stock_move_id.picking_id
                        date = datetime.date.today()
                        if picking_id:
                            date = picking_id.date_of_transfer or picking_id.create_date
                        new_rate_ids = company.currency_id_dif._get_rates(company, date)
                        if new_rate_ids:
                            new_rate = 1 / new_rate_ids[company.currency_id_dif.id]
                if 'unit_cost' in vals:

                    standard_price_usd = float(vals['unit_cost']) / new_rate
                    vals['unit_cost_usd'] = standard_price_usd
                    if vals.get('stock_move_id') or self.stock_move_id:
                        stock_move_id = self.env['stock.move'].search(
                            [('id', '=', vals.get('stock_move_id') or self.stock_move_id.id)])
                        if stock_move_id.location_id.usage == 'supplier':
                            self.product_id.with_company(company.id).standard_price_usd = standard_price_usd
                if 'value' in vals:
                    value_usd = float(vals['value']) / new_rate
                    vals['value_usd'] = value_usd
        if 'account_move_id' in vals:
            new_rate = company.currency_id_dif.rate
            product_id = self.product_id
            for rec in self:
                if rec.stock_move_id:
                        picking_id = rec.stock_move_id.picking_id
                        date = datetime.date.today()
                        if picking_id:
                            date = picking_id.date_of_transfer or picking_id.create_date
                        new_rate_ids = company.currency_id_dif._get_rates(company,date)
                        if new_rate_ids:
                            new_rate = 1 / new_rate_ids[company.currency_id_dif.id]
                move_id = self.env['account.move'].sudo().with_context(check_move_validity=False).search(
                    [('id', '=', vals['account_move_id'])])
                print('entra en el asiento contable', move_id)
                if move_id:
                    #move_id.button_draft()
                    if move_id.line_ids[0].currency_id != self.currency_id:
                        for l in move_id.line_ids:
                            l.currency_id = self.currency_id
                            if l.amount_currency < 0:
                                l.amount_currency = self.value * -1
                            else:
                                l.amount_currency = self.value


                    if rec.stock_move_id.location_id.usage == 'supplier':
                        move_id.tax_today = new_rate
                    else:
                        move_id.tax_today = rec.tasa

                    for l in move_id.line_ids:
                        if l.credit_usd > 0:
                            l.credit_usd = self.value_usd
                        if l.debit_usd > 0:
                            l.debit_usd = self.value_usd

                    # if move_id.state == 'draft':
                    #     move_id._post()

        return super(StockValuationLayer, self).write(vals)

    def create(self, vals):
        print('creando valores de inventario', vals)
        if isinstance(vals, list):
            for val in vals:
                company = self.env['res.company'].browse(val.get('company_id') or self.env.company.id)
                if not 'unit_cost_usd' in val and not 'value_usd' in val:
                    if val.get('quantity'):
                        if float(val['quantity']) != 0:
                            supplier = False
                            product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                            standard_price_usd = 0
                            new_rate = company.currency_id_dif.rate
                            if 'stock_move_id' in val:
                                stock_move_id = self.env['stock.move'].search([('id', '=', val['stock_move_id'])])
                                if stock_move_id:
                                    picking_id = stock_move_id.picking_id
                                    date = datetime.date.today()
                                    if picking_id:
                                        date = picking_id.date_of_transfer or picking_id.create_date
                                    new_rate_ids = company.currency_id_dif._get_rates(company,date)
                                    if new_rate_ids:
                                        new_rate = 1 / new_rate_ids[company.currency_id_dif.id]
                                if stock_move_id.location_id.usage in ['supplier','production']:
                                    supplier = True
                                else:
                                    if 'tasa' in val:
                                        new_rate = val['tasa']

                            if 'stock_move_id' in val:
                                standard_price_usd = float(val['unit_cost']) / new_rate
                            else:
                                standard_price_usd = product_id.with_company(company.id).standard_price_usd
                            val['unit_cost_usd'] = standard_price_usd
                            val['value_usd'] = float(val['quantity']) * standard_price_usd
                            val['tasa'] = new_rate
                            if product_id.with_company(company.id).cost_method in ('average', 'fifo') and supplier:
                                val['remaining_value_usd'] = float(val['quantity']) * standard_price_usd
                            # if 'stock_move_id' in val:#HELP
                            #     stock_move_id = self.env['stock.move'].search([('id', '=', val.get('stock_move_id'))])
                            #     if stock_move_id.location_id.usage in ['supplier','production']:
                            #         product_id.with_company(company.id).standard_price_usd = standard_price_usd
                                    #product_id.standard_price = standard_price_usd * new_rate
                            #fifo
                            if product_id.with_company(company.id).cost_method in ('fifo'):
                                candidates = self.env['stock.valuation.layer'].sudo().search([
                                    ('product_id', '=', product_id.id),
                                    ('remaining_qty', '>', 0),
                                    ('company_id', '=', company.id),
                                ])
                                if candidates:
                                    next_candidates = candidates.filtered(lambda svl: svl.remaining_qty > 0)
                                    new_standard_price = next_candidates and next_candidates[0].unit_cost
                                    new_standard_price_usd = next_candidates and next_candidates[0].unit_cost_usd
                                    product_id.with_company(company.id).standard_price = new_standard_price
                                    product_id.with_company(company.id).standard_price_usd = new_standard_price_usd
                                else:
                                    product_id.with_company(company.id).standard_price = val['unit_cost']
                                    product_id.with_company(company.id).standard_price_usd = standard_price_usd
                            #promedio
                            if product_id.with_company(company.id).cost_method in ('average'):
                                if 'stock_move_id' in val:#HELP
                                    stock_move_id = self.env['stock.move'].search([('id', '=', val.get('stock_move_id'))])
                                    if stock_move_id.location_id.usage in ['supplier','production']:
                                        product_id.with_company(company.id).standard_price_usd = standard_price_usd
                                        product_id.standard_price = standard_price_usd * new_rate

                        else:
                            product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                            val['value_usd'] = product_id.qty_available * product_id.with_company(company.id).standard_price_usd
                else:
                    product_id = self.env['product.product'].search([('id', '=', val['product_id'])])
                    if val.get('stock_move_id'):
                        stock_move_id = self.env['stock.move'].search([('id', '=', val.get('stock_move_id'))])
                        if stock_move_id.location_id.usage in ['supplier','production']:
                            if product_id.with_company(company.id).cost_method == 'average':
                                if product_id.with_company(company.id).standard_price_usd == 0:
                                    product_id.with_company(company.id).standard_price_usd = val['unit_cost_usd']
        else:
            company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
            if not 'unit_cost_usd' in vals and not 'value_usd' in vals:
                if 'quantity' in vals:
                    if float(vals['quantity']) != 0:
                        supplier = False
                        product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                        standard_price_usd = 0
                        # tasa = self.env.company.currency_id_dif
                        new_rate = company.currency_id_dif.rate
                        if 'stock_move_id' in vals:
                            stock_move_id = self.env['stock.move'].search([('id', '=', vals['stock_move_id'])])
                            if stock_move_id:
                                picking_id = stock_move_id.picking_id
                                date = datetime.date.today()
                                if picking_id:
                                    date = picking_id.date_of_transfer or picking_id.create_date
                                new_rate_ids = company.currency_id_dif._get_rates(company,date)
                                if new_rate_ids:
                                    new_rate = 1 / new_rate_ids[company.currency_id_dif.id]
                            if stock_move_id.location_id.usage == 'supplier':
                                supplier = True
                            else:
                                if 'tasa' in vals:
                                    new_rate = vals['tasa']
                            standard_price_usd = float(vals['unit_cost']) / new_rate
                        else:
                            standard_price_usd = product_id.with_company(company.id).standard_price_usd
                        vals['unit_cost_usd'] = standard_price_usd
                        vals['value_usd'] = float(vals['quantity']) * standard_price_usd
                        vals['tasa'] = new_rate
                        if vals.get('stock_move_id'):
                            stock_move_id = self.env['stock.move'].search([('id', '=', vals.get('stock_move_id'))])
                            if stock_move_id.location_id.usage in ['supplier','production']:
                                supplier = True
                                product_id.with_company(company.id).standard_price_usd = standard_price_usd
                                # product_id.standard_price = standard_price_usd * new_rate
                        if product_id.with_company(company.id).cost_method in ('average', 'fifo') and supplier:
                            vals['remaining_value_usd'] = float(vals['quantity']) * standard_price_usd
                    else:
                        product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                        if float(vals['value']) < 0:
                            vals['value_usd'] = float(vals['value']) / company.currency_id_dif.rate
                            #vals['value_usd'] = product_id.with_company(company.id).qty_available * product_id.with_company(company.id).standard_price_usd
            else:
                product_id = self.env['product.product'].search([('id', '=', vals['product_id'])])
                if vals.get('stock_move_id'):
                    stock_move_id = self.env['stock.move'].search([('id', '=', vals.get('stock_move_id'))])
                    if stock_move_id.location_id.usage in ['supplier','production']:
                        if product_id.with_company(company.id).cost_method == 'average':
                            if product_id.with_company(company.id).standard_price_usd == 0:
                                product_id.with_company(company.id).standard_price_usd = vals['unit_cost_usd']
        #print('creando valores de inventario', vals)
        res = super(StockValuationLayer, self).create(vals)
        for sl in res:
            if sl.stock_move_id:
                if sl.stock_move_id.location_id.usage in ['supplier','production'] and not sl.stock_landed_cost_id:
                    if sl.product_id.with_company(company.id).cost_method == 'average':
                        # print('entra en el promedio')
                        # print('sl.product_id.with_company(company.id).value_usd_svl',sl.product_id.value_usd_svl)
                        # print('sl.product_id.with_company(company.id).value_svl', sl.product_id.with_company(company.id).value_svl)
                        # print('sl.product_id.with_company(company.id).quantity_svl',sl.product_id.with_company(company.id).quantity_svl)
                        sl.product_id.with_company(company.id).standard_price_usd = sl.product_id.value_usd_svl / sl.product_id.with_company(company.id).quantity_svl

        return res