from __future__ import annotations
import re
import pdfplumber
from .base import BaseParser
from .types import Statement, Transaction
from .utils import (
    parse_amount,
    norm_space,
    parse_date_iso,
    extract_installments,
    strip_trailing_amounts,
    extract_trailing_operation_id,
)

class HSBCCajaAhorroParser(BaseParser):
    """HSBC - Savings account statement.

    - Parses the FECHA/REFERENCIA/NRO/DEBITO/CREDITO/SALDO table
    - Emits signed amounts: debit -> negative, credit -> positive (inferred from running balance)
    - Currency by section (ARS or USD) from 'CAJA DE AHORRO $' / 'U$S'
    """

    def parse(self) -> None:
        if self._pages_override is None:
            with pdfplumber.open(self.pdf_path) as pdf:
                pages = [(p.extract_text() or "") for p in pdf.pages]
        else:
            pages = self._pages_override
        text = "\n".join(pages)

        archivo = self.pdf_path.split("/")[-1]

        m_period = re.search(r"EXTRACTO\s+DEL\s+(\d{2}/\d{2}/\d{4})\s+AL\s+(\d{2}/\d{2}/\d{4})", text, re.I)
        default_year = None
        if m_period:
            default_year = int(m_period.group(2).split("/")[-1])

        self.statement = Statement(
            archivo=archivo,
            banco="HSBC",
            origen="cuenta",
            fecha_desde=parse_date_iso(m_period.group(1)) if m_period else None,
            fecha_hasta=parse_date_iso(m_period.group(2)) if m_period else None,
        )

        if not m_period:
            self.warn("WARNING", "NO_PERIOD", "Could not detect statement period")

        in_table = False
        prev_saldo = None
        current_currency = None
        section_start: dict[str, float] = {}
        section_end: dict[str, float] = {}
        section_sum: dict[str, float] = {}
        ignored_rows: dict[str, int] = {}
        last_fecha: str | None = None

        # Heurística: tabla empieza tras header 'FECHA REFERENCIA NRO DEBITO CREDITO SALDO'
        for page in pages:
            for raw in page.split("\n"):
                line = raw.strip()
                up = line.upper()

                # Detect cambio de cuenta / moneda
                if "CAJA DE AHORRO" in up and "U$S" in up:
                    current_currency = "USD"
                    prev_saldo = None
                    last_fecha = None
                elif "CAJA DE AHORRO" in up and "$" in up:
                    current_currency = "ARS"
                    prev_saldo = None
                    last_fecha = None

                if re.search(r"FECHA\s+REFERENCIA\s+NRO\s+DEBITO\s+CREDITO\s+SALDO", up):
                    in_table = True
                    continue

                if not in_table:
                    continue

                # Ignore obvious section breaks
                if up.startswith("HOJA ") or "DETALLE DE INTERESES" in up or "DETALLE DE PLAZOS FIJOS" in up:
                    continue

                m_prev = re.search(r"SALDO ANTERIOR\s+([-\d.,]+)", line, re.I)
                if m_prev:
                    prev_saldo = parse_amount(m_prev.group(1))
                    if current_currency:
                        section_start[current_currency] = prev_saldo
                        section_sum.setdefault(current_currency, 0.0)
                        ignored_rows.setdefault(current_currency, 0)
                    continue

                m_final = re.search(r"SALDO FINAL\s+([-\d.,]+)", line, re.I)
                if m_final:
                    end_val = parse_amount(m_final.group(1))
                    if current_currency:
                        section_end[current_currency] = end_val
                        if prev_saldo is not None and round(prev_saldo, 2) != round(end_val, 2):
                            self.warn(
                                "WARNING",
                                "BALANCE_FINAL_MISMATCH",
                                "PDF final balance does not match the last running balance in the table",
                                {
                                    "moneda": current_currency,
                                    "ultimo_saldo_tabla": prev_saldo,
                                    "saldo_final": end_val,
                                },
                            )
                    in_table = False
                    prev_saldo = None
                    last_fecha = None
                    continue

                # Rows can be either dated or continued lines without the date.
                m_date = re.match(r"(\d{2}-[A-Z]{3})\s+(.+)", line)
                if m_date:
                    fecha_raw, resto = m_date.groups()
                    last_fecha = fecha_raw
                    fecha = parse_date_iso(fecha_raw, default_year=default_year)
                elif line.startswith("-"):
                    fecha = parse_date_iso(last_fecha or "", default_year=default_year) if last_fecha else ""
                    resto = line
                else:
                    continue

                # numeric tokens with decimal (handles 1.234,56 / 1,234.56 / .06)
                num_re = r"-?(?:\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d+[.,]\d{2}|\.\d{2})"
                nums = re.findall(num_re, resto)
                if len(nums) < 1:
                    if current_currency:
                        ignored_rows[current_currency] = ignored_rows.get(current_currency, 0) + 1
                    continue

                saldo_val = parse_amount(nums[-1])
                importe_val = None
                if prev_saldo is not None:
                    # Most reliable: delta between running balances
                    importe_val = round(saldo_val - prev_saldo, 2)
                else:
                    # Fallback when we didn't capture SALDO ANTERIOR for the table
                    if len(nums) >= 3:
                        debito_val = parse_amount(nums[-3])
                        credito_val = parse_amount(nums[-2])
                        importe_val = round(credito_val, 2) if abs(credito_val) > 0 else round(-debito_val, 2)
                    elif len(nums) == 2:
                        self.warn(
                            "WARNING",
                            "NO_PREV_BALANCE",
                            "Could not infer transaction sign (missing previous balance)",
                            norm_space(line),
                        )
                        importe_val = parse_amount(nums[0])

                prev_saldo = saldo_val

                if importe_val is None:
                    self.warn("WARNING", "NO_AMOUNT_ROW", "Row without debit or credit", norm_space(line))
                    continue

                first_num = re.search(num_re, resto)
                desc = norm_space(resto[:first_num.start()] if first_num else resto)
                desc = desc.lstrip("-").strip()
                desc, inst_num, inst_total = extract_installments(desc)
                desc = strip_trailing_amounts(desc)

                desc, operation_id = extract_trailing_operation_id(desc)

                if current_currency:
                    section_sum[current_currency] = section_sum.get(current_currency, 0.0) + float(importe_val)

                self.transactions.append(Transaction(
                    archivo=archivo,
                    fecha=fecha,
                    descripcion=desc,
                    moneda=current_currency or "ARS",
                    importe=importe_val,
                    persona="TITULAR",
                    origen="cuenta",
                    operation_id=operation_id,
                    installment_number=inst_num,
                    installment_total=inst_total,
                ))

        # Section-level validations: start + sum == end
        for cur, start_val in section_start.items():
            if cur in section_end:
                expected_end = round(start_val + section_sum.get(cur, 0.0), 2)
                actual_end = round(section_end[cur], 2)
                if expected_end != actual_end:
                    diff = round(expected_end - actual_end, 2)
                    denom = max(abs(actual_end), 1.0)
                    within = abs(diff) / denom <= 0.05
                    level = "INFO" if within else "WARNING"
                    code = "BALANCE_SUM_WITHIN_TOLERANCE" if within else "BALANCE_SUM_MISMATCH"
                    self.warn(
                        level,
                        code,
                        "PDF balances do not reconcile with parsed transactions",
                        {
                            "moneda": cur,
                            "saldo_anterior": start_val,
                            "suma_movimientos": round(section_sum.get(cur, 0.0), 2),
                            "saldo_final_esperado": expected_end,
                            "saldo_final_pdf": actual_end,
                            "diff": diff,
                            "tolerance_ratio": 0.05,
                        },
                    )

        # Expose end balances in statement row (best-effort)
        if "ARS" in section_end:
            self.statement.saldo_actual_ars = section_end["ARS"]
        if "USD" in section_end:
            self.statement.saldo_actual_usd = section_end["USD"]
        if "ARS" in section_start:
            self.statement.saldo_anterior_ars = section_start["ARS"]
        if "USD" in section_start:
            self.statement.saldo_anterior_usd = section_start["USD"]

        for cur, count in ignored_rows.items():
            if count:
                self.warn(
                    "WARNING",
                    "IGNORED_ROWS",
                    "Table rows that could not be parsed",
                    {"moneda": cur, "count": count},
                )

        if not self.transactions:
            self.warn("ERROR", "NO_TRANSACTIONS", "No transactions detected")

        if self.statement.fecha_desde is None or self.statement.fecha_hasta is None:
            self.warn("WARNING", "MISSING_STATEMENT_FIELD", "Missing statement period", {"field": "fecha_desde/fecha_hasta"})
