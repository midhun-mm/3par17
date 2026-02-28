# -*- coding: utf-8 -*-

from odoo import models, _, fields


class AccountMoveReversalInherit(models.TransientModel):
    _inherit = 'account.move.reversal'

    nro_ctrl = fields.Char(
        'Número de Control', size=32,
        help="Número utilizado para gestionar facturas preimpresas, por ley "
             "Necesito poner aquí este número para poder declarar"
             "Informes fiscales correctamente.", store=True)
    supplier_invoice_number = fields.Char(
        string='Número de factura del proveedor', size=64,
        store=True)

    # def reverse_moves(self):
    #     moves = self.env['account.move'].browse(self.env.context['active_ids']) if self.env.context.get('active_model') == 'account.move' else self.move_id
    #
    #     # Create default values.
    #     default_values_list = []
    #     for move in moves:
    #         default_values_list.append(self._prepare_default_reversal(move))
    #
    #
    #     batches = [
    #         [self.env['account.move'], [], True],   # Moves to be cancelled by the reverses.
    #         [self.env['account.move'], [], False],  # Others.
    #     ]
    #     for move, default_vals in zip(moves, default_values_list):
    #         is_auto_post = bool(default_vals.get('auto_post'))
    #         is_cancel_needed = not is_auto_post and self.refund_method in ('cancel', 'modify')
    #         batch_index = 0 if is_cancel_needed else 1
    #         batches[batch_index][0] |= move
    #         batches[batch_index][1].append(default_vals)
    #
    #     # Handle reverse method.
    #     moves_to_redirect = self.env['account.move']
    #     for moves, default_values_list, is_cancel_needed in batches:
    #         if default_values_list:
    #             default_values_list[0]['supplier_invoice_number'] = self.supplier_invoice_number
    #             default_values_list[0]['nro_ctrl'] = self.nro_ctrl
    #         new_moves = moves._reverse_moves(default_values_list, cancel=is_cancel_needed)
    #         if new_moves.state != 'draft':
    #             new_moves.already_posted_iva()
    #
    #
    #         # if new_moves:
    #         #     new_moves.supplier_invoice_number_aux.name = new_moves.supplier_invoice_number
    #
    #         if self.refund_method == 'modify':
    #             moves_vals_list = []
    #             for move in moves.with_context(include_business_fields=True):
    #                 moves_vals_list.append(move.copy_data({'date': self.date or move.date})[0])
    #             new_moves = self.env['account.move'].create(moves_vals_list)
    #
    #         moves_to_redirect |= new_moves
    #
    #     # Create action.
    #     action = {
    #         'name': _('Reverse Moves'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.move',
    #     }
    #     if len(moves_to_redirect) == 1:
    #         action.update({
    #             'view_mode': 'form',
    #             'res_id': moves_to_redirect.id,
    #         })
    #     else:
    #         action.update({
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', moves_to_redirect.ids)],
    #         })
    #     return action

    def reverse_moves(self, is_modify=False):
        self.ensure_one()
        moves = self.move_ids

        # Create default values.
        default_values_list = []
        for move in moves:
            default_values_list.append(self._prepare_default_reversal(move))

        batches = [
            [self.env['account.move'], [], True],   # Moves to be cancelled by the reverses.
            [self.env['account.move'], [], False],  # Others.
        ]
        for move, default_vals in zip(moves, default_values_list):
            is_auto_post = default_vals.get('auto_post') != 'no'
            is_cancel_needed = not is_auto_post and is_modify
            batch_index = 0 if is_cancel_needed else 1
            batches[batch_index][0] |= move
            batches[batch_index][1].append(default_vals)

        # Handle reverse method.
        moves_to_redirect = self.env['account.move']
        for moves, default_values_list, is_cancel_needed in batches:
            if default_values_list:
                default_values_list[0]['supplier_invoice_number'] = self.supplier_invoice_number
                default_values_list[0]['nro_ctrl'] = self.nro_ctrl
            new_moves = moves._reverse_moves(default_values_list, cancel=is_cancel_needed)
            moves._message_log_batch(
                bodies={move.id: _('This entry has been %s', reverse._get_html_link(title=_("reversed"))) for move, reverse in zip(moves, new_moves)}
            )

            if is_modify:
                moves_vals_list = []
                for move in moves.with_context(include_business_fields=True):
                    data = move.copy_data({'date': self.date})[0]
                    data['line_ids'] = [line for line in data['line_ids'] if line[2]['display_type'] == 'product']
                    moves_vals_list.append(data)
                new_moves = self.env['account.move'].create(moves_vals_list)

            moves_to_redirect |= new_moves

        self.new_move_ids = moves_to_redirect

        # Create action.
        action = {
            'name': _('Reverse Moves'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
        }
        if len(moves_to_redirect) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': moves_to_redirect.id,
                'context': {'default_move_type':  moves_to_redirect.move_type},
            })
        else:
            action.update({
                'view_mode': 'tree,form',
                'domain': [('id', 'in', moves_to_redirect.ids)],
            })
            if len(set(moves_to_redirect.mapped('move_type'))) == 1:
                action['context'] = {'default_move_type':  moves_to_redirect.mapped('move_type').pop()}
        return action
