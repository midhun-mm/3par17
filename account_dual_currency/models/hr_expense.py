# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields,  models, _
from odoo.tools import float_repr


class HrExpenseInherit(models.Model):
    _inherit = "hr.expense"


    @api.depends('currency_id', 'total_amount_currency', 'date')
    def _compute_currency_rate(self):
        """
            We want the default odoo rate when the following change:
            - the currency of the expense
            - the total amount in foreign currency
            - the date of the expense
            this will cause the rate to be recomputed twice with possible changes but we don't have the required fields
            to store the override state in stable
        """
        date_today = fields.Date.context_today(self)
        for expense in self:
            if expense.is_multiple_currency:
                if (
                        expense.currency_id != expense._origin.currency_id
                        or expense.total_amount_currency != expense._origin.total_amount_currency
                        or expense.date != expense._origin.date
                ):
                    currency_rate = self.env['res.currency']._get_conversion_rate(
                        from_currency=expense.currency_id,
                        to_currency=expense.company_currency_id,
                        company=expense.company_id,
                        date=expense.date or date_today,
                    )
                    if expense.company_currency_id != self.env.company.currency_id_dif:
                        expense.currency_rate = 1 / currency_rate
                    else:
                        expense.currency_rate = currency_rate


                    # expense.currency_rate = self.env['res.currency']._get_conversion_rate(
                    #     from_currency=expense.currency_id,
                    #     to_currency=expense.company_currency_id,
                    #     company=expense.company_id,
                    #     date=expense.date or date_today,
                    # )
                else:
                    expense.currency_rate = expense.total_amount / expense.total_amount_currency if expense.total_amount_currency else 1.0
            else:  # Mono-currency case computation shortcut, no need for the label if there is no conversion
                expense.currency_rate = 1.0
                expense.label_currency_rate = False
                continue

            expense.label_currency_rate = _(
                '1 %(exp_cur)s = %(rate)s %(comp_cur)s',
                exp_cur=expense.currency_id.name,
                rate=float_repr(expense.currency_rate, 6),
                comp_cur=expense.company_currency_id.name,
            )