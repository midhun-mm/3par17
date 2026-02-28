# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

logger = logging.getLogger(__name__)

class Productos(models.Model):
    _inherit = 'product.template'

    currency_id_dif = fields.Many2one('res.currency', string='Moneda Diferente', default=lambda self: self.env.company.currency_id_dif.id)

    list_price_usd = fields.Monetary(string="Precio de venta $", currency_field='currency_id_dif')
    standard_price_usd = fields.Float(string="Costo $", inverse='_set_standard_price_usd', compute='_compute_standard_price_usd', currency_field='currency_id_dif')
    costo_reposicion_usd = fields.Monetary(string="Costo Reposición $", currency_field='currency_id_dif')

    def _price_compute(self, price_type, uom=None, currency=None, company=None, date=False):
        logger.info('Estes es otro')
        logger.info('Estes es otro')
        logger.info('Estes es otro')
        logger.info('Estes es otro')
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        company = company or self.env.company
        date = date or fields.Date.context_today(self)

        self = self.with_company(company)
        if price_type == 'standard_price':
            logger.info('uno')
            # standard_price field can only be seen by users in base.group_user
            # Thus, in order to compute the sale price from the cost for users not in this group
            # We fetch the standard price as the superuser
            self = self.sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for template in self:
            logger.info('dos')
            price = template[price_type] or 0.0
            price_currency = template.currency_id
            if price_type == 'standard_price':
                logger.info('tres')
                if not price and template.product_variant_ids:
                    logger.info('cuatro')
                    price = template.product_variant_ids[0].standard_price
                price_currency = template.cost_currency_id
            elif price_type == 'list_price':
                logger.info('cinco')
                price += template._get_attributes_extra_price()

            if uom:
                logger.info('seis')
                price = template.uom_id._compute_price(price, uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            if currency:
                logger.info('siete')
                logger.info(price)
                price = price_currency._convert(price, currency, company, date)

            prices[template.id] = price
        logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        return prices

    def _set_standard_price_usd(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.standard_price_usd = template.standard_price_usd

    @api.depends_context('company')
    @api.depends('product_variant_ids', 'product_variant_ids.standard_price_usd')
    def _compute_standard_price_usd(self):
        # Depends on force_company context because standard_price is company_dependent
        # on the product_product
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.standard_price_usd = template.product_variant_ids.standard_price_usd
        for template in (self - unique_variants):
            template.standard_price_usd = 0.0

    @api.onchange('list_price_usd')
    def _onchange_list_price_usd(self):
        for rec in self:
            if rec.list_price_usd:
                if rec.list_price_usd >0:
                    tasa = self.env.company.currency_id_dif
                    if tasa:
                        rec.list_price = rec.list_price_usd * tasa.rate

    @api.onchange('standard_price_usd')
    def _onchange_standard_price_usd(self):
        for rec in self:
            if len(rec.product_variant_ids) == 1:
                rec.product_variant_ids[0].standard_price_usd = rec.standard_price_usd

            if rec.standard_price_usd and rec.categ_id.property_valuation == 'manual_periodic':
                if rec.standard_price_usd > 0:
                    tasa = self.env.company.currency_id_dif
                    if tasa:
                        rec.standard_price = rec.standard_price_usd * tasa.rate


