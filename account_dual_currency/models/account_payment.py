# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountMove(models.Model):
    _inherit = 'account.payment'

    tax_today = fields.Float(string="Tasa", default=lambda self: self._get_default_tasa(), digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency",
                                      string="Divisa de Referencia",
                                      default=lambda self: self.env.company.currency_id_dif )
    currency_id_company = fields.Many2one("res.currency",
                                          string="Divisa compañia",
                                          default=lambda self: self.env.company.currency_id)
    amount_local = fields.Monetary(string="Importe local", currency_field='currency_id_company')
    amount_ref = fields.Monetary(string="Importe referencia", currency_field='currency_id_dif')
    currency_equal = fields.Boolean(compute="_currency_equal")
    move_id_dif = fields.Many2one(
        'account.move', 'Asiento contable diferencia',  # required=True,
        readonly=True,
        help="Asiento contable de diferencia en tipo de cambio")

    currency_id_name = fields.Char(related="currency_id.name")
    journal_igtf_id = fields.Many2one('account.journal', string='Diario IGTF', check_company=True)
    aplicar_igtf_divisa = fields.Boolean(string="Aplicar IGTF")
    igtf_divisa_porcentage = fields.Float('% IGTF', related='company_id.igtf_divisa_porcentage')

    mount_igtf = fields.Monetary(currency_field='currency_id', string='Importe IGTF', readonly=True,
                                 digits='Dual_Currency')

    amount_total_pagar = fields.Monetary(currency_field='currency_id', string="Total Pagar(Importe + IGTF):",
                                         readonly=True)

    move_id_igtf_divisa = fields.Many2one(
        'account.move', 'Asiento IGTF Divisa',
        readonly=True)

    def _get_default_tasa(self):
        return self.env.company.currency_id_dif.rate

    @api.depends('currency_id_dif','currency_id','amount','tax_today')
    def _currency_equal(self):
        for rec in self:
            currency_equal = rec.currency_id_company != rec.currency_id
            if currency_equal:
                rec.amount_local = rec.amount * rec.tax_today
                rec.amount_ref = rec.amount
            else:
                rec.amount_local = rec.amount
                rec.amount_ref = (rec.amount / rec.tax_today) if rec.amount > 0 and rec.tax_today > 0 else 0
            rec.currency_equal = currency_equal

            if rec.aplicar_igtf_divisa:
                if rec.currency_id.name == 'USD':
                    rec.mount_igtf = rec.amount * rec.igtf_divisa_porcentage / 100
                    rec.amount_total_pagar = rec.mount_igtf + rec.amount
                else:
                    rec.mount_igtf = 0
                    rec.amount_total_pagar = rec.amount
            else:
                rec.mount_igtf = 0
                rec.amount_total_pagar = rec.amount

    def action_draft(self):
        ''' posted -> draft '''
        res = super().action_draft()
        self.move_id_dif.button_draft()
        if self.move_id_igtf_divisa:
            if self.move_id_igtf_divisa.state == 'done':
                self.move_id_igtf_divisa.button_draft()

    def action_cancel(self):
        ''' draft -> cancelled '''
        res = super().action_cancel()
        self.move_id_dif.button_cancel()
        if self.move_id_igtf_divisa:
            self.move_id_igtf_divisa.button_cancel()

    def action_post(self):
        res = super().action_post()
        ''' draft -> posted '''
        self.move_id_dif._post(soft=False)
        """Genera la retencion IGTF """
        for pago in self:
            if not pago.move_id_igtf_divisa:
                if pago.aplicar_igtf_divisa:
                    pago.register_move_igtf_divisa_payment()
            else:
                if pago.move_id_igtf_divisa.state == 'draft':
                    pago.move_id_igtf_divisa.action_post()


    def register_move_igtf_divisa_payment(self):
        '''Este método realiza el asiento contable de la comisión según el porcentaje que indica la compañia'''
        #self.env['ir.sequence'].with_context(ir_sequence_date=self.date_advance).next_by_code(sequence_code)
        diario = self.journal_igtf_id or self.journal_id
        vals = {
            'date': self.date,
            'journal_id': diario.id,
            'currency_id': self.currency_id.id,
            'state': 'draft',
            'tax_today':self.tax_today,
            'ref':self.ref,
            'move_type': 'entry',
            'line_ids': [
                (0, 0, {
                'account_id': diario.company_id.account_journal_payment_debit_account_id.id if self.payment_type == 'inbound' else diario.company_id.account_journal_payment_credit_account_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'date_maturity': False,
                'ref': "Comisión IGTF Divisa",
                'date': self.date,
                'partner_id': self.partner_id.id,
                'name': "Comisión IGTF Divisa",
                'journal_id': self.journal_id.id,
                'credit': float(self.mount_igtf * self.tax_today) if not self.payment_type == 'inbound' else float(0.0),
                'debit': float(self.mount_igtf * self.tax_today) if self.payment_type == 'inbound' else float(0.0),
                'amount_currency': -self.mount_igtf if not self.payment_type == 'inbound' else self.mount_igtf,
            }),
                (0, 0, {
                'account_id': self.company_id.account_debit_wh_igtf_id.id if self.payment_type == 'inbound' else self.company_id.account_credit_wh_igtf_id.id,
                'company_id': self.company_id.id,
                'currency_id': self.currency_id.id,
                'date_maturity': False,
                'ref': "Comisión IGTF Divisa",
                'date': self.date,
                'name': "Comisión IGTF Divisa",
                'journal_id': self.journal_id.id,
                'credit': float(self.mount_igtf * self.tax_today) if self.payment_type == 'inbound' else float(0.0),
                'debit': float(self.mount_igtf * self.tax_today) if not self.payment_type == 'inbound' else float(0.0),
                'amount_currency': -self.mount_igtf if self.payment_type == 'inbound' else self.mount_igtf,
            }),
            ],
        }


        move_id = self.env['account.move'].with_context(check_move_validity=False).create(vals)

        if move_id:
            res = {'move_id_igtf_divisa': move_id.id}
            self.write(res)
            move_id.action_post()
        return True

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        res = super()._prepare_move_line_default_vals(write_off_line_vals, force_balance)
        total_debit = 0
        total_credit = 0
        if res:
            currency_id = res[0]['currency_id']
        currencies_are_different = self.currency_id_company.id != currency_id
        for line in res:
            if line['account_id'] == self.outstanding_account_id.id:
                line['tax_today'] = self.tax_today
                if currencies_are_different:
                    line['debit'] = (line['amount_currency'] * self.tax_today) if line['debit'] else 0
                    line['credit'] = (abs(line['amount_currency']) * self.tax_today) if line['credit'] else 0
            elif line['account_id'] == self.destination_account_id.id:
                tasa_factura = self.env.context.get('tasa_factura', self.tax_today)
                line['tax_today'] = tasa_factura if write_off_line_vals else self.tax_today
                if currencies_are_different:
                    line['debit'] = (line['amount_currency'] * line['tax_today']) if line['debit'] else 0
                    line['credit'] = (abs(line['amount_currency']) * line['tax_today']) if line['credit'] else 0
            else:
                continue
            total_debit += line['debit']
            total_credit += line['credit']

        payment_difference_handling = self._context.get('payment_difference_handling', False)
        if currencies_are_different and payment_difference_handling == 'open' and total_debit != total_credit:
            if self.payment_type == 'inbound':
                # Receive money.
                write_off = sum(x['credit'] for x in write_off_line_vals)
                liquidy = sum(x['debit'] for x in res if x['account_id'] == self.outstanding_account_id.id)
            if self.payment_type == 'outbound':
                # Send money.
                write_off = sum(x['debit'] for x in write_off_line_vals)
                liquidy = sum(x['credit'] for x in res if x['account_id'] == self.outstanding_account_id.id)
            counterpart = liquidy - write_off
            for r in res:
                if r['account_id'] == self.destination_account_id.id:
                    if self.payment_type == 'inbound':
                        r['credit'] = counterpart
                        r['balance'] = -counterpart
                    if self.payment_type == 'outbound':
                        r['debit'] = counterpart
                        r['balance'] = counterpart
        return res

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        return (
            'date', 'amount', 'payment_type', 'partner_type', 'payment_reference', 'is_internal_transfer',
            'currency_id', 'partner_id', 'destination_account_id', 'partner_bank_id', 'journal_id', 'tax_today'
        )

    def _synchronize_to_moves(self, changed_fields):
        if 'tax_today' in changed_fields:
            for pay in self.with_context(skip_account_move_synchronization=True):
                pay.move_id.write({
                    'tax_today': pay.tax_today,
                })
        super(AccountMove, self)._synchronize_to_moves(changed_fields)

    # @api.depends('reconciled_invoice_ids')
    # def _compute_payment_state(self):
    #     for payment in self:
    #         payment.payment_state = payment.reconciled_invoice_ids[0].payment_state if payment.reconciled_invoice_ids else None
