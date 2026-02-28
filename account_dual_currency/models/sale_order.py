# -*- coding: utf-8 -*-

from itertools import groupby
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command

import logging
logger = logging.getLogger(__name__)
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _recompute_prices(self):
        logger.info('RECOMPUTE PRICES')
        logger.info('RECOMPUTE PRICES')
        logger.info('RECOMPUTE PRICES')
        logger.info('RECOMPUTE PRICES')
        logger.info('RECOMPUTE PRICES')
        lines_to_recompute = self._get_update_prices_lines()
        logger.info(lines_to_recompute)
        lines_to_recompute.invalidate_recordset(['pricelist_item_id'])
        lines_to_recompute._compute_price_unit()
        # Special case: we want to overwrite the existing discount on _recompute_prices call
        # i.e. to make sure the discount is correctly reset
        # if pricelist discount_policy is different than when the price was first computed.
        lines_to_recompute.discount = 0.0
        lines_to_recompute._compute_discount()
        self.show_update_pricelist = False

    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()

        values = {
            'ref': self.client_order_ref or '',
            'move_type': 'out_invoice',
            'narration': self.note,
            'currency_id': self.currency_id.id,
            'tax_today': self.company_id.currency_id_dif.rate,
            'campaign_id': self.campaign_id.id,
            'medium_id': self.medium_id.id,
            'source_id': self.source_id.id,
            'team_id': self.team_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'fiscal_position_id': (self.fiscal_position_id or self.fiscal_position_id._get_fiscal_position(
                self.partner_invoice_id)).id,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.payment_term_id.id,
            'invoice_user_id': self.user_id.id,
            'payment_reference': self.reference,
            'transaction_ids': [Command.set(self.transaction_ids.ids)],
            'company_id': self.company_id.id,
            'invoice_line_ids': [],
            'user_id': self.user_id.id,
        }
        if self.journal_id:
            values['journal_id'] = self.journal_id.id
        return values