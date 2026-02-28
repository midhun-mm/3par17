# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleReportInherit(models.Model):
    _inherit = 'sale.report'


    def _select_sale(self):
        select_ = f"""
            MIN(l.id) AS id,
            l.product_id AS product_id,
            t.uom_id AS product_uom,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.product_uom_qty / u.factor * u2.factor) ELSE 0 END AS product_uom_qty,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.qty_delivered / u.factor * u2.factor) ELSE 0 END AS qty_delivered,
            CASE WHEN l.product_id IS NOT NULL THEN SUM((l.product_uom_qty - l.qty_delivered) / u.factor * u2.factor) ELSE 0 END AS qty_to_deliver,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.qty_invoiced / u.factor * u2.factor) ELSE 0 END AS qty_invoiced,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(l.qty_to_invoice / u.factor * u2.factor) ELSE 0 END AS qty_to_invoice,
            CASE WHEN l.product_id IS NOT NULL THEN 
                CASE WHEN s.currency_id = partner.currency_id_dif THEN
                    SUM(l.price_total
                        * {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                ELSE
                    SUM(l.price_total
                        / {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                END        
            ELSE 0 END AS price_total,
            CASE WHEN l.product_id IS NOT NULL THEN 
                 CASE WHEN s.currency_id = partner.currency_id_dif THEN
                    SUM(l.price_subtotal
                        * {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                ELSE
                    SUM(l.price_subtotal
                        / {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                END        
            ELSE 0 END AS price_subtotal,
            CASE WHEN l.product_id IS NOT NULL THEN 
                 CASE WHEN s.currency_id = partner.currency_id_dif THEN
                    SUM(l.untaxed_amount_to_invoice
                        * {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                ELSE
                    SUM(l.untaxed_amount_to_invoice
                        / {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                END        
            ELSE 0 END AS untaxed_amount_to_invoice,
            CASE WHEN l.product_id IS NOT NULL THEN 
                 CASE WHEN s.currency_id = partner.currency_id_dif THEN
                    SUM(l.untaxed_amount_invoiced
                        * {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                ELSE
                    SUM(l.untaxed_amount_invoiced
                        / {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                END        
            ELSE 0 END AS untaxed_amount_invoiced,
            COUNT(*) AS nbr,
            s.name AS name,
            s.date_order AS date,
            s.state AS state,
            s.invoice_status as invoice_status,
            s.partner_id AS partner_id,
            s.user_id AS user_id,
            s.company_id AS company_id,
            s.campaign_id AS campaign_id,
            s.medium_id AS medium_id,
            s.source_id AS source_id,
            t.categ_id AS categ_id,
            s.pricelist_id AS pricelist_id,
            s.analytic_account_id AS analytic_account_id,
            s.team_id AS team_id,
            p.product_tmpl_id,
            partner.commercial_partner_id AS commercial_partner_id,
            partner.country_id AS country_id,
            partner.industry_id AS industry_id,
            partner.state_id AS state_id,
            partner.zip AS partner_zip,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(p.weight * l.product_uom_qty / u.factor * u2.factor) ELSE 0 END AS weight,
            CASE WHEN l.product_id IS NOT NULL THEN SUM(p.volume * l.product_uom_qty / u.factor * u2.factor) ELSE 0 END AS volume,
            l.discount AS discount,
            CASE WHEN l.product_id IS NOT NULL THEN 
                 CASE WHEN s.currency_id = partner.currency_id_dif THEN
                    SUM(l.price_unit * l.product_uom_qty * l.discount / 100.0
                        * {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                ELSE
                    SUM(l.price_unit * l.product_uom_qty * l.discount / 100.0
                        / {self._case_value_or_one('s.currency_rate')}
                        * {self._case_value_or_one('currency_table.rate')}
                        ) 
                END        
            ELSE 0 END AS discount_amount,
            concat('sale.order', ',', s.id) AS order_reference"""

        additional_fields_info = self._select_additional_fields()
        template = """,
            %s AS %s"""
        for fname, query_info in additional_fields_info.items():
            select_ += template % (query_info, fname)

        return select_


    def _group_by_sale(self):
        res = super(SaleReportInherit, self)._group_by_sale()
        res += """,
            partner.currency_id_dif"""
        return res