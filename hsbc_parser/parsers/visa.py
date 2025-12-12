from __future__ import annotations
import re
import pdfplumber
from .base import BaseParser
from .types import Statement, Transaction, warn
from .utils import parse_amount, norm_space

class HSBCVisaParser(BaseParser):
    """HSBC Argentina - Visa (resumen).

    - Ignora headers de tabla como 'DETALLE DE TRANSACCION ...'
    - Moneda por columna (ARS/USD). Si no se logra leer columnas, se usa heurística simple.
    - Movimientos financieros por keywords (SU PAGO / IMPUESTO / IVA / COM / BONI).
    """

    HEADER_GUARD = ("DETALLE DE TRANSACCION", "FECHA COMPROBANTE", "PESOS DOLARES")

    def parse(self) -> None:
        with pdfplumber.open(self.pdf_path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        text = "\n".join(pages)

        archivo = self.pdf_path.split("/")[-1]

        # Metadata best-effort (Visa suele variar; no forzamos)
        numero = re.search(r"RESUMEN\s+NRO\.?\s*(\d+)", text, re.I)

        self.statement = Statement(
            archivo=archivo,
            banco="HSBC",
            origen="visa",
            numero_resumen=numero.group(1) if numero else None,
            fecha_desde=None,
            fecha_hasta=None,
            titular_nombre=None,
            moneda=None,
        )

        current_person = "TITULAR"

        for page in pages:
            for raw in page.split("\n"):
                line = raw.strip()
                up = line.upper()

                # Filter table headers
                if any(h in up for h in self.HEADER_GUARD):
                    continue

                # Detect card-holder blocks (adicionales)
                m_holder = re.search(r"TARJETA\s+\d+\s+Total\s+Consumos\s+de\s+(.+)", line)
                if m_holder:
                    current_person = norm_space(m_holder.group(1))
                    continue

                # Financial-like lines
                if re.match(r"(SU\s+PAGO|IMPUESTO|IVA|COM\s+|BONI\s+)", up):
                    m_amt = re.search(r"(-?[\d.]+,\d{2})", line)
                    if m_amt:
                        self.transactions.append(Transaction(
                            archivo=archivo,
                            fecha="",
                            descripcion=norm_space(line),
                            moneda="ARS",
                            importe=parse_amount(m_amt.group(1)),
                            persona=current_person,
                            origen="visa",
                        ))
                    continue

                # Purchase line (best-effort): date dd.mm.yy + ... + pesos + optional usd
                # Many PDFs collapse columns; this regex is intentionally permissive.
                m = re.match(r"(\d{2}\.\d{2}\.\d{2})\s+.+?([\d.]+,\d{2})\s*([\d.]+,\d{2})?$", line)
                if not m:
                    continue

                fecha, pesos, dolares = m.groups()

                # Choose ARS if pesos != 0, else USD if dolares exists
                imp_pesos = parse_amount(pesos) if pesos else 0.0
                if imp_pesos != 0:
                    moneda, importe = "ARS", imp_pesos
                elif dolares:
                    moneda, importe = "USD", parse_amount(dolares)
                else:
                    warn(self.warnings, archivo, "WARNING", "NO_AMOUNT", "Línea sin importe", norm_space(line))
                    continue

                self.transactions.append(Transaction(
                    archivo=archivo,
                    fecha=fecha,
                    descripcion=norm_space(line),
                    moneda=moneda,
                    importe=importe,
                    persona=current_person,
                    origen="visa",
                ))

        if not self.transactions:
            warn(self.warnings, archivo, "ERROR", "NO_TRANSACTIONS", "No se detectaron transacciones")
