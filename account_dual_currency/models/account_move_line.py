# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, Command, _
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.models import NewId
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    debit_usd = fields.Monetary(currency_field='currency_id_dif', string='Débito $', store=True, compute="_debit_usd",
                                 readonly=False)
    credit_usd = fields.Monetary(currency_field='currency_id_dif', string='Crédito $', store=True,
                                 compute="_credit_usd", readonly=False)
    tax_today = fields.Float(related="move_id.tax_today", store=True, digits='Dual_Currency_rate')
    currency_id_dif = fields.Many2one("res.currency", related="move_id.currency_id_dif", store=True)
    price_unit_usd = fields.Monetary(currency_field='currency_id_dif', string='Precio $', store=True,
                                     compute='_price_unit_usd', readonly=False)
    price_subtotal_usd = fields.Monetary(currency_field='currency_id_dif', string='SubTotal $', store=True,
                                         compute="_price_subtotal_usd", digits='Dual_Currency')
    amount_residual_usd = fields.Monetary(string='Residual Amount USD', computed='_compute_amount_residual_usd', store=True,
                                       help="The residual amount on a journal item expressed in the company currency.")
    balance_usd = fields.Monetary(string='Balance Ref.',
                                  currency_field='currency_id_dif', store=True, readonly=False,
                                  compute='_compute_balance_usd',
                                  # default=lambda self: self._compute_balance_usd(),
                                  help="Technical field holding the debit_usd - credit_usd in order to open meaningful graph views from reports")

    @api.depends('currency_rate', 'balance')
    def _compute_amount_currency(self):
        for line in self:
            if line.amount_currency is False:
                line.amount_currency = line.currency_id.round(line.balance * line.currency_rate)
            if line.currency_id == line.company_id.currency_id:
                line.amount_currency = line.balance
            else:
                if line.tax_today:
                    line.amount_currency = line.currency_id._convert_new(to_currency=line.currency_id, from_amount=line.balance,
                                                                            to_rate=line.tax_today, from_rate=1)
                else:
                    line.amount_currency = line.currency_id._convert_new(to_currency=line.currency_id, from_amount=line.balance,
                                                                     to_rate=line.move_id.tax_today, from_rate=1)




    @api.depends('currency_id', 'company_id', 'move_id.date','move_id.tax_today')
    def _compute_currency_rate(self):
        for line in self:
            #print('pasando por _compute_currency_rate')
            # self.env.context = dict(self.env.context, tasa_factura=line.move_id.tax_today, calcular_dual_currency=True)
            line.currency_rate = 1 / line.move_id.tax_today if line.move_id.tax_today > 0 else 1
            #print('line.currency_rate', line.currency_rate)
        # self.env.context = dict(self.env.context, tasa_factura=None, calcular_dual_currency=False)

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        self._debit_usd()
        self._credit_usd()

    @api.onchange('price_unit_usd')
    def _onchange_price_unit_usd(self):
        for rec in self:
            if rec.move_id.currency_id != rec.company_id.currency_id:
                rec.price_unit = rec.price_unit_usd
            else:
                if rec.move_id.move_type not in ['in_invoice', 'in_refund']:
                    rec.price_unit = rec.price_unit_usd * rec.tax_today


    @api.onchange('product_id')
    def _onchange_product_id(self):
        #super()._onchange_product_id()
        self._price_unit_usd()



    @api.depends('price_unit', 'product_id')
    def _price_unit_usd(self):
        for rec in self:
            if isinstance(rec.id, NewId):
                rec_sin_newId = self.browse(rec.ids)
                if rec_sin_newId:
                    rec = rec_sin_newId
            if rec.price_unit > 0:
                if rec.move_id.currency_id == self.env.company.currency_id:
                    rec.price_unit_usd = rec.move_id.currency_id._convert_new(to_currency=rec.currency_id, from_amount=rec.price_unit, to_rate=rec.tax_today, from_rate=1)
                else:
                    rec.price_unit_usd = rec.price_unit
            else:
                rec.price_unit_usd = 0

    @api.depends('price_unit_usd', 'quantity')
    def _price_subtotal_usd(self):
        for rec in self:
            rec.price_subtotal_usd = rec.price_unit_usd * rec.quantity
            # if rec.price_subtotal > 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         rec.price_subtotal_usd = (rec.price_subtotal / rec.tax_today) if rec.tax_today > 0 else 0
            #     else:
            #         rec.price_subtotal_usd = rec.price_subtotal
            # else:
            #     rec.price_subtotal_usd = 0

            # if rec.price_subtotal_usd > 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         rec.price_subtotal = rec.price_subtotal_usd * rec.tax_today
            #     else:
            #         rec.price_subtotal = rec.price_subtotal_usd
            # else:
            #     rec.price_subtotal = 0

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if 'tax_today' not in fields:
            return super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                           orderby=orderby, lazy=lazy)
        res = super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        for group in res:
            if group.get('__domain'):
                records = self.search(group['__domain'])
                group['tax_today'] = 0
        return res

    @api.depends('debit', 'amount_currency', 'tax_today',)
    def _debit_usd(self):

        for line in self:
            # print('pasando por _debit_usd', rec.display_type)
            if line.debit or line.amount_currency > 0:
                if line.currency_id.id == self.env.company.currency_id_dif.id:
                    line.debit_usd = abs(line.amount_currency)
                elif line.currency_id.id == self.env.company.currency_id.id:
                    if line.move_id.tax_today:
                        line.debit_usd = round(line.debit / line.move_id.tax_today, 2)
                    else:
                        currency_rate = self.env['res.currency']._get_conversion_rate(
                            from_currency=line.move_id.currency_id,
                            to_currency=self.env.company.currency_id_dif,
                            company=line.company_id,
                            date=line.move_id.date,
                        )
                        if currency_rate:
                            line.debit_usd = line.debit / currency_rate
                        else:
                            line.debit_usd = 0
                else:
                    currency_rate = self.env['res.currency']._get_conversion_rate(
                        from_currency=line.move_id.currency_id,
                        to_currency=self.env.company.currency_id_dif,
                        company=line.company_id,
                        date=line.move_id.date,
                    )
                    if currency_rate:
                        line.debit_usd = abs(line.amount_currency) * currency_rate
                    else:
                        line.debit_usd = 0
            else:
                line.debit_usd = 0
            # if not rec.debit == 0:
            #     if rec.move_id.currency_id == self.env.company.currency_id:
            #         if rec.display_type == 'product' and rec.move_id.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']:
            #             rec.debit_usd = rec.price_subtotal_usd
            #         else:
            #             amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
            #             rec.debit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
            #         #rec.debit = amount_currency
            #     else:
            #         if rec.move_id.currency_id == self.env.company.currency_id_dif:
            #             # rec.debit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
            #             rec.debit_usd = rec.move_id.currency_id._convert_new(to_currency=rec.currency_id, from_amount=rec.debit, to_rate=rec.tax_today, from_rate=1)
            #         else:
            #             #busca la tasa de la moneda
            #             #rate = self.env['res.currency.rate'].search(
            #             #    [('currency_id', '=', rec.move_id.currency_id.id), ('name', '=', rec.move_id.date), ('company_id', '=', rec.company_id.id)])
            #             rate = self.env['res.currency']._get_conversion_rate(
            #                 from_currency=rec.move_id.currency_id,
            #                 to_currency=self.env.company.currency_id_dif,
            #                 company=rec.company_id,
            #                 date=rec.move_id.date,
            #             )
            #             if rate:
            #                 rec.debit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1)) * rate
            #
            #         # if not 'calcular_dual_currency' in self.env.context:
            #         #     if not rec.move_id.stock_move_id:
            #         #         module_dual_currency = self.env['ir.module.module'].sudo().search(
            #         #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
            #         #         if module_dual_currency:
            #         #             # rec.debit = ((rec.amount_currency * rec.tax_today) if rec.amount_currency > 0 else (
            #         #             #         (rec.amount_currency * -1) * rec.tax_today))
            #         #             rec.with_context(check_move_validity=False).debit = (rec.debit_usd * rec.tax_today)
            #
            # else:
            #     rec.debit_usd = 0

    @api.depends('credit', 'amount_currency', 'tax_today')
    def _credit_usd(self):
        for line in self:
            # print('pasando por _debit_usd', rec.display_type)
            if line.credit or line.amount_currency < 0:
                if line.currency_id.id == self.env.company.currency_id_dif.id:
                    line.credit_usd = abs(line.amount_currency)
                elif line.currency_id.id == self.env.company.currency_id.id:
                    if line.move_id.tax_today:
                        line.credit_usd = round(line.credit / line.move_id.tax_today, 2)
                    else:
                        currency_rate = self.env['res.currency']._get_conversion_rate(
                            from_currency=line.move_id.currency_id,
                            to_currency=self.env.company.currency_id_dif,
                            company=line.company_id,
                            date=line.move_id.date,
                        )
                        if currency_rate:
                            line.credit_usd = line.credit / currency_rate
                        else:
                            line.credit_usd = 0
                else:
                    currency_rate = self.env['res.currency']._get_conversion_rate(
                        from_currency=line.move_id.currency_id,
                        to_currency=self.env.company.currency_id_dif,
                        company=line.company_id,
                        date=line.move_id.date,
                    )
                    if currency_rate:
                        line.credit_usd = abs(line.amount_currency) * currency_rate
                    else:
                        line.credit_usd = 0
            else:
                line.credit_usd = 0



        # for rec in self:
        #     # tmp = rec.credit_usd if rec.credit_usd > 0 else 0
        #     if not rec.credit == 0:
        #         if rec.move_id.currency_id == self.env.company.currency_id:
        #             if rec.display_type == 'product' and rec.move_id.move_type in ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']:
        #                 rec.credit_usd = rec.price_subtotal_usd
        #             else:
        #                 amount_currency = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
        #                 rec.credit_usd = (amount_currency / rec.tax_today) if rec.tax_today > 0 else 0
        #                 #rec.credit = amount_currency
        #         else:
        #             if rec.move_id.currency_id == self.env.company.currency_id_dif:
        #                 # rec.credit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1))
        #                 rec.credit_usd = rec.move_id.currency_id._convert_new(to_currency=rec.currency_id, from_amount=rec.credit, to_rate=rec.tax_today, from_rate=1)
        #             else:
        #                 #busca la tasa de la moneda
        #                 rate = self.env['res.currency']._get_conversion_rate(
        #                     from_currency=rec.move_id.currency_id,
        #                     to_currency=self.env.company.currency_id_dif,
        #                     company=rec.company_id,
        #                     date=rec.move_id.date,
        #                 )
        #                 if rate:
        #                     rec.credit_usd = (rec.amount_currency if rec.amount_currency > 0 else (rec.amount_currency * -1)) * rate
        #             #model = self.env.context.get('active_model')
        #             #print('contexto--->', self._context)
        #             #print('contexto', self.env.context)
        #             # if not 'calcular_dual_currency' in self.env.context:
        #             #     if not rec.move_id.stock_move_id:
        #             #         module_dual_currency = self.env['ir.module.module'].sudo().search(
        #             #             [('name', '=', 'account_dual_currency'), ('state', '=', 'installed')])
        #             #         if module_dual_currency:
        #             #             #rec.credit = ((rec.amount_currency * rec.tax_today) if rec.amount_currency > 0 else (
        #             #             #        (rec.amount_currency * -1) * rec.tax_today))
        #             #             rec.with_context(check_move_validity=False).credit = rec.credit_usd * rec.tax_today
        #
        #     else:
        #         rec.credit_usd = 0


    @api.depends('debit_usd', 'credit_usd')
    def _compute_balance_usd(self):
        for line in self:
            line.balance_usd = line.debit_usd - line.credit_usd

    @api.depends('debit','credit',
                 # 'debit_usd', 'credit_usd',
                 'amount_currency', 'account_id', 'currency_id', 'move_id.state',
                 'company_id',
                 'matched_debit_ids', 'matched_credit_ids')
    def _compute_amount_residual_usd(self):
        """ Computes the residual amount of a move line from a reconcilable account in the company currency and the line's currency.
            This amount will be 0 for fully reconciled lines or lines from a non-reconcilable account, the original line amount
            for unreconciled lines, and something in-between for partially reconciled lines.
        """
        for line in self:
            if line.id and (line.account_id.reconcile or line.account_id.account_type in ('asset_cash', 'liability_credit_card')):
                reconciled_balance = sum(line.matched_credit_ids.mapped('amount_usd')) \
                                     - sum(line.matched_debit_ids.mapped('amount_usd'))

                line.amount_residual_usd = (line.debit_usd - line.credit_usd) - reconciled_balance

                line.reconciled = (line.amount_residual_usd == 0)
            else:
                # Must not have any reconciliation since the line is not eligible for that.
                line.amount_residual_usd = 0.0
                line.reconciled = False

    def _reconcile_plan_with_sync(self, plan_list, all_amls):
        # Parameter allowing to disable the exchange journal entries on partials.
        disable_partial_exchange_diff = bool(
            self.env['ir.config_parameter'].sudo().get_param('account.disable_partial_exchange_diff'))

        # ==== Prefetch the fields all at once to speedup the reconciliation ====
        # All of those fields will be cached by the orm. Since the amls are split into multiple batches, the orm is not
        # able to prefetch the data for all of them at once. For that reason, we force the orm to populate the cache
        # before doing anything.
        all_amls.move_id
        all_amls.matched_debit_ids
        all_amls.matched_credit_ids

        # ==== Track the invoice's state to call the hook when they become paid ====
        pre_hook_data = all_amls._reconcile_pre_hook()

        # ==== Collect amls data ====
        # All residual amounts are collected and updated until the creation of partials in batch.
        # This is done that way to minimize the orm time for fields invalidation/mark as recompute and
        # recomputation.
        aml_values_map = {
            aml: {
                'aml': aml,
                'amount_residual': aml.amount_residual,
                'amount_residual_usd': aml.amount_residual_usd,
                'amount_residual_currency': aml.amount_residual_currency,
            }
            for aml in all_amls
        }

        # ==== Prepare the partials ====
        partials_values_list = []
        exchange_diff_values_list = []
        exchange_diff_partial_index = []
        all_plan_results = []
        partial_index = 0
        for plan in plan_list:
            plan_results = self \
                .with_context(
                no_exchange_difference=self._context.get('no_exchange_difference') or disable_partial_exchange_diff) \
                ._prepare_reconciliation_plan(plan, aml_values_map)
            all_plan_results.append(plan_results)
            for results in plan_results:
                partials_values_list.append(results['partial_values'])
                if results.get('exchange_values') and results['exchange_values']['move_values']['line_ids']:
                    exchange_diff_values_list.append(results['exchange_values'])
                    exchange_diff_partial_index.append(partial_index)
                    partial_index += 1

        # ==== Create the partials ====
        # Link the newly created partials to the plan. There are needed later for caba exchange entries.
        partials = self.env['account.partial.reconcile'].create(partials_values_list)
        for parcial in partials:
            amount_usd = min(abs(parcial.debit_move_id.amount_residual_usd),
                                 abs(parcial.credit_move_id.amount_residual_usd))
            parcial.write({'amount_usd': abs(amount_usd)})
        start_range = 0
        for plan_results, plan in zip(all_plan_results, plan_list):
            size = len(plan_results)
            plan['partials'] = partials[start_range:start_range + size]
            start_range += size

        # ==== Create the partial exchange journal entries ====
        exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
        for index, exchange_move in zip(exchange_diff_partial_index, exchange_moves):
            partials[index].exchange_move_id = exchange_move

        # ==== Create entries for cash basis taxes ====
        def is_cash_basis_needed(account):
            return account.company_id.tax_exigibility \
                and account.account_type in ('asset_receivable', 'liability_payable')

        if not self._context.get('move_reverse_cancel') and not self._context.get('no_cash_basis'):
            for plan in plan_list:
                if is_cash_basis_needed(plan['amls'].account_id):
                    plan['partials']._create_tax_cash_basis_moves()

        # ==== Prepare full reconcile creation ====
        # First, we need to find all sub-set of amls that are candidates for a full.

        def is_line_reconciled(aml, has_multiple_currencies):
            # Check if the journal item passed as parameter is now fully reconciled.
            if aml.reconciled:
                return True
            if not aml.matched_debit_ids and not aml.matched_credit_ids:
                # Suppose a journal item having balance = 0 but an amount_currency like an exchange difference.
                return False
            if has_multiple_currencies:
                return aml.company_currency_id.is_zero(aml.amount_residual)
            else:
                return aml.currency_id.is_zero(aml.amount_residual_currency)

        full_batches = []
        all_aml_ids = set()
        number2lines = all_amls._reconciled_by_number()
        for plan in plan_list:
            for aml in plan['amls']:
                if 'full_batch_index' in aml_values_map[aml]:
                    continue

                involved_amls = plan['amls']._filter_reconciled_by_number(number2lines)
                all_aml_ids.update(involved_amls.ids)
                full_batch_index = len(full_batches)
                has_multiple_currencies = len(involved_amls.currency_id) > 1
                is_fully_reconciled = all(
                    is_line_reconciled(involved_aml, has_multiple_currencies)
                    for involved_aml in involved_amls
                )
                full_batches.append({
                    'amls': involved_amls,
                    'is_fully_reconciled': is_fully_reconciled,
                })
                for involved_aml in involved_amls:
                    if aml_values_map.get(involved_aml):
                        aml_values_map[involved_aml]['full_batch_index'] = full_batch_index

        # ==== Prefetch the fields all at once to speedup the reconciliation ====
        # Again, we do the same optimization for the prefetching. We need to do it again since most of the values have
        # been invalidated with the creation of the account.partial.reconcile records.
        all_amls = self.browse(list(all_aml_ids))
        all_amls.move_id
        all_amls.matched_debit_ids
        all_amls.matched_credit_ids

        # ==== Prepare the full exchange journal entries ====
        # This part could be bypassed using the 'no_exchange_difference' key inside the context. This is useful
        # when importing a full accounting including the reconciliation like Winbooks.

        exchange_diff_values_list = []
        exchange_diff_full_batch_index = []
        if not self._context.get('no_exchange_difference'):
            for full_batch_index, full_batch in enumerate(full_batches):
                involved_amls = full_batch['amls']
                if not full_batch['is_fully_reconciled']:
                    continue

                # In normal cases, the exchange differences are already generated by the partial at this point meaning
                # there is no journal item left with a zero amount residual in one currency but not in the other.
                # However, after a migration coming from an older version with an older partial reconciliation or due to
                # some rounding issues (when dealing with different decimal places for example), we could need an extra
                # exchange difference journal entry to handle them.
                exchange_lines_to_fix = self.env['account.move.line']
                amounts_list = []
                exchange_max_date = date.min
                for aml in involved_amls:
                    if not aml.company_currency_id.is_zero(aml.amount_residual):
                        exchange_lines_to_fix += aml
                        amounts_list.append({'amount_residual': aml.amount_residual})
                    elif not aml.currency_id.is_zero(aml.amount_residual_currency):
                        exchange_lines_to_fix += aml
                        amounts_list.append({'amount_residual_currency': aml.amount_residual_currency})
                    exchange_max_date = max(exchange_max_date, aml.date)
                exchange_diff_values = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    company=involved_amls.company_id,
                    exchange_date=exchange_max_date,
                )

                # Exchange difference for cash basis entries.
                # If we are fully reversing the entry, no need to fix anything since the journal entry
                # is exactly the mirror of the source journal entry.
                caba_lines_to_reconcile = None
                if is_cash_basis_needed(involved_amls.account_id) and not self._context.get('move_reverse_cancel'):
                    caba_lines_to_reconcile = involved_amls._add_exchange_difference_cash_basis_vals(
                        exchange_diff_values)

                # Prepare the exchange difference.
                if exchange_diff_values['move_values']['line_ids']:
                    exchange_diff_full_batch_index.append(full_batch_index)
                    exchange_diff_values_list.append(exchange_diff_values)
                    full_batch['caba_lines_to_reconcile'] = caba_lines_to_reconcile

        # ==== Create the full exchange journal entries ====
        exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
        for full_batch_index, exchange_move in zip(exchange_diff_full_batch_index, exchange_moves):
            full_batch = full_batches[full_batch_index]
            amls = full_batch['amls']
            full_batch['exchange_move'] = exchange_move
            exchange_move_lines = exchange_move.line_ids.filtered(lambda line: line.account_id == amls.account_id)
            full_batch['amls'] |= exchange_move_lines

        # ==== Create the full reconcile ====
        # Note we are using Command.link and not Command.set because Command.set is triggering an unlink that is
        # slowing down the assignation of the co-fields. Indeed, unlink is forcing a flush.
        full_reconcile_values_list = []
        full_reconcile_full_batch_index = []
        for full_batch_index, full_batch in enumerate(full_batches):
            amls = full_batch['amls']
            involved_partials = amls.matched_debit_ids + amls.matched_credit_ids
            if full_batch['is_fully_reconciled']:
                full_reconcile_values_list.append({
                    'exchange_move_id': full_batch.get('exchange_move') and full_batch['exchange_move'].id,
                    'partial_reconcile_ids': [Command.link(partial.id) for partial in involved_partials],
                    'reconciled_line_ids': [Command.link(aml.id) for aml in amls],
                })
                full_reconcile_full_batch_index.append(full_batch_index)

        self.env['account.full.reconcile'].create(full_reconcile_values_list)

        # === Cash basis rounding autoreconciliation ===
        # In case a cash basis rounding difference line got created for the transition account, we reconcile it with the corresponding lines
        # on the cash basis moves (so that it reaches full reconciliation and creates an exchange difference entry for this account as well)
        for full_batch in full_batches:
            if not full_batch.get('caba_lines_to_reconcile'):
                continue

            caba_lines_to_reconcile = full_batch['caba_lines_to_reconcile']
            exchange_move = full_batch['exchange_move']
            for (dummy, account, repartition_line), amls_to_reconcile in caba_lines_to_reconcile.items():
                if not account.reconcile:
                    continue

                exchange_line = exchange_move.line_ids.filtered(
                    lambda l: l.account_id == account and l.tax_repartition_line_id == repartition_line
                )

                (exchange_line + amls_to_reconcile) \
                    .filtered(lambda l: not l.reconciled) \
                    .reconcile()

        all_amls._compute_amount_residual_usd()
        all_amls._reconcile_post_hook(pre_hook_data)

    def _apply_price_difference(self):
        svl_vals_list = []
        aml_vals_list = []
        if self.env.company.anglo_saxon_accounting:
            for line in self:
                line = line.with_company(line.company_id)
                po_line = line.purchase_line_id
                uom = line.product_uom_id or line.product_id.uom_id

                # Don't create value for more quantity than received
                quantity = po_line.qty_received - (po_line.qty_invoiced - line.quantity)
                quantity = max(min(line.quantity, quantity), 0)
                if float_is_zero(quantity, precision_rounding=uom.rounding):
                    continue

                layers = line._get_valued_in_moves().stock_valuation_layer_ids.filtered(
                    lambda svl: svl.product_id == line.product_id and not svl.stock_valuation_layer_id)
                if not layers:
                    continue

                new_svl_vals_list, new_aml_vals_list = line._generate_price_difference_vals(layers)
                svl_vals_list += new_svl_vals_list
                aml_vals_list += new_aml_vals_list
        return self.env['stock.valuation.layer'].sudo().create(svl_vals_list), self.env[
            'account.move.line'].sudo().create(aml_vals_list)

    def _prepare_analytic_distribution_line(self, distribution, account_ids, distribution_on_each_plan):
        """ Prepare the values used to create() an account.analytic.line upon validation of an account.move.line having
            analytic tags with analytic distribution.
        """
        self.ensure_one()
        account_field_values = {}
        decimal_precision = self.env['decimal.precision'].precision_get('Percentage Analytic')
        amount = 0
        amount_usd = 0
        for account in self.env['account.analytic.account'].browse(map(int, account_ids.split(","))).exists():
            distribution_plan = distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
            if float_compare(distribution_plan, 100, precision_digits=decimal_precision) == 0:
                amount = -self.balance * (100 - distribution_on_each_plan.get(account.root_plan_id, 0)) / 100.0
                amount_usd = -self.balance_usd * (100 - distribution_on_each_plan.get(account.root_plan_id, 0)) / 100.0
            else:
                amount = -self.balance * distribution / 100.0
                amount_usd = -self.balance_usd * distribution / 100.0
            distribution_on_each_plan[account.root_plan_id] = distribution_plan
            account_field_values[account.plan_id._column_name()] = account.id
        default_name = self.name or (self.ref or '/' + ' -- ' + (self.partner_id and self.partner_id.name or '/'))
        return {
            'name': default_name,
            'date': self.date,
            **account_field_values,
            'partner_id': self.partner_id.id,
            'unit_amount': self.quantity,
            'product_id': self.product_id and self.product_id.id or False,
            'product_uom_id': self.product_uom_id and self.product_uom_id.id or False,
            'amount': amount,
            'amount_usd': amount_usd,
            'general_account_id': self.account_id.id,
            'ref': self.ref,
            'move_line_id': self.id,
            'user_id': self.move_id.invoice_user_id.id or self._uid,
            'company_id': self.company_id.id or self.env.company.id,
            'category': 'invoice' if self.move_id.is_sale_document() else 'vendor_bill' if self.move_id.is_purchase_document() else 'other',
        }


    #SOBRE ESCRITURA - CAMBIOS PERMITEN ADAPTAR LOS DATOS A LA TASA CORRESPONDIENTES
    @api.model
    def _prepare_move_line_residual_amounts(self, aml_values, counterpart_currency, shadowed_aml_values=None,
                                            other_aml_values=None):
        """ Prepare the available residual amounts for each currency.
        :param aml_values: The values of account.move.line to consider.
        :param counterpart_currency: The currency of the opposite line this line will be reconciled with.
        :param shadowed_aml_values: A mapping aml -> dictionary to replace some original aml values to something else.
                                    This is usefull if you want to preview the reconciliation before doing some changes
                                    on amls like changing a date or an account.
        :param other_aml_values:    The other aml values to be reconciled with the current one.
        :return: A mapping currency -> dictionary containing:
            * residual: The residual amount left for this currency.
            * rate:     The rate applied regarding the company's currency.
        """

        def is_payment(aml):
            return aml.move_id.payment_id or aml.move_id.statement_line_id

        def get_odoo_rate(aml, other_aml, currency):  # HELP - Aca saca mal la cuenta
            if forced_rate := self._context.get('forced_rate_from_register_payment'):
                return forced_rate
            if other_aml and not is_payment(aml) and is_payment(other_aml):
                return get_accounting_rate(other_aml, currency)
            if aml.move_id.is_invoice(include_receipts=True):
                exchange_rate_date = aml.move_id.invoice_date
            else:
                exchange_rate_date = aml._get_reconciliation_aml_field_value('date', shadowed_aml_values)
            return currency._get_conversion_rate(aml.company_currency_id, currency, aml.company_id, exchange_rate_date)

        def get_accounting_rate(aml, currency):
            if forced_rate := self._context.get('forced_rate_from_register_payment'):
                return forced_rate
            balance = aml._get_reconciliation_aml_field_value('balance', shadowed_aml_values)
            amount_currency = aml._get_reconciliation_aml_field_value('amount_currency', shadowed_aml_values)
            if not aml.company_currency_id.is_zero(balance) and not currency.is_zero(amount_currency):
                return abs(amount_currency / balance)

        aml = aml_values['aml']
        other_aml = (other_aml_values or {}).get('aml')
        remaining_amount_curr = aml_values['amount_residual_currency']
        remaining_amount = aml_values['amount_residual']
        company_currency = aml.company_currency_id
        currency = aml._get_reconciliation_aml_field_value('currency_id', shadowed_aml_values)
        account = aml._get_reconciliation_aml_field_value('account_id', shadowed_aml_values)
        has_zero_residual = company_currency.is_zero(remaining_amount)
        has_zero_residual_currency = currency.is_zero(remaining_amount_curr)
        is_rec_pay_account = account.account_type in ('asset_receivable', 'liability_payable')

        available_residual_per_currency = {}

        if not has_zero_residual:
            available_residual_per_currency[company_currency] = {
                'residual': remaining_amount,
                'rate': 1,
            }
        if currency != company_currency and not has_zero_residual_currency:
            available_residual_per_currency[currency] = {
                'residual': remaining_amount_curr,
                'rate': get_accounting_rate(aml, currency),
            }

        if currency == company_currency \
                and is_rec_pay_account \
                and not has_zero_residual \
                and counterpart_currency != company_currency:
            rate = get_odoo_rate(aml, other_aml,counterpart_currency)
            # CAMBIO - Unico cambio el resto es estandar
            if rate >= 1: # Se usa solo cuando la tasa venga expresada 36,3662 y no en el formato 0.0023123123
                rate = 1 / rate
            #------------------------
            residual_in_foreign_curr = counterpart_currency.round(remaining_amount * rate)
            if not counterpart_currency.is_zero(residual_in_foreign_curr):
                available_residual_per_currency[counterpart_currency] = {
                    'residual': residual_in_foreign_curr,
                    'rate': rate,
                }
        elif currency == counterpart_currency \
                and currency != company_currency \
                and not has_zero_residual_currency:
            available_residual_per_currency[counterpart_currency] = {
                'residual': remaining_amount_curr,
                'rate': get_accounting_rate(aml, currency),
            }
        return available_residual_per_currency


    #SOBRE ESCRITURA - SE LLEVA ACABO YA QUE POR AJUSTES DE LA DUALIDAD ALGUNOS DIFERENCIALES
    #                - NO DEBEN GENERARSE, YA HAY UN APARTADO QUE LO HACE
    @api.model
    def _create_exchange_difference_moves(self, exchange_diff_values_list):
        """ Create the exchange difference journal entry on the current journal items.

        :param exchange_diff_values_list:   A list of values to create and reconcile the exchange differences
                                            See the '_prepare_exchange_difference_move_vals' method.
        :return: An account.move recordset.
        """
        exchange_move_values_list = []
        journal_ids = set()
        for exchange_diff_values in exchange_diff_values_list:
            move_vals = exchange_diff_values['move_values']
            exchange_move_values_list.append(move_vals)

            if not move_vals['journal_id']:
                raise UserError(_(
                    "You have to configure the 'Exchange Gain or Loss Journal' in your company settings, to manage"
                    " automatically the booking of accounting entries related to differences between exchange rates."
                ))

            journal_ids.add(move_vals['journal_id'])

        if not exchange_move_values_list:
            return self.env['account.move']

        # ==== Check the config ====
        journals = self.env['account.journal'].browse(list(journal_ids))
        for journal in journals:
            if not journal.company_id.expense_currency_exchange_account_id:
                raise UserError(_(
                    "You should configure the 'Loss Exchange Rate Account' in your company settings, to manage"
                    " automatically the booking of accounting entries related to differences between exchange rates."
                ))
            if not journal.company_id.income_currency_exchange_account_id.id:
                raise UserError(_(
                    "You should configure the 'Gain Exchange Rate Account' in your company settings, to manage"
                    " automatically the booking of accounting entries related to differences between exchange rates."
                ))

        # ==== Create the move ====
        exchange_moves = self.env['account.move'].create(exchange_move_values_list)
        # CAMBIO - LLEGA ACA SIN LINEAS PORQ EN EL CODIGO DE DUALIDAD SE LO MANDA A BORRAR - account_dual_currency
        if exchange_moves.line_ids:
            exchange_moves._post(soft=False)

            # ==== Reconcile ====
            reconciliation_plan = []
            for exchange_move, exchange_diff_values in zip(exchange_moves, exchange_diff_values_list):
                for source_line, sequence in exchange_diff_values['to_reconcile']:
                    exchange_diff_line = exchange_move.line_ids[sequence]
                    reconciliation_plan.append((source_line + exchange_diff_line))

            self \
                .with_context(no_exchange_difference=True) \
                ._reconcile_plan(reconciliation_plan)
        else:
            exchange_moves.unlink()
            return self.env['account.move']

        return exchange_moves

    # @api.model
    # def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None):
    #     """ Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
    #     as parameters, each one representing an account.move.line.
    #     :param debit_values:  The values of account.move.line to consider for a debit line.
    #     :param credit_values: The values of account.move.line to consider for a credit line.
    #     :param shadowed_aml_values: A mapping aml -> dictionary to replace some original aml values to something else.
    #                                 This is usefull if you want to preview the reconciliation before doing some changes
    #                                 on amls like changing a date or an account.
    #     :return: A dictionary:
    #         * debit_values:     None if the line has nothing left to reconcile.
    #         * credit_values:    None if the line has nothing left to reconcile.
    #         * partial_values:   The newly computed values for the partial.
    #         * exchange_values:  The values to create an exchange difference linked to this partial.
    #     """
    #     # ==== Determine the currency in which the reconciliation will be done ====
    #     # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
    #     # currency and at which rate the reconciliation will be done.
    #     res = {
    #         'debit_values': debit_values,
    #         'credit_values': credit_values,
    #     }
    #     debit_aml = debit_values['aml']
    #     credit_aml = credit_values['aml']
    #     debit_currency = debit_aml._get_reconciliation_aml_field_value('currency_id', shadowed_aml_values)
    #     credit_currency = credit_aml._get_reconciliation_aml_field_value('currency_id', shadowed_aml_values)
    #     company_currency = debit_aml.company_currency_id
    #
    #     remaining_debit_amount_curr = debit_values['amount_residual_currency']
    #     remaining_credit_amount_curr = credit_values['amount_residual_currency']
    #     remaining_debit_amount = debit_values['amount_residual']
    #     remaining_credit_amount = credit_values['amount_residual']
    #
    #     debit_available_residual_amounts = self._prepare_move_line_residual_amounts(
    #         debit_values,
    #         credit_currency,
    #         shadowed_aml_values=shadowed_aml_values,
    #         other_aml_values=credit_values,
    #     )
    #     credit_available_residual_amounts = self._prepare_move_line_residual_amounts(
    #         credit_values,
    #         debit_currency,
    #         shadowed_aml_values=shadowed_aml_values,
    #         other_aml_values=debit_values,
    #     )
    #
    #     if debit_currency != company_currency \
    #             and debit_currency in debit_available_residual_amounts \
    #             and debit_currency in credit_available_residual_amounts:
    #         recon_currency = debit_currency
    #     elif credit_currency != company_currency \
    #             and credit_currency in debit_available_residual_amounts \
    #             and credit_currency in credit_available_residual_amounts:
    #         recon_currency = credit_currency
    #     else:
    #         pass
    #     recon_currency = company_currency
    #
    #     debit_recon_values = debit_available_residual_amounts.get(recon_currency)
    #     credit_recon_values = credit_available_residual_amounts.get(recon_currency)
    #     print('debit_recon_values', debit_recon_values)
    #     print('credit_recon_values', credit_recon_values)
    #     # Check if there is something left to reconcile. Move to the next loop iteration if not.
    #     skip_reconciliation = False
    #     if not debit_recon_values:
    #         res['debit_values'] = None
    #         skip_reconciliation = True
    #     if not credit_recon_values:
    #         res['credit_values'] = None
    #         skip_reconciliation = True
    #     if skip_reconciliation:
    #         return res
    #
    #     recon_debit_amount = debit_recon_values['residual']
    #     recon_credit_amount = -credit_recon_values['residual']
    #
    #     # ==== Match both lines together and compute amounts to reconcile ====
    #
    #     # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
    #     # currency but at least one has no amount in foreign currency.
    #     # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
    #     # to reduce only the amount in company currency but not the foreign one.
    #     exchange_line_mode = \
    #         recon_currency == company_currency \
    #         and debit_currency == credit_currency \
    #         and (
    #                 not debit_available_residual_amounts.get(debit_currency)
    #                 or not credit_available_residual_amounts.get(credit_currency)
    #         )
    #
    #     # Determine which line is fully matched by the other.
    #     compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
    #     min_recon_amount = min(recon_debit_amount, recon_credit_amount)
    #     debit_fully_matched = compare_amounts <= 0
    #     credit_fully_matched = compare_amounts >= 0
    #
    #     # ==== Computation of partial amounts ====
    #     if recon_currency == company_currency:
    #         if exchange_line_mode:
    #             debit_rate = None
    #             credit_rate = None
    #         else:
    #             debit_rate = debit_available_residual_amounts.get(debit_currency, {}).get('rate')
    #             credit_rate = credit_available_residual_amounts.get(credit_currency, {}).get('rate')
    #
    #         # Compute the partial amount expressed in company currency.
    #         partial_amount = min_recon_amount
    #
    #         # Compute the partial amount expressed in foreign currency.
    #         if debit_rate:
    #             partial_debit_amount_currency = debit_currency.round(debit_rate * min_recon_amount)
    #             partial_debit_amount_currency = min(partial_debit_amount_currency, remaining_debit_amount_curr)
    #         else:
    #             partial_debit_amount_currency = 0.0
    #         if credit_rate:
    #             partial_credit_amount_currency = credit_currency.round(credit_rate * min_recon_amount)
    #             partial_credit_amount_currency = min(partial_credit_amount_currency, -remaining_credit_amount_curr)
    #         else:
    #             partial_credit_amount_currency = 0.0
    #
    #     else:
    #         # recon_currency != company_currency
    #         if exchange_line_mode:
    #             debit_rate = None
    #             credit_rate = None
    #         else:
    #             debit_rate = debit_recon_values['rate']
    #             credit_rate = credit_recon_values['rate']
    #
    #         # Compute the partial amount expressed in foreign currency.
    #         if debit_rate:
    #             partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
    #             partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
    #         else:
    #             partial_debit_amount = 0.0
    #         if credit_rate:
    #             partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
    #             partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
    #         else:
    #             partial_credit_amount = 0.0
    #         partial_amount = min(partial_debit_amount, partial_credit_amount)
    #
    #         # Compute the partial amount expressed in foreign currency.
    #         # Take care to handle the case when a line expressed in company currency is mimicking the foreign
    #         # currency of the opposite line.
    #         if debit_currency == company_currency:
    #             partial_debit_amount_currency = partial_amount
    #         else:
    #             partial_debit_amount_currency = min_recon_amount
    #         if credit_currency == company_currency:
    #             partial_credit_amount_currency = partial_amount
    #         else:
    #             partial_credit_amount_currency = min_recon_amount
    #
    #     # Computation of the partial exchange difference. You can skip this part using the
    #     # `no_exchange_difference` context key (when reconciling an exchange difference for example).
    #     if not self._context.get('no_exchange_difference'):
    #         exchange_lines_to_fix = self.env['account.move.line']
    #         amounts_list = []
    #         if recon_currency == company_currency:
    #             if debit_fully_matched:
    #                 debit_exchange_amount = remaining_debit_amount_curr - partial_debit_amount_currency
    #                 if not debit_currency.is_zero(debit_exchange_amount):
    #                     exchange_lines_to_fix += debit_aml
    #                     amounts_list.append({'amount_residual_currency': debit_exchange_amount})
    #                     remaining_debit_amount_curr -= debit_exchange_amount
    #             if credit_fully_matched:
    #                 credit_exchange_amount = remaining_credit_amount_curr + partial_credit_amount_currency
    #                 if not credit_currency.is_zero(credit_exchange_amount):
    #                     exchange_lines_to_fix += credit_aml
    #                     amounts_list.append({'amount_residual_currency': credit_exchange_amount})
    #                     remaining_credit_amount_curr += credit_exchange_amount
    #
    #         else:
    #             if debit_fully_matched:
    #                 # Create an exchange difference on the remaining amount expressed in company's currency.
    #                 debit_exchange_amount = remaining_debit_amount - partial_amount
    #                 if not company_currency.is_zero(debit_exchange_amount):
    #                     exchange_lines_to_fix += debit_aml
    #                     amounts_list.append({'amount_residual': debit_exchange_amount})
    #                     remaining_debit_amount -= debit_exchange_amount
    #                     if debit_currency == company_currency:
    #                         remaining_debit_amount_curr -= debit_exchange_amount
    #             else:
    #                 # Create an exchange difference ensuring the rate between the residual amounts expressed in
    #                 # both foreign and company's currency is still consistent regarding the rate between
    #                 # 'amount_currency' & 'balance'.
    #                 debit_exchange_amount = partial_debit_amount - partial_amount
    #                 if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
    #                     exchange_lines_to_fix += debit_aml
    #                     amounts_list.append({'amount_residual': debit_exchange_amount})
    #                     remaining_debit_amount -= debit_exchange_amount
    #                     if debit_currency == company_currency:
    #                         remaining_debit_amount_curr -= debit_exchange_amount
    #
    #             if credit_fully_matched:
    #                 # Create an exchange difference on the remaining amount expressed in company's currency.
    #                 credit_exchange_amount = remaining_credit_amount + partial_amount
    #                 if not company_currency.is_zero(credit_exchange_amount):
    #                     exchange_lines_to_fix += credit_aml
    #                     amounts_list.append({'amount_residual': credit_exchange_amount})
    #                     remaining_credit_amount -= credit_exchange_amount
    #                     if credit_currency == company_currency:
    #                         remaining_credit_amount_curr -= credit_exchange_amount
    #             else:
    #                 # Create an exchange difference ensuring the rate between the residual amounts expressed in
    #                 # both foreign and company's currency is still consistent regarding the rate between
    #                 # 'amount_currency' & 'balance'.
    #                 credit_exchange_amount = partial_amount - partial_credit_amount
    #                 if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
    #                     exchange_lines_to_fix += credit_aml
    #                     amounts_list.append({'amount_residual': credit_exchange_amount})
    #                     remaining_credit_amount -= credit_exchange_amount
    #                     if credit_currency == company_currency:
    #                         remaining_credit_amount_curr -= credit_exchange_amount
    #
    #         if exchange_lines_to_fix:
    #             res['exchange_values'] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
    #                 amounts_list,
    #                 exchange_date=max(
    #                     debit_aml._get_reconciliation_aml_field_value('date', shadowed_aml_values),
    #                     credit_aml._get_reconciliation_aml_field_value('date', shadowed_aml_values),
    #                 ),
    #             )
    #
    #     # ==== Create partials ====
    #
    #     remaining_debit_amount -= partial_amount
    #     remaining_credit_amount += partial_amount
    #     remaining_debit_amount_curr -= partial_debit_amount_currency
    #     remaining_credit_amount_curr += partial_credit_amount_currency
    #
    #     res['partial_values'] = {
    #         'amount': partial_amount,
    #         'debit_amount_currency': partial_debit_amount_currency,
    #         'credit_amount_currency': partial_credit_amount_currency,
    #         'debit_move_id': debit_aml.id,
    #         'credit_move_id': credit_aml.id,
    #     }
    #
    #     debit_values['amount_residual'] = remaining_debit_amount
    #     debit_values['amount_residual_currency'] = remaining_debit_amount_curr
    #     credit_values['amount_residual'] = remaining_credit_amount
    #     credit_values['amount_residual_currency'] = remaining_credit_amount_curr
    #
    #     if debit_fully_matched:
    #         res['debit_values'] = None
    #     if credit_fully_matched:
    #         res['credit_values'] = None
    #     return res
    #
    #     # nuevo método para reconciliar en v17
    #     @api.model
    #     def _reconcile_plan(self, reconciliation_plan):
    #         """ Reconcile the amls following the reconciliation plan.
    #         The plan passed as parameter is a list of either a recordset of amls, either another plan.
    #
    #         For example:
    #         [account.move.line(1, 2), account.move.line(3, 4)] means:
    #         - account.move.line(1, 2) will be reconciled first.
    #         - account.move.line(3, 4) will be reconciled after.
    #
    #         [[account.move.line(1, 2), account.move.line(3, 4)]] means:
    #         - account.move.line(1, 2) will be reconciled first.
    #         - account.move.line(3, 4) will be reconciled after.
    #         - account.move.line(1, 2, 3, 4).filtered(lambda x: not x.reconciled) will be reconciled at the end.
    #
    #         :param reconciliation_plan: A list of reconciliation to perform.
    #         """
    #         # Parameter allowing to disable the exchange journal entries on partials.
    #         disable_partial_exchange_diff = bool(
    #             self.env['ir.config_parameter'].sudo().get_param('account.disable_partial_exchange_diff'))
    #
    #         # ==== Prepare the reconciliation ====
    #         # Batch the amls all together to know what should be reconciled and when.
    #         plan_list, all_amls = self._optimize_reconciliation_plan(reconciliation_plan)
    #         print('plan_list', plan_list)
    #         print('all_amls', all_amls)
    #         print('reconciliation_plan', reconciliation_plan)
    #         # ==== Prefetch the fields all at once to speedup the reconciliation ====
    #         # All of those fields will be cached by the orm. Since the amls are split into multiple batches, the orm is not
    #         # able to prefetch the data for all of them at once. For that reason, we force the orm to populate the cache
    #         # before doing anything.
    #         all_amls.move_id
    #         all_amls.matched_debit_ids
    #         all_amls.matched_credit_ids
    #
    #         # ==== Track the invoice's state to call the hook when they become paid ====
    #         pre_hook_data = all_amls._reconcile_pre_hook()
    #
    #         # ==== Collect amls data ====
    #         # All residual amounts are collected and updated until the creation of partials in batch.
    #         # This is done that way to minimize the orm time for fields invalidation/mark as recompute and
    #         # recomputation.
    #         aml_values_map = {
    #             aml: {
    #                 'aml': aml,
    #                 'amount_residual': aml.amount_residual,
    #                 'amount_residual_usd': aml.amount_residual_usd,
    #                 'amount_residual_currency': aml.amount_residual_currency,
    #             }
    #             for aml in all_amls
    #         }
    #         print('aml_values_map', aml_values_map)
    #         # ==== Prepare the partials ====
    #         partials_values_list = []
    #         exchange_diff_values_list = []
    #         exchange_diff_partial_index = []
    #         all_plan_results = []
    #         partial_index = 0
    #         for plan in plan_list:
    #             plan_results = self \
    #                 .with_context(
    #                 no_exchange_difference=self._context.get('no_exchange_difference') or disable_partial_exchange_diff) \
    #                 ._prepare_reconciliation_plan(plan, aml_values_map)
    #             all_plan_results.append(plan_results)
    #             for results in plan_results:
    #                 # actualizar amount en partial_values agregar el menor de los dos valores
    #                 partials_values_list.append(results['partial_values'])
    #                 # if results.get('exchange_values') and results['exchange_values']['move_values']['line_ids']:
    #                 #     exchange_diff_values_list.append(results['exchange_values'])
    #                 #     exchange_diff_partial_index.append(partial_index)
    #                 #     partial_index += 1
    #
    #         # ==== Create the partials ====
    #         # Link the newly created partials to the plan. There are needed later for caba exchange entries.
    #         partials = self.env['account.partial.reconcile'].create(partials_values_list)
    #         for parcial in partials:
    #             amount_usd = min(abs(parcial.debit_move_id.amount_residual_usd),
    #                              abs(parcial.credit_move_id.amount_residual_usd))
    #             parcial.write({'amount_usd': abs(amount_usd)})
    #         start_range = 0
    #         for plan_results, plan in zip(all_plan_results, plan_list):
    #             size = len(plan_results)
    #             plan['partials'] = partials[start_range:start_range + size]
    #             start_range += size
    #
    #         # ==== Create the partial exchange journal entries ====
    #         exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
    #         for index, exchange_move in zip(exchange_diff_partial_index, exchange_moves):
    #             partials[index].exchange_move_id = exchange_move
    #
    #         # ==== Create entries for cash basis taxes ====
    #         def is_cash_basis_needed(account):
    #             return account.company_id.tax_exigibility \
    #                 and account.account_type in ('asset_receivable', 'liability_payable')
    #
    #         if not self._context.get('move_reverse_cancel') and not self._context.get('no_cash_basis'):
    #             for plan in plan_list:
    #                 if is_cash_basis_needed(plan['amls'].account_id):
    #                     plan['partials']._create_tax_cash_basis_moves()
    #
    #         # ==== Prepare full reconcile creation ====
    #         # First, we need to find all sub-set of amls that are candidates for a full.
    #
    #         def is_line_reconciled(aml, has_multiple_currencies):
    #             # Check if the journal item passed as parameter is now fully reconciled.
    #             if aml.reconciled:
    #                 return True
    #             if not aml.matched_debit_ids and not aml.matched_credit_ids:
    #                 # Suppose a journal item having balance = 0 but an amount_currency like an exchange difference.
    #                 return False
    #             if has_multiple_currencies:
    #                 return aml.company_currency_id.is_zero(aml.amount_residual)
    #             else:
    #                 return aml.currency_id.is_zero(aml.amount_residual_currency)
    #
    #         full_batches = []
    #         all_aml_ids = set()
    #         for plan in plan_list:
    #             for aml in plan['amls']:
    #                 if 'full_batch_index' in aml_values_map[aml]:
    #                     continue
    #
    #                 involved_amls = plan['amls']._all_reconciled_lines()
    #                 all_aml_ids.update(involved_amls.ids)
    #                 full_batch_index = len(full_batches)
    #                 has_multiple_currencies = len(involved_amls.currency_id) > 1
    #                 is_fully_reconciled = all(
    #                     is_line_reconciled(involved_aml, has_multiple_currencies)
    #                     for involved_aml in involved_amls
    #                 )
    #                 full_batches.append({
    #                     'amls': involved_amls,
    #                     'is_fully_reconciled': is_fully_reconciled,
    #                 })
    #                 for involved_aml in involved_amls:
    #                     if aml_values_map.get(involved_aml):
    #                         aml_values_map[involved_aml]['full_batch_index'] = full_batch_index
    #
    #         # ==== Prefetch the fields all at once to speedup the reconciliation ====
    #         # Again, we do the same optimization for the prefetching. We need to do it again since most of the values have
    #         # been invalidated with the creation of the account.partial.reconcile records.
    #         all_amls = self.browse(list(all_aml_ids))
    #         all_amls.move_id
    #         all_amls.matched_debit_ids
    #         all_amls.matched_credit_ids
    #
    #         # ==== Prepare the full exchange journal entries ====
    #         # This part could be bypassed using the 'no_exchange_difference' key inside the context. This is useful
    #         # when importing a full accounting including the reconciliation like Winbooks.
    #
    #         exchange_diff_values_list = []
    #         exchange_diff_full_batch_index = []
    #         if not self._context.get('no_exchange_difference'):
    #             for fulL_batch_index, full_batch in enumerate(full_batches):
    #                 involved_amls = full_batch['amls']
    #                 if not full_batch['is_fully_reconciled']:
    #                     continue
    #
    #                 # In normal cases, the exchange differences are already generated by the partial at this point meaning
    #                 # there is no journal item left with a zero amount residual in one currency but not in the other.
    #                 # However, after a migration coming from an older version with an older partial reconciliation or due to
    #                 # some rounding issues (when dealing with different decimal places for example), we could need an extra
    #                 # exchange difference journal entry to handle them.
    #                 exchange_lines_to_fix = self.env['account.move.line']
    #                 amounts_list = []
    #                 exchange_max_date = date.min
    #                 for aml in involved_amls:
    #                     if not aml.company_currency_id.is_zero(aml.amount_residual):
    #                         exchange_lines_to_fix += aml
    #                         amounts_list.append({'amount_residual': aml.amount_residual})
    #                     elif not aml.currency_id.is_zero(aml.amount_residual_currency):
    #                         exchange_lines_to_fix += aml
    #                         amounts_list.append({'amount_residual_currency': aml.amount_residual_currency})
    #                     exchange_max_date = max(exchange_max_date, aml.date)
    #                 exchange_diff_values = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
    #                     amounts_list,
    #                     company=involved_amls.company_id,
    #                     exchange_date=exchange_max_date,
    #                 )
    #
    #                 # Exchange difference for cash basis entries.
    #                 # If we are fully reversing the entry, no need to fix anything since the journal entry
    #                 # is exactly the mirror of the source journal entry.
    #                 caba_lines_to_reconcile = None
    #                 if is_cash_basis_needed(involved_amls.account_id) and not self._context.get('move_reverse_cancel'):
    #                     caba_lines_to_reconcile = involved_amls._add_exchange_difference_cash_basis_vals(
    #                         exchange_diff_values)
    #
    #                 # Prepare the exchange difference.
    #                 if exchange_diff_values['move_values']['line_ids']:
    #                     exchange_diff_full_batch_index.append(fulL_batch_index)
    #                     exchange_diff_values_list.append(exchange_diff_values)
    #                     full_batch['caba_lines_to_reconcile'] = caba_lines_to_reconcile
    #
    #         # ==== Create the full exchange journal entries ====
    #         exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
    #         for fulL_batch_index, exchange_move in zip(exchange_diff_full_batch_index, exchange_moves):
    #             full_batch = full_batches[full_batch_index]
    #             amls = full_batch['amls']
    #             full_batch['exchange_move'] = exchange_move
    #             exchange_move_lines = exchange_move.line_ids.filtered(lambda line: line.account_id == amls.account_id)
    #             full_batch['amls'] |= exchange_move_lines
    #
    #         # ==== Create the full reconcile ====
    #         # Note we are using Command.link and not Command.set because Command.set is triggering an unlink that is
    #         # slowing down the assignation of the co-fields. Indeed, unlink is forcing a flush.
    #         full_reconcile_values_list = []
    #         full_reconcile_fulL_batch_index = []
    #         for fulL_batch_index, full_batch in enumerate(full_batches):
    #             amls = full_batch['amls']
    #             involved_partials = amls.matched_debit_ids + amls.matched_credit_ids
    #             if full_batch['is_fully_reconciled']:
    #                 full_reconcile_values_list.append({
    #                     'exchange_move_id': full_batch.get('exchange_move') and full_batch['exchange_move'].id,
    #                     'partial_reconcile_ids': [Command.link(partial.id) for partial in involved_partials],
    #                     'reconciled_line_ids': [Command.link(aml.id) for aml in amls],
    #                 })
    #                 full_reconcile_fulL_batch_index.append(fulL_batch_index)
    #
    #         self.env['account.full.reconcile'] \
    #             .with_context(
    #             skip_invoice_sync=True,
    #             skip_invoice_line_sync=True,
    #             skip_account_move_synchronization=True,
    #             check_move_validity=False,
    #         ) \
    #             .create(full_reconcile_values_list)
    #
    #         # === Cash basis rounding autoreconciliation ===
    #         # In case a cash basis rounding difference line got created for the transition account, we reconcile it with the corresponding lines
    #         # on the cash basis moves (so that it reaches full reconciliation and creates an exchange difference entry for this account as well)
    #         for fulL_batch_index, full_batch in enumerate(full_batches):
    #             if not full_batch.get('caba_lines_to_reconcile'):
    #                 continue
    #
    #             caba_lines_to_reconcile = full_batch['caba_lines_to_reconcile']
    #             exchange_move = full_batch['exchange_move']
    #             for (dummy, account, repartition_line), amls_to_reconcile in caba_lines_to_reconcile.items():
    #                 if not account.reconcile:
    #                     continue
    #
    #                 exchange_line = exchange_move.line_ids.filtered(
    #                     lambda l: l.account_id == account and l.tax_repartition_line_id == repartition_line
    #                 )
    #
    #                 (exchange_line + amls_to_reconcile) \
    #                     .filtered(lambda l: not l.reconciled) \
    #                     .reconcile()
    #
    #         all_amls._compute_amount_residual_usd()
    #         all_amls._reconcile_post_hook(pre_hook_data)
    #


