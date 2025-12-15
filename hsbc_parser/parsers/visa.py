from __future__ import annotations
import re
import pdfplumber
from .base import BaseParser
from .types import Statement, Transaction
from .utils import (
    parse_amount,
    norm_space,
    compact_spaced_numbers,
    compact_spaced_month_letters,
    parse_date_iso,
    add_days_iso,
    parse_date_iso_loose,
    extract_installments,
    strip_trailing_amounts,
    extract_trailing_operation_id,
    is_statement_commentary_line,
)

class HSBCVisaParser(BaseParser):
    """HSBC Argentina - Visa statement.

    - Ignores table headers like 'DETALLE DE TRANSACCION ...'
    - Currency by column (ARS/USD). If columns collapse, uses a simple heuristic.
    - Financial movements by keywords (SU PAGO / IMPUESTO / IVA / COM / BONI).
    """

    HEADER_GUARD = ("DETALLE DE TRANSACCION", "FECHA COMPROBANTE", "PESOS DOLARES")
    _AMOUNT_RE = re.compile(r"-?[\d.]+,\d{2}-?(?!%)")

    def parse(self) -> None:
        if self._pages_override is None:
            with pdfplumber.open(self.pdf_path) as pdf:
                pages = [(p.extract_text() or "") for p in pdf.pages]
        else:
            pages = self._pages_override
        text = "\n".join(pages)
        text_compact = compact_spaced_month_letters(compact_spaced_numbers(text))

        archivo = self.pdf_path.split("/")[-1]

        # Metadata best-effort (Visa suele variar; no forzamos)
        m_prev = re.search(r"SALDO\s+ANTERIOR\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})", text_compact, re.I)
        m_cur = re.search(r"SALDO\s+ACTUAL\s+\$?\s*([\d.]+,\d{2})\s+U\$S\s*([\d.]+,\d{2})", text_compact, re.I)
        cierre = re.search(r"CIERRE\s+ACTUAL\s+([0-9A-Za-z\s]{4,20})", text_compact, re.I)
        cierre_ant = re.search(r"CIERRE\s+ANTERIOR\s+([0-9A-Za-z\s]{4,20})", text_compact, re.I)
        prev_ars = parse_amount(m_prev.group(1)) if m_prev else None
        prev_usd = parse_amount(m_prev.group(2)) if m_prev else None
        cur_ars = parse_amount(m_cur.group(1)) if m_cur else None
        cur_usd = parse_amount(m_cur.group(2)) if m_cur else None

        fecha_hasta = parse_date_iso_loose(cierre.group(1)) if cierre else None
        fecha_desde = add_days_iso(parse_date_iso_loose(cierre_ant.group(1)), 1) if cierre_ant else None

        self.statement = Statement(
            archivo=archivo,
            banco="HSBC",
            origen="visa",
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            saldo_anterior_ars=prev_ars,
            saldo_anterior_usd=prev_usd,
            saldo_actual_ars=cur_ars,
            saldo_actual_usd=cur_usd,
        )

        current_person = "TITULAR"
        ignored = 0

        for page in pages:
            for raw in page.split("\n"):
                line = compact_spaced_numbers(raw.strip())
                # Some PDFs collapse columns and even remove the space after the date (e.g. '08.09.23350257* ...')
                line = re.sub(r"^(\d{2}\.\d{2}\.\d{2})(?=\d)", r"\1 ", line)
                up = line.upper()

                # Filter table headers
                if any(h in up for h in self.HEADER_GUARD):
                    continue
                if is_statement_commentary_line(line):
                    continue

                # Detect card-holder blocks (adicionales)
                m_holder = re.search(r"TARJETA\s+\d+\s+Total\s+Consumos\s+de\s+(.+)", line)
                if m_holder:
                    current_person = norm_space(m_holder.group(1))
                    continue

                # Financial-like lines (payments, taxes, fees). Prefer the table amounts at the end of the line
                # (avoid picking bases like '( 869,00 )' inside parentheses).
                if re.search(r"(SU\s+PAGO|IMPUESTO|IVA|COM\s+|BONI\s+)", up):
                    amounts = self._AMOUNT_RE.findall(line)
                    if not amounts:
                        if re.match(r"\d{2}\.\d{2}\.\d{2}\s+", line):
                            ignored += 1
                        continue
                    pesos = amounts[-2] if len(amounts) >= 2 else amounts[-1]
                    dolares = amounts[-1] if len(amounts) >= 2 else None

                    imp_pesos = parse_amount(pesos) if pesos else 0.0
                    imp_dolares = parse_amount(dolares) if dolares else 0.0
                    if imp_pesos != 0:
                        moneda, importe = "ARS", imp_pesos
                    elif imp_dolares != 0:
                        moneda, importe = "USD", imp_dolares
                    else:
                        moneda, importe = "ARS", 0.0

                    m_date = re.match(r"(\d{2}\.\d{2}\.\d{2})\s+(.+)$", line)
                    fecha = parse_date_iso(m_date.group(1)) if m_date else ""
                    desc = strip_trailing_amounts(line)
                    operation_id = None
                    m_lead = re.match(r"^\d{2}\.\d{2}\.\d{2}\s+(.+)$", desc)
                    if m_lead:
                        desc = m_lead.group(1)
                    m_op = re.match(r"^([0-9A-Z]{5,10}\*?)\s+(.+)$", desc)
                    if m_op and any(ch.isdigit() for ch in m_op.group(1)):
                        operation_id = m_op.group(1)
                        desc = m_op.group(2)
                    desc, inst_num, inst_total = extract_installments(desc)
                    desc, trailing_id = extract_trailing_operation_id(desc)
                    operation_id = operation_id or trailing_id
                    desc = re.sub(r"^\d{2}\.\d{2}\.\d{2}\s+", "", desc).strip()

                    self.transactions.append(Transaction(
                        archivo=archivo,
                        fecha=fecha,
                        descripcion=desc,
                        moneda=moneda,
                        importe=importe,
                        persona=current_person,
                        origen="visa",
                        operation_id=operation_id,
                        installment_number=inst_num,
                        installment_total=inst_total,
                    ))
                    continue

                # Purchase line: date dd.mm.yy + ... + (pesos, dolares) columns (collapsed is common)
                m = re.match(r"(\d{2}\.\d{2}\.\d{2})\s+(.+)", line)
                if not m:
                    continue

                fecha, _ = m.groups()
                amounts = self._AMOUNT_RE.findall(line)
                if not amounts:
                    ignored += 1
                    continue

                pesos = amounts[-2] if len(amounts) >= 2 else amounts[-1]
                dolares = amounts[-1] if len(amounts) >= 2 else None

                imp_pesos = parse_amount(pesos) if pesos else 0.0
                imp_dolares = parse_amount(dolares) if dolares else 0.0
                if imp_pesos != 0:
                    moneda, importe = "ARS", imp_pesos
                elif imp_dolares != 0:
                    moneda, importe = "USD", imp_dolares
                else:
                    self.warn("WARNING", "NO_AMOUNT", "Line without amount", norm_space(line))
                    continue

                desc = strip_trailing_amounts(line)
                operation_id = None
                m_lead = re.match(r"^(\d{2}\.\d{2}\.\d{2})\s+(.+)$", desc)
                if m_lead:
                    desc = m_lead.group(2)
                m_op = re.match(r"^([0-9A-Z]{5,10}\*?)\s+(.+)$", desc)
                if m_op and any(ch.isdigit() for ch in m_op.group(1)):
                    operation_id = m_op.group(1)
                    desc = m_op.group(2)
                desc, inst_num, inst_total = extract_installments(desc)
                desc, trailing_id = extract_trailing_operation_id(desc)
                operation_id = operation_id or trailing_id
                desc = re.sub(r"^\d{2}\.\d{2}\.\d{2}\s+", "", desc).strip()

                self.transactions.append(Transaction(
                    archivo=archivo,
                    fecha=parse_date_iso(fecha),
                    descripcion=desc,
                    moneda=moneda,
                    importe=importe,
                    persona=current_person,
                    origen="visa",
                    operation_id=operation_id,
                    installment_number=inst_num,
                    installment_total=inst_total,
                ))

        if not self.transactions:
            self.warn("ERROR", "NO_TRANSACTIONS", "No transactions detected")
        elif ignored:
            self.warn("WARNING", "IGNORED_ROWS", "Date lines that could not be parsed", {"count": ignored})

        if prev_ars is not None and prev_usd is not None and cur_ars is not None and cur_usd is not None:
            sum_ars = round(sum(t.importe for t in self.transactions if t.moneda == "ARS"), 2)
            sum_usd = round(sum(t.importe for t in self.transactions if t.moneda == "USD"), 2)
            exp_ars = round(prev_ars + sum_ars, 2)
            exp_usd = round(prev_usd + sum_usd, 2)
            if exp_ars != round(cur_ars, 2) or exp_usd != round(cur_usd, 2):
                diff_ars = round(exp_ars - round(cur_ars, 2), 2)
                diff_usd = round(exp_usd - round(cur_usd, 2), 2)
                denom = max(abs(cur_ars), 1.0)
                within = abs(diff_ars) / denom <= 0.05
                level = "INFO" if within else "WARNING"
                code = "BALANCE_SUM_WITHIN_TOLERANCE" if within else "BALANCE_SUM_MISMATCH"
                self.warn(
                    level,
                    code,
                    "PDF balances do not reconcile with parsed transactions",
                    {
                        "prev_ars": prev_ars,
                        "sum_ars": sum_ars,
                        "expected_ars": exp_ars,
                        "pdf_ars": cur_ars,
                        "diff_ars": diff_ars,
                        "prev_usd": prev_usd,
                        "sum_usd": sum_usd,
                        "expected_usd": exp_usd,
                        "pdf_usd": cur_usd,
                        "diff_usd": diff_usd,
                        "tolerance_ratio": 0.05,
                    },
                )
        else:
            self.warn("WARNING", "MISSING_BALANCE_FIELDS", "Could not extract SALDO ANTERIOR/SALDO ACTUAL from PDF")
