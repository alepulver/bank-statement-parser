from __future__ import annotations
import re
import pdfplumber
from .base import BaseParser
from .types import Statement, Transaction, warn
from .utils import parse_amount, norm_space

class HSBCCajaAhorroParser(BaseParser):
    """HSBC - Resumen de Caja de Ahorro (extracto).

    - Lee tabla FECHA/REFERENCIA/NRO/DEBITO/CREDITO/SALDO
    - Emite importe con signo: débito -> negativo, crédito -> positivo
    - Moneda por sección (ARS o USD) detectada por presencia de 'CAJA DE AHORRO $' / 'U$S'
    """

    def parse(self) -> None:
        with pdfplumber.open(self.pdf_path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        text = "\n".join(pages)

        archivo = self.pdf_path.split("/")[-1]

        m_period = re.search(r"EXTRACTO\s+DEL\s+(\d{2}/\d{2}/\d{4})\s+AL\s+(\d{2}/\d{2}/\d{4})", text, re.I)

        moneda = None
        if "CAJA DE AHORRO $" in text or "CAJA DE AHORRO $" in text.upper() or "CAJA DE AHORRO $ " in text.upper() or "CAJA DE AHORRO $" in text:
            moneda = "ARS"
        if "CAJA DE AHORRO U$S" in text.upper() or "CAJA DE AHORRO EN U$S" in text.upper():
            # Nota: algunos PDFs incluyen ambas cuentas; el parser usa la primera detectada en statement
            moneda = moneda or "USD"

        self.statement = Statement(
            archivo=archivo,
            banco="HSBC",
            origen="cuenta",
            numero_resumen=None,
            fecha_desde=m_period.group(1) if m_period else None,
            fecha_hasta=m_period.group(2) if m_period else None,
            titular_nombre=None,
            moneda=moneda,
        )

        if not m_period:
            warn(self.warnings, archivo, "WARNING", "NO_PERIOD", "No se detectó período del extracto")

        in_table = False
        # Heurística: tabla empieza tras header 'FECHA REFERENCIA NRO DEBITO CREDITO SALDO'
        for page in pages:
            for raw in page.split("\n"):
                line = raw.strip()
                up = line.upper()

                if re.search(r"FECHA\s+REFERENCIA\s+NRO\s+DEBITO\s+CREDITO\s+SALDO", up):
                    in_table = True
                    continue

                if not in_table:
                    continue

                # Ignore obvious section breaks
                if up.startswith("HOJA ") or "DETALLE DE INTERESES" in up or "DETALLE DE PLAZOS FIJOS" in up:
                    continue
                if "SALDO FINAL" in up or "SALDO ANTERIOR" in up:
                    continue

                # Row: 09-ENE - EXT. POR CAJA 05274 2,500.00 5,065.88  (USD example)
                m = re.match(r"(\d{2}-[A-Z]{3})\s+(.+?)\s+(\d{5}|\d{4,5})\s+([\d.,]*)\s+([\d.,]*)\s+([\d.,]+)$", line)
                if not m:
                    continue

                fecha, desc, nro, debito, credito, saldo = m.groups()
                desc = norm_space(f"{desc} {nro}")

                if debito:
                    importe = -parse_amount(debito)
                elif credito:
                    importe = parse_amount(credito)
                else:
                    warn(self.warnings, archivo, "WARNING", "NO_AMOUNT_ROW", "Fila sin débito ni crédito", norm_space(line))
                    continue

                self.transactions.append(Transaction(
                    archivo=archivo,
                    fecha=fecha,
                    descripcion=desc,
                    moneda=self.statement.moneda or "ARS",
                    importe=importe,
                    persona="TITULAR",
                    origen="cuenta",
                ))

        if not self.transactions:
            warn(self.warnings, archivo, "ERROR", "NO_TRANSACTIONS", "No se detectaron transacciones")
