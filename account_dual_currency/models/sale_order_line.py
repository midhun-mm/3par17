# -*- coding: utf-8 -*-

from itertools import groupby
from odoo import api, fields, models, tools, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
import logging
logger = logging.getLogger(__name__)

class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'


    def _compute_base_price(self, product, quantity, uom, date, currency):
        """ Compute the base price for a given rule

        :param product: recordset of product (product.product/product.template)
        :param float qty: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency conversions
        :param currency: currency in which the returned price must be expressed

        :returns: base price, expressed in provided pricelist currency
        :rtype: float
        """
        currency.ensure_one()
        logger.info('Voy a iniciar')
        logger.info('Voy a iniciar')
        logger.info('·····································································')
        rule_base = self.base or 'list_price'
        if rule_base == 'pricelist' and self.base_pricelist_id:
            logger.info('uno')
            price = self.base_pricelist_id._get_product_price(
                product, quantity, currency=self.base_pricelist_id.currency_id, uom=uom, date=date
            )
            src_currency = self.base_pricelist_id.currency_id
        elif rule_base == "standard_price":
            logger.info('dos')
            src_currency = product.cost_currency_id
            price = product._price_compute(rule_base, uom=uom, date=date)[product.id]
        else: # list_price
            logger.info('tres')
            src_currency = product.currency_id
            price = product._price_compute(rule_base, uom=uom, date=date)[product.id]

        if src_currency != currency:
            logger.info('cuatro')
            logger.info(src_currency)
            logger.info(currency)
            logger.info(price)
            logger.info(date)
            logger.info(self.env.company)
            price = src_currency._convert(price, currency, self.env.company, date, round=False)
            logger.info(price)
        logger.info('·····································································')
        return price

    def _compute_price(self, product, quantity, uom, date, currency=None):
        """Compute the unit price of a product in the context of a pricelist application.

        Note: self and self.ensure_one()

        :param product: recordset of product (product.product/product.template)
        :param float qty: quantity of products requested (in given uom)
        :param uom: unit of measure (uom.uom record)
        :param datetime date: date to use for price computation and currency conversions
        :param currency: currency (for the case where self is empty)

        :returns: price according to pricelist rule or the product price, expressed in the param
                  currency, the pricelist currency or the company currency
        :rtype: float
        """
        logger.info('COMPUTE PRICE')
        logger.info('COMPUTE PRICE')
        logger.info('COMPUTE PRICE')
        logger.info('COMPUTE PRICE')
        self and self.ensure_one()  # self is at most one record
        product.ensure_one()
        uom.ensure_one()

        currency = currency or self.currency_id or self.env.company.currency_id
        currency.ensure_one()

        # Pricelist specific values are specified according to product UoM
        # and must be multiplied according to the factor between uoms
        product_uom = product.uom_id
        if product_uom != uom:
            logger.info('uno')
            convert = lambda p: product_uom._compute_price(p, uom)
        else:
            logger.info('dos')
            convert = lambda p: p

        if self.compute_price == 'fixed':
            logger.info('tres')
            logger.info(self.fixed_price)
            price = convert(self.fixed_price)
        elif self.compute_price == 'percentage':
            logger.info('cuatro')
            base_price = self._compute_base_price(product, quantity, uom, date, currency)
            price = (base_price - (base_price * (self.percent_price / 100))) or 0.0
        elif self.compute_price == 'formula':
            logger.info('cinco')
            logger.info(product)
            logger.info(quantity)
            logger.info(uom)
            logger.info(date)
            logger.info(currency)
            base_price = self._compute_base_price(product, quantity, uom, date, currency)
            logger.info(base_price)
            # complete formula
            price_limit = base_price
            price = (base_price - (base_price * (self.price_discount / 100))) or 0.0
            if self.price_round:
                price = tools.float_round(price, precision_rounding=self.price_round)

            if self.price_surcharge:
                price += convert(self.price_surcharge)

            if self.price_min_margin:
                price = max(price, price_limit + convert(self.price_min_margin))

            if self.price_max_margin:
                price = min(price, price_limit + convert(self.price_max_margin))
        else:  # empty self, or extended pricelist price computation logic
            logger.info('seis')
            price = self._compute_base_price(product, quantity, uom, date, currency)
        logger.info(price)

        return price



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_pricelist_price(self):
        """Compute the price given by the pricelist for the given line information.

        :return: the product sales price in the order currency (without taxes)
        :rtype: float
        """
        self.ensure_one()
        self.product_id.ensure_one()

        price = self.pricelist_item_id._compute_price(
            product=self.product_id.with_context(**self._get_product_price_context()),
            quantity=self.product_uom_qty or 1.0,
            uom=self.product_uom,
            date=self.order_id.date_order,
            currency=self.currency_id,
        )
        logger.info('GET PRICELIST PRICE')
        logger.info('GET PRICELIST PRICE')
        logger.info('GET PRICELIST PRICE')
        logger.info('GET PRICELIST PRICE')
        logger.info(price)
        logger.info(self._get_product_price_context())

        return price

    def _get_display_price(self):
        """Compute the displayed unit price for a given line.

        Overridden in custom flows:
        * where the price is not specified by the pricelist
        * where the discount is not specified by the pricelist

        Note: self.ensure_one()
        """
        self.ensure_one()

        pricelist_price = self._get_pricelist_price()
        logger.info('Voy para acaaaa')
        logger.info('Voy para acaaaa')
        logger.info('Voy para acaaaa')
        logger.info(pricelist_price)

        if self.order_id.pricelist_id.discount_policy == 'with_discount':
            return pricelist_price

        if not self.pricelist_item_id:
            # No pricelist rule found => no discount from pricelist
            return pricelist_price

        base_price = self._get_pricelist_price_before_discount()

        # negative discounts (= surcharge) are included in the display price
        return max(base_price, pricelist_price)

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        for line in self:
            logger.info('COMPUTE PRICE UNIT')
            logger.info('COMPUTE PRICE UNIT')
            logger.info('COMPUTE PRICE UNIT')
            logger.info('COMPUTE PRICE UNIT')
            logger.info(line)
            # check if there is already invoiced amount. if so, the price shouldn't change as it might have been
            # manually edited
            if line.qty_invoiced > 0 or (line.product_id.expense_policy == 'cost' and line.is_expense):
                logger.info('uno')
                continue
            if not line.product_uom or not line.product_id:
                logger.info('dos')
                line.price_unit = 0.0
            else:
                logger.info('tres')
                line = line.with_company(line.company_id)
                price = line._get_display_price()
                logger.info(price)
                logger.info(price)
                logger.info(price)
                line.price_unit = line.product_id._get_tax_included_unit_price_from_price(
                    price,
                    line.currency_id or line.order_id.currency_id,
                    product_taxes=line.product_id.taxes_id.filtered(
                        lambda tax: tax.company_id == line.env.company
                    ),
                    fiscal_position=line.order_id.fiscal_position_id,
                )

    def _prepare_invoice_line(self, **optional_values):
        """Prepare the values to create the new invoice line for a sales order line.

        :param optional_values: any parameter that should be added to the returned invoice line
        :rtype: dict
        """
        tax_today = self.company_id.currency_id_dif.rate
        self.ensure_one()
        res = {
            'display_type': self.display_type or 'product',
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': self.price_unit,
            'price_unit_usd': self.price_unit if self.currency_id == self.company_id.currency_id_dif else self.price_unit / tax_today,
            'price_subtotal_usd': self.price_subtotal if self.currency_id == self.company_id.currency_id_dif else self.price_subtotal / tax_today,
            'tax_ids': [Command.set(self.tax_id.ids)],
            'sale_line_ids': [Command.link(self.id)],
            'is_downpayment': self.is_downpayment,
        }
        self._set_analytic_distribution(res, **optional_values)
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res