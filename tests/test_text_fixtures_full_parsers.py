import json
import unittest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class TestTextFixturesFullParsers(unittest.TestCase):
    def test_mastercard_text_fixture_parses_statement_transactions_and_warnings(self):
        from hsbc_parser.parsers.mastercard import HSBCMastercardParser

        page = _load_fixture("mastercard_full_page.txt")
        p = HSBCMastercardParser("HSBC MasterCard fixture.pdf", pages=[page])
        p.parse()

        self.assertIsNotNone(p.statement)
        self.assertEqual(p.statement.origen, "mastercard")
        self.assertEqual(p.statement.fecha_hasta, "2024-05-30")
        self.assertEqual(p.statement.fecha_desde, "2024-05-03")
        self.assertAlmostEqual(p.statement.saldo_anterior_ars or 0.0, 1000.0, places=2)
        self.assertAlmostEqual(p.statement.saldo_actual_ars or 0.0, 1180.50, places=2)

        self.assertGreaterEqual(len(p.transactions), 4)
        descs = [t.descripcion for t in p.transactions]
        self.assertIn("GIESSO ARCOS", descs)
        self.assertFalse(any("ABONANDO EL PAGO" in (d or "").upper() for d in descs))
        self.assertFalse(any("CFT" in (d or "").upper() for d in descs))
        self.assertFalse(any("ESTAS MISMAS TASAS" in (d or "").upper() for d in descs))
        self.assertFalse(any("SHOULD_NOT_PARSE_AFTER_TAIL" in (d or "").upper() for d in descs))

        by_op = {t.operation_id: t for t in p.transactions if t.operation_id}
        self.assertIn("04252", by_op)
        self.assertEqual(by_op["04252"].fecha, "2024-05-10")
        self.assertEqual(by_op["04252"].moneda, "ARS")
        self.assertAlmostEqual(by_op["04252"].importe, 200.0, places=2)

        self.assertIn("07777", by_op)
        self.assertEqual(by_op["07777"].installment_number, 7)
        self.assertEqual(by_op["07777"].installment_total, 18)

        # DEV line split across lines should be included as an ARS transaction for reconciliation.
        self.assertTrue(any(t.descripcion.startswith("DEV ") and t.importe < 0 for t in p.transactions))

        # Balance reconciliation should produce an INFO warning within tolerance for the fixture.
        self.assertTrue(any(w["code"] == "BALANCE_SUM_WITHIN_TOLERANCE" for w in p.warnings), p.warnings)

    def test_visa_text_fixture_parses_statement_transactions_and_warnings(self):
        from hsbc_parser.parsers.visa import HSBCVisaParser

        page = _load_fixture("visa_full_page.txt")
        p = HSBCVisaParser("HSBC Visa fixture.pdf", pages=[page])
        p.parse()

        self.assertIsNotNone(p.statement)
        self.assertEqual(p.statement.origen, "visa")
        self.assertEqual(p.statement.fecha_hasta, "2024-01-25")
        self.assertEqual(p.statement.fecha_desde, "2023-12-22")

        by_desc = {t.descripcion: t for t in p.transactions}
        self.assertIn("SU PAGO EN PESOS", by_desc)
        self.assertAlmostEqual(by_desc["SU PAGO EN PESOS"].importe, -100.0, places=2)

        self.assertIn("MERCPAGO*TIENDAEJEMPLO", by_desc)
        tx = by_desc["MERCPAGO*TIENDAEJEMPLO"]
        self.assertEqual(tx.operation_id, "350257*")
        self.assertEqual(tx.installment_number, 5)
        self.assertEqual(tx.installment_total, 6)

        # Financing offer should never be parsed as a transaction
        self.assertFalse(any("CUOTAS" in (t.descripcion or "").upper() for t in p.transactions))
        self.assertFalse(any("SHOULD_NOT_PARSE_AFTER_TAIL" in (t.descripcion or "").upper() for t in p.transactions))

        # Balance reconciliation should produce an INFO warning within tolerance for the fixture.
        self.assertTrue(any(w["code"] == "BALANCE_SUM_WITHIN_TOLERANCE" for w in p.warnings), p.warnings)

    def test_cuenta_text_fixture_parses_statement_transactions_and_warnings(self):
        from hsbc_parser.parsers.cuenta import HSBCCajaAhorroParser

        page = _load_fixture("cuenta_full_page.txt")
        p = HSBCCajaAhorroParser("HSBC Cuenta fixture.pdf", pages=[page])
        p.parse()

        self.assertIsNotNone(p.statement)
        self.assertEqual(p.statement.origen, "cuenta")
        self.assertEqual(p.statement.fecha_desde, "2024-01-01")
        self.assertEqual(p.statement.fecha_hasta, "2024-01-31")

        self.assertEqual(len(p.transactions), 3)
        self.assertEqual(p.transactions[0].fecha, "2024-01-09")
        self.assertAlmostEqual(p.transactions[0].importe, -100.0, places=2)
        self.assertEqual(p.transactions[1].fecha, "2024-01-09")
        self.assertAlmostEqual(p.transactions[1].importe, 0.06, places=2)
        self.assertEqual(p.transactions[2].fecha, "2024-01-10")
        self.assertAlmostEqual(p.transactions[2].importe, 50.0, places=2)

        # The fixture purposely makes SALDO FINAL differ from the last running balance.
        self.assertTrue(any(w["code"] == "BALANCE_FINAL_MISMATCH" for w in p.warnings), p.warnings)
        self.assertTrue(any(w["code"] == "BALANCE_SUM_WITHIN_TOLERANCE" for w in p.warnings), p.warnings)

    def test_export_csv_includes_statements_transactions_warnings(self):
        from hsbc_parser.export import export_csv
        from hsbc_parser.parsers.mastercard import HSBCMastercardParser
        from hsbc_parser.parsers.visa import HSBCVisaParser
        from hsbc_parser.parsers.cuenta import HSBCCajaAhorroParser

        parsers = [
            HSBCMastercardParser("HSBC MasterCard fixture.pdf", pages=[_load_fixture("mastercard_full_page.txt")]),
            HSBCVisaParser("HSBC Visa fixture.pdf", pages=[_load_fixture("visa_full_page.txt")]),
            HSBCCajaAhorroParser("HSBC Cuenta fixture.pdf", pages=[_load_fixture("cuenta_full_page.txt")]),
        ]
        for p in parsers:
            p.parse()

        out_dir = Path("data/output/unittest_text_fixtures")
        df_s, df_t, df_w = export_csv(parsers, out_dir)

        self.assertEqual(len(df_s), 3)
        self.assertGreaterEqual(len(df_t), 1)
        self.assertGreaterEqual(len(df_w), 1)

        # warnings.csv contexts must be json strings for dict/list contexts
        for ctx in df_w["context"].dropna().tolist():
            if isinstance(ctx, str) and ctx.startswith("{"):
                json.loads(ctx)


if __name__ == "__main__":
    unittest.main()
