import os
import unittest
from pathlib import Path

from hsbc_parser.dispatcher import parse_pdf
from hsbc_parser.export import export_csv

class TestSanity(unittest.TestCase):
    def test_parse_on_sample_pdfs_if_present(self):
        # If user provides PDFs locally under data/input, run sanity checks.
        in_dir = Path("data/input")
        if not in_dir.exists():
            self.skipTest("No hay data/input (PDFs) para testear en este entorno.")

        pdfs = list(in_dir.glob("*.pdf"))
        if not pdfs:
            self.skipTest("No hay PDFs en data/input.")

        parsers = [parse_pdf(str(p)) for p in pdfs]
        df_s, df_t, df_w = export_csv(parsers, "data/output_test")

        self.assertGreater(len(df_t), 0, "No se extrajeron transacciones")
        self.assertEqual(df_t["moneda"].isna().sum(), 0, "Hay transacciones sin moneda")

        # Visa: no se deben colar headers como transacciones
        bad = df_t["descripcion"].astype(str).str.upper().str.contains("DETALLE DE TRANSACCION")
        self.assertFalse(bool(bad.any()), "Se coló un header de tabla como transacción")

        # No ERROR warnings (si hay, alertar)
        if "level" in df_w.columns:
            self.assertFalse(bool((df_w["level"] == "ERROR").any()), "Hay warnings nivel ERROR")

if __name__ == "__main__":
    unittest.main()
