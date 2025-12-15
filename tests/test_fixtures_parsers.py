import unittest


class TestFixtureParsing(unittest.TestCase):
    def test_parse_amount_formats(self):
        from hsbc_parser.parsers.utils import parse_amount

        self.assertEqual(parse_amount("1.234,56"), 1234.56)
        self.assertEqual(parse_amount("1,234.56"), 1234.56)
        self.assertEqual(parse_amount("0,06"), 0.06)
        self.assertEqual(parse_amount(".06"), 0.06)
        self.assertEqual(parse_amount("425.471,35-"), -425471.35)

    def test_visa_fixture_reconciles_and_parses_edge_cases(self):
        from hsbc_parser.parsers.visa import HSBCVisaParser

        pages = [
            "\n".join(
                [
                    "SALDO ANTERIOR 1.000,00 0,00",
                    "SALDO ACTUAL $ 1.548,06 U$S 0,00",
                    "CIERRE ACTUAL 25 Ene 24",
                    "VENCIMIENTO ACTUAL 02 Feb 24",
                    "PAGO MINIMO $ 30.308,00",
                    "CIERRE ANTERIOR 21 Dic 23",
                    "FECHA COMPROBANTE DETALLE DE TRANSACCION PESOS DOLARES",
                    "SALDO ANTERIOR 1.000,00 0,00",
                    "27.12.23 SU PAGO EN PESOS 100,00- 0,00",
                    "Sin IVA: 3 cuotas 159,29%/ 6 cuotas 159,29%/12 cuotas 159,29%/24 cuotas 159,29%",
                    # date glued to the next column (space missing after date)
                    "08.09.23350257* MERCPAGO*TIENDAEJEMPLO C.05/06 200,00-",
                    # fee lines with parentheses containing base amounts; the last amount is the actual charge
                    "25.01.24 DB.IMPUESTO PAIS 8%( 123,45 ) 9,88 0,00",
                    "25.01.24 IIBB PERCEP-CABA 2,00%( 123,45) 17,38 0,00",
                    "25.01.24 IVA RG 4240 21%( 123,45) 182,49 0,00",
                    # a positive purchase
                    "23.12.23 003445* WWW.EJEMPLO.COM 638,31",
                ]
            )
        ]

        p = HSBCVisaParser("fixture.pdf", pages=pages)
        p.parse()

        self.assertTrue(p.transactions)
        self.assertFalse(p.warnings, f"Expected no warnings, got: {p.warnings}")
        self.assertEqual(p.statement.fecha_desde, "2023-12-22")
        self.assertEqual(p.statement.fecha_hasta, "2024-01-25")
        self.assertAlmostEqual(p.statement.saldo_anterior_ars or 0.0, 1000.0, places=2)
        self.assertAlmostEqual(p.statement.saldo_actual_ars or 0.0, 1548.06, places=2)

        # Key edge cases
        by_desc = {t.descripcion: t for t in p.transactions}
        self.assertAlmostEqual(by_desc["SU PAGO EN PESOS"].importe, -100.0, places=2)
        self.assertEqual(by_desc["SU PAGO EN PESOS"].fecha, "2023-12-27")
        self.assertFalse(by_desc["SU PAGO EN PESOS"].descripcion.startswith("27.12.23"))

        self.assertAlmostEqual(by_desc["DB.IMPUESTO PAIS 8%( 123,45 )"].importe, 9.88, places=2)

        # glued-date line should be parsed as negative and have installments extracted
        glued = by_desc["MERCPAGO*TIENDAEJEMPLO"]
        self.assertAlmostEqual(glued.importe, -200.0, places=2)
        self.assertEqual(glued.installment_number, 5)
        self.assertEqual(glued.installment_total, 6)
        self.assertEqual(glued.operation_id, "350257")

        # Financing offer should never be parsed as a transaction
        self.assertFalse(any("CUOTAS" in (t.descripcion or "").upper() for t in p.transactions))

    def test_mastercard_dual_currency_amounts(self):
        from hsbc_parser.parsers.mastercard import HSBCMastercardParser

        pages = [
            "\n".join(
                [
                    "Estado de cuenta al: 25-Ene-24",
                    "Cierre Anterior: 02-Ene-24",
                    "SALDO ANTERIOR 1.000,00 5,00",
                    "SALDO ACTUAL 1.100,00 4,50",
                    "Pago Mínimo : $ 54.270,00",
                    "01-Ene-24 COMPRA EJEMPLO 200,00 0,00",
                    "02-Ene-24 PAGO CAJERO/INTERNET -150,00 -0,50",
                    "03-Ene-24 COMPRA EJEMPLO 50,00 0,00",
                ]
            )
        ]

        p = HSBCMastercardParser("fixture.pdf", pages=pages)
        p.parse()
        self.assertTrue(p.transactions)
        self.assertFalse([w for w in p.warnings if w["level"] == "ERROR"])
        self.assertEqual(p.statement.fecha_desde, "2024-01-03")
        self.assertEqual(p.statement.fecha_hasta, "2024-01-25")
        self.assertAlmostEqual(p.statement.saldo_anterior_ars or 0.0, 1000.0, places=2)
        self.assertAlmostEqual(p.statement.saldo_actual_ars or 0.0, 1100.0, places=2)

        sum_ars = round(sum(t.importe for t in p.transactions if t.moneda == "ARS"), 2)
        sum_usd = round(sum(t.importe for t in p.transactions if t.moneda == "USD"), 2)
        self.assertEqual(sum_ars, 100.0)
        self.assertEqual(sum_usd, -0.5)

    def test_cuenta_running_balance_infers_signs_and_continuations(self):
        from hsbc_parser.parsers.cuenta import HSBCCajaAhorroParser

        pages = [
            "\n".join(
                [
                    "EXTRACTO DEL 01/01/2024 AL 31/01/2024",
                    "CAJA DE AHORRO EN U$S NRO. 000-0-00000-0",
                    "- DETALLE DE OPERACIONES -",
                    "FECHA REFERENCIA NRO DEBITO CREDITO SALDO",
                    "- SALDO ANTERIOR 1,000.00",
                    "09-ENE - EXT. POR CAJA 00001 100.00 900.00",
                    # continuation line without date
                    "- AJUSTE 00000 .06 900.06",
                    "10-ENE - DEPOSITO 00002 0.00 50.00 950.06",
                    "- SALDO FINAL 950.06",
                ]
            )
        ]

        p = HSBCCajaAhorroParser("fixture.pdf", pages=pages)
        p.parse()
        self.assertTrue(p.transactions)
        self.assertFalse(p.warnings, f"Expected no warnings, got: {p.warnings}")
        self.assertEqual(p.statement.fecha_desde, "2024-01-01")
        self.assertEqual(p.statement.fecha_hasta, "2024-01-31")

        # 09-ENE is a debit (balance goes down)
        self.assertAlmostEqual(p.transactions[0].importe, -100.0, places=2)
        # continuation line uses the previous date
        self.assertEqual(p.transactions[1].fecha, "2024-01-09")
        self.assertAlmostEqual(p.transactions[1].importe, 0.06, places=2)
        self.assertEqual(p.transactions[0].descripcion, "EXT. POR CAJA")
        self.assertEqual(p.transactions[0].operation_id, "00001")


if __name__ == "__main__":
    unittest.main()
