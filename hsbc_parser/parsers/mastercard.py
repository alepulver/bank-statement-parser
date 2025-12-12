from __future__ import annotations
import re
import pdfplumber
from .base import BaseParser
from .types import Statement, Transaction, warn
from .utils import parse_amount, norm_space

class HSBCMastercardParser(BaseParser):
    """HSBC Argentina - MasterCard (formato moderno 2024–2025).

    - Moneda explícita si existe (USD/ARS). Si no hay, se asume ARS si hay importe.
    - Separa real vs financiero por keywords (sin categorizar gastos).
    """

    def parse(self) -> None:
        with pdfplumber.open(self.pdf_path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)

        archivo = self.pdf_path.split("/")[-1]
        numero = re.search(r"Nº de Resumen\s+(\d+)", text)
        cierre = re.search(r"Estado de cuenta al\s+(\d{2}-[A-Za-z]{3}-\d{2})", text)

        self.statement = Statement(
            archivo=archivo,
            banco="HSBC",
            origen="mastercard",
            numero_resumen=numero.group(1) if numero else None,
            fecha_desde=None,
            fecha_hasta=cierre.group(1) if cierre else None,
            titular_nombre=None,
            moneda=None,
        )

        current_person = "TITULAR"

        for raw in text.split("\n"):
            line = raw.strip()

            if line.startswith("TOTAL TITULAR"):
                current_person = norm_space(line.replace("TOTAL TITULAR", ""))
                continue
            if line.startswith("TOTAL ADICIONAL"):
                current_person = norm_space(line.replace("TOTAL ADICIONAL", ""))
                continue

            m = re.match(r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(.+)", line)
            if not m:
                continue

            fecha, resto = m.groups()
            resto = norm_space(resto)

            m_amt = re.search(r"(-?[\d.]+,\d{2})$", resto)
            if not m_amt:
                continue

            importe = parse_amount(m_amt.group(1))

            # moneda explícita dentro de paréntesis
            moneda = None
            m_cur = re.search(r"\((?:[A-Z]{3},)?\s*(USD|ARS|DOP)", resto)
            if m_cur:
                moneda = m_cur.group(1)

            # Regla acordada: si no hay moneda explícita pero sí importe -> ARS
            if moneda is None:
                moneda = "ARS"

            # real vs financiero (simple y auditable)
            tipo = "financiero" if re.search(r"PAGO|IMPUESTO|PERCEP|INTERES|INT\.|DEV ", resto.upper()) else "real"

            self.transactions.append(Transaction(
                archivo=archivo,
                fecha=fecha,
                descripcion=resto,
                moneda=moneda,
                importe=importe,
                persona=current_person,
                origen="mastercard",
            ))

        if not self.transactions:
            warn(self.warnings, archivo, "ERROR", "NO_TRANSACTIONS", "No se detectaron transacciones")
