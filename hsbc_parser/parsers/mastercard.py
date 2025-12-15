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
    extract_installments,
    strip_trailing_amounts,
    extract_trailing_operation_id,
    strip_paren_currency_amount,
    is_statement_commentary_line,
)

class HSBCMastercardParser(BaseParser):
    """HSBC Argentina - MasterCard statement (modern format 2024–2025).

    - Uses explicit currency when present (USD/ARS). Otherwise assumes ARS if there is an amount.
    """

    def parse(self) -> None:
        if self._pages_override is None:
            with pdfplumber.open(self.pdf_path) as pdf:
                pages = [(p.extract_text() or "") for p in pdf.pages]
        else:
            pages = self._pages_override
        text = "\n".join(pages)
        text_compact = compact_spaced_month_letters(compact_spaced_numbers(text))

        archivo = self.pdf_path.split("/")[-1]
        cierre = re.search(r"Estado de cuenta al:?\s+(\d{2}-[A-Za-z]{3}-\d{2})", text_compact)
        cierre_anterior = re.search(r"Cierre Anterior:\s+(\d{2}-[A-Za-z]{3}-\d{2})", text_compact, re.I)
        m_prev_balance = re.search(r"SALDO ANTERIOR\s+([-\d.,]+)\s+([-\d.,]+)", text_compact, re.I)
        m_cur_balance = re.search(r"SALDO ACTUAL\s+([-\d.,]+)\s+([-\d.,]+)", text_compact, re.I)

        saldo_anterior_ars = saldo_anterior_usd = None
        saldo_actual_ars = saldo_actual_usd = None
        if m_prev_balance:
            saldo_anterior_ars = parse_amount(m_prev_balance.group(1))
            saldo_anterior_usd = parse_amount(m_prev_balance.group(2))
        if m_cur_balance:
            saldo_actual_ars = parse_amount(m_cur_balance.group(1))
            saldo_actual_usd = parse_amount(m_cur_balance.group(2))

        fecha_hasta = parse_date_iso(cierre.group(1)) if cierre else None
        fecha_desde = add_days_iso(parse_date_iso(cierre_anterior.group(1)), 1) if cierre_anterior else None

        self.statement = Statement(
            archivo=archivo,
            banco="HSBC",
            origen="mastercard",
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            saldo_anterior_ars=saldo_anterior_ars,
            saldo_anterior_usd=saldo_anterior_usd,
            saldo_actual_ars=saldo_actual_ars,
            saldo_actual_usd=saldo_actual_usd,
        )

        current_person = "TITULAR"

        for raw in text.split("\n"):
            line = raw.strip()
            up = line.upper()
            if "CON IVA" in up and "%" in up:
                continue

            if line.startswith("TOTAL TITULAR"):
                current_person = norm_space(line.replace("TOTAL TITULAR", ""))
                continue
            if line.startswith("TOTAL ADICIONAL"):
                current_person = norm_space(line.replace("TOTAL ADICIONAL", ""))
                continue

            m = re.match(r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(.+)", line)
            if not m:
                continue

            fecha_raw, resto = m.groups()
            if is_statement_commentary_line(resto):
                continue
            fecha = parse_date_iso(fecha_raw)
            resto = norm_space(resto)

            amounts = re.findall(r"(-?[\d.]+,\d{2}-?)", resto)
            if not amounts:
                continue

            desc = strip_trailing_amounts(resto)
            desc = strip_paren_currency_amount(desc)
            desc, inst_num, inst_total = extract_installments(desc)
            desc, operation_id = extract_trailing_operation_id(desc)

            # Many PDFs collapse currency columns; if we see two trailing amounts, treat them as ARS + USD.
            # Keep only non-zero USD rows to avoid noise.
            if len(amounts) >= 2:
                ars_raw, usd_raw = amounts[-2], amounts[-1]
                ars_val, usd_val = parse_amount(ars_raw), parse_amount(usd_raw)
                self.transactions.append(Transaction(
                    archivo=archivo,
                    fecha=fecha,
                    descripcion=desc,
                    moneda="ARS",
                    importe=ars_val,
                    persona=current_person,
                    origen="mastercard",
                    operation_id=operation_id,
                    installment_number=inst_num,
                    installment_total=inst_total,
                ))
                if round(usd_val, 2) != 0.0:
                    self.transactions.append(Transaction(
                        archivo=archivo,
                        fecha=fecha,
                        descripcion=desc,
                        moneda="USD",
                        importe=usd_val,
                        persona=current_person,
                        origen="mastercard",
                        operation_id=operation_id,
                        installment_number=inst_num,
                        installment_total=inst_total,
                    ))
                continue

            importe = parse_amount(amounts[-1])

            # moneda explícita dentro de paréntesis
            moneda = None
            m_currency = re.search(r"\((?:[A-Z]{3},)?\s*(USD|ARS|DOP)", resto)
            if m_currency:
                moneda = m_currency.group(1)

            # Regla acordada: si no hay moneda explícita pero sí importe -> ARS
            if moneda is None:
                moneda = "ARS"

            # real vs financiero (simple y auditable)
            tipo = "financiero" if re.search(r"PAGO|IMPUESTO|PERCEP|INTERES|INT\.|DEV ", resto.upper()) else "real"

            self.transactions.append(Transaction(
                archivo=archivo,
                fecha=fecha,
                descripcion=desc,
                moneda=moneda,
                importe=importe,
                persona=current_person,
                origen="mastercard",
                operation_id=operation_id,
                installment_number=inst_num,
                installment_total=inst_total,
            ))

        # Reconciliation: saldo_anterior + sum(transactions) == saldo_actual (per currency)
        if m_prev_balance and m_cur_balance:
            prev_ars, prev_usd = parse_amount(m_prev_balance.group(1)), parse_amount(m_prev_balance.group(2))
            cur_ars, cur_usd = parse_amount(m_cur_balance.group(1)), parse_amount(m_cur_balance.group(2))
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

        if not self.transactions:
            self.warn("ERROR", "NO_TRANSACTIONS", "No transactions detected")

        if self.statement.fecha_hasta is None:
            self.warn("WARNING", "MISSING_STATEMENT_FIELD", "Missing statement closing date", {"field": "fecha_hasta"})
