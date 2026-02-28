# coding: utf-8
from odoo import fields, models, api
import requests
import json

class AccountWhMunicipalRates(models.Model):
    _name = 'account.wh.municipal.rates'
    _description = 'Conceptos de retención municipal'
    _rec_name = 'code'
    _rec_names_search = ['code', 'name', 'ordenanza']
    _order = 'code asc'

    code = fields.Char('Código', required=True)
    name = fields.Char(string='Nombre', required=True)
    description = fields.Text('Descripción')
    rate = fields.Float('Alícuota %', required=True)
    ordenanza = fields.Char('Ordenanza', )
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"({rec.code} {rec.ordenanza or ''}) {rec.name}"

    def obtener_data(self):
        # hacer un llamado a la url https://www.paez.net.ve/appweb/Consultas_publicas/contribuyente/4/%s/adminATR/b33ac90146
        # incrementado la variable i en 1 hasta 10000 y obtener el json como respuesta
        headers = {
            'Content-Type': 'application/json'
        }
        state_id = self.env.ref('l10n_ve_full.est_ve_POR').id
        municipality_id = self.env.ref('l10n_ve_full.mun_ve_POR_PAE').id
        for i in range(1, 10000):
            url = "https://www.paez.net.ve/appweb/Consultas_publicas/contribuyente/4/%s/adminATR/b33ac90146" % i
            response = requests.request("GET", url, headers=headers, data={})

            if response.text:
                data = json.loads(response.text)
                if data.get('data'):
                    municipal_rate_ids = []
                    print(f"Registro {i} cargado")
                    if 'rubros' in data['data']:
                        for rubros in data['data']['rubros'][0]:
                            # print(rubros)
                            if 'codigo' in rubros:
                                code = rubros['codigo']
                                ordenanza = rubros['ordenanza']
                                if not code == None:
                                    codes = self.env['account.wh.municipal.rates'].search(
                                        [('code', '=', code), ('ordenanza', '=', ordenanza)])
                                    if not codes:
                                        id_create = self.env['account.wh.municipal.rates'].create({
                                            'code': rubros['codigo'],
                                            'name': rubros['nombre'],
                                            'description': rubros['nombre'],
                                            'rate': rubros['aliquot'],
                                            'state_id': state_id,
                                            'ordenanza': rubros['ordenanza'],
                                            'municipality_id': municipality_id
                                        })
                                        municipal_rate_ids.append(id_create.id)
                                    else:
                                        # if 'ordenanza' in rubros:
                                        #     if rubros['ordenanza'] == 'Ordenanza 2023':
                                        #         #print(f"Rubro {rubros['nombre']} con Ordenanza 2023")
                                        #         codes.write({
                                        #             'rate': rubros['aliquot'],
                                        #             'name': rubros['nombre'],
                                        #             'description': rubros['nombre'],
                                        #         })
                                        municipal_rate_ids.append(codes.id)
                    # buscar la licencia y realizar nueva consulta a la url https://www.paez.net.ve/appweb/Consultas_publicas/contribuyente/3/%s/adminATR/b33ac90146
                    # con el nro_cuenta obtenido
                    # for l in data['data']['licencia']:
                    #     nro_cuenta = l['nro_cuenta']
                    #     print(f"Consultando Licencia {nro_cuenta}:")
                    #     url = "https://www.paez.net.ve/appweb/Consultas_publicas/contribuyente/3/%s/adminATR/b33ac90146" % nro_cuenta
                    #     response = requests.request("GET", url, headers=headers, data={})
                    #     if response.text:
                    #         data = json.loads(response.text)
                    #         if data.get('data'):
                    #             if 'contribuyente' in data['data']:
                    #                 contribuyente = data['data']['contribuyente'][0]
                    #                 address = ''
                    #                 razon_social = ''
                    #                 rif = ''
                    #                 if 'direccion' in contribuyente:
                    #                     address = contribuyente['direccion']
                    #                 if 'razon_social' in contribuyente:
                    #                     razon_social = contribuyente['razon_social']
                    #                 if 'rif' in contribuyente:
                    #                     rif = contribuyente['rif']
                    #                 #print(f"Rif: {rif} - Razon Social: {razon_social} - Address: {address}")
                    #                 partner = self.env['res.partner'].search([('rif', '=', rif)])
                    #                 if not partner:
                    #                     partner = self.env['res.partner'].create({
                    #                         'company_type': 'company',
                    #                         'name': razon_social,
                    #                         'vat': rif,
                    #                         'rif': rif,
                    #                         'street': address,
                    #                         'state_id': state_id,
                    #                         'municipality_id': municipality_id,
                    #                         'country_id': self.company_id.country_id.id,
                    #                         'licencia_municipal': nro_cuenta,
                    #                         'municipal_rate_id': [(6, 0, municipal_rate_ids)]
                    #                     })


                else:
                    print(f"Error en el registro {i}")
            # hacer commit
            self._cr.commit()

