import os
import unittest
from pathlib import Path

try:
    from hsbc_parser.dispatcher import parse_pdf
    from hsbc_parser.export import export_csv
except ModuleNotFoundError:
    parse_pdf = None
    export_csv = None

class TestSanity(unittest.TestCase):
    def test_parse_on_sample_pdfs_if_present(self):
        if parse_pdf is None or export_csv is None:
            self.skipTest("Dependencies not installed (run inside .venv).")

        in_dir = Path("data/input")
        if not in_dir.exists():
            self.skipTest("No PDFs found (data/input).")

        pdfs = list(in_dir.glob("*.pdf"))
        if not pdfs:
            self.skipTest("No PDFs to test.")

        parsers = [parse_pdf(str(p)) for p in pdfs]
        df_s, df_t, df_w = export_csv(parsers, "data/output/unittest_run")

        self.assertGreater(len(df_t), 0, "No transactions extracted")
        self.assertEqual(df_t["moneda"].isna().sum(), 0, "Some transactions have empty currency")

        # Visa: no se deben colar headers como transacciones
        bad = df_t["descripcion"].astype(str).str.upper().str.contains("DETALLE DE TRANSACCION")
        self.assertFalse(bool(bad.any()), "A table header was parsed as a transaction")

        # No ERROR warnings (si hay, alertar)
        if "level" in df_w.columns:
            self.assertFalse(bool((df_w["level"] == "ERROR").any()), "There are ERROR warnings")

if __name__ == "__main__":
    unittest.main()
