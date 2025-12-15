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
    is_statement_tail_conditions_start,
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
        saw_total_row = False
        pending_tx_indexes: list[int] = []
        last_tx_fecha: str | None = None
        pending_adjustment_desc: str | None = None
        in_tail_conditions = False
        total_line_re = re.compile(
            r"^TOTAL\s+(TITULAR|ADICIONAL)\s+(.+?)\s+(-?[\d.]+,\d{2}-?)\s+(-?[\d.]+,\d{2}-?)\s*$",
            re.I,
        )
        date_line_re = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}\b")
        amount_re = re.compile(r"(-?[\d.]+,\d{2}-?)")

        def find_money_amounts(s: str) -> list[str]:
            # Avoid treating percentages like "80,48%" as money amounts.
            out: list[str] = []
            for m in amount_re.finditer(s):
                if m.end() < len(s) and s[m.end()] == "%":
                    continue
                out.append(m.group(1))
            return out

        def is_summary_adjustment_line(up: str) -> bool:
            # Statement-level adjustments (taxes, perceptions, interests, refunds) sometimes appear in the
            # consolidated summary without a leading date.
            #
            # Examples:
            #   - "DEV IMPUESTO PAIS -184102,49"
            #   - "IMPUESTO PAIS 184102,48"
            #   - "PERCEP.AFIP RG 4815 30% 184102,48"
            #   - "INT. FINANCIACION 23229,43"
            #
            # Exclude summary totals (SUBTOTAL, SALDO PENDIENTE, etc.) and unrelated informational blocks.
            if up.startswith(("SALDO ", "SUBTOTAL", "TOTAL ", "COMPRAS ", "PAGO MINIMO", "VENCIMIENTO", "CIERRE ")):
                return False
            if up.startswith(("LIMITE ", "LÍMITE ", "ABONANDO ", "EFVO", "ENT/SUCURSAL", "DB ")):
                return False
            return up.startswith(
                (
                    "DEV ",
                    "IMPUESTO",
                    "PERCEP",
                    "PERCEPC",
                    "PERC ",
                    "INT.",
                    "INTERES",
                    "I.V.A",
                    "IVA ",
                    "IVA.",
                    "IVA:",
                    "PUNITORIO",
                    "PUNITORIOS",
                )
            )

        def _finalize_person_block(name: str, total_ars: float | None, total_usd: float | None) -> None:
            if not pending_tx_indexes:
                return

            # Backfill persona for this block.
            for idx in pending_tx_indexes:
                self.transactions[idx].persona = name

            # Validate the totals row vs the parsed transactions in this block.
            if total_ars is not None and total_usd is not None:
                # The 'TOTAL TITULAR/ADICIONAL' row is a purchases/consumption subtotal. It typically EXCLUDES
                # payments like 'PAGO CAJERO/INTERNET' and similar financial rows.
                def is_financial(desc: str) -> bool:
                    up = (desc or "").upper()
                    return bool(re.search(r"\b(SU\s+PAGO|PAGO|IMPUESTO|PERCEP|INTERES|INT\.|DEV)\b", up))

                sum_ars = round(
                    sum(
                        self.transactions[i].importe
                        for i in pending_tx_indexes
                        if self.transactions[i].moneda == "ARS" and not is_financial(self.transactions[i].descripcion)
                    ),
                    2,
                )
                sum_usd = round(
                    sum(
                        self.transactions[i].importe
                        for i in pending_tx_indexes
                        if self.transactions[i].moneda == "USD" and not is_financial(self.transactions[i].descripcion)
                    ),
                    2,
                )

                diff_ars = round(sum_ars - round(total_ars, 2), 2)
                diff_usd = round(sum_usd - round(total_usd, 2), 2)
                denom = max(abs(total_ars), 1.0)
                within = abs(diff_ars) / denom <= 0.05 and abs(diff_usd) <= 0.01

                # Avoid noisy logs: only report when there's a real discrepancy.
                if not (diff_ars == 0.0 and diff_usd == 0.0):
                    level = "INFO" if within else "WARNING"
                    code = "PERSON_TOTAL_WITHIN_TOLERANCE" if within else "PERSON_TOTAL_MISMATCH"
                    self.warn(
                        level,
                        code,
                        "TOTAL (TITULAR/ADICIONAL) differs from sum of parsed purchases for that block",
                        {
                            "persona": name,
                            "sum_ars": sum_ars,
                            "total_ars": round(total_ars, 2),
                            "diff_ars": diff_ars,
                            "sum_usd": sum_usd,
                            "total_usd": round(total_usd, 2),
                            "diff_usd": diff_usd,
                            "tolerance_ratio_ars": 0.05,
                        },
                    )

            pending_tx_indexes.clear()

        for raw in text.split("\n"):
            line = raw.strip()
            up = line.upper()
            if "CON IVA" in up and "%" in up:
                continue

            # If we hit the trailing terms/conditions section, stop parsing further transaction-like rows.
            # Keep scanning for TOTAL rows (persona backfill) but ignore purchases/adjustments afterwards.
            if not in_tail_conditions and last_tx_fecha and is_statement_tail_conditions_start(line):
                in_tail_conditions = True

            # Some statements include statement-level adjustment lines (refunds/taxes/interests) in the
            # consolidated summary without a leading date. Treat them as transactions for reconciliation,
            # but do NOT attach them to a TITULAR/ADICIONAL purchases block.
            if in_tail_conditions:
                m_total = total_line_re.match(line)
                if m_total:
                    saw_total_row = True
                    name = norm_space(m_total.group(2))
                    total_ars = parse_amount(m_total.group(3))
                    total_usd = parse_amount(m_total.group(4))
                    _finalize_person_block(name, total_ars, total_usd)
                    current_person = "TITULAR"
                continue

            if pending_adjustment_desc is not None:
                amounts = find_money_amounts(line)
                if amounts:
                    importe = parse_amount(amounts[-1])
                    self.transactions.append(
                        Transaction(
                            archivo=archivo,
                            fecha=last_tx_fecha or (self.statement.fecha_hasta or ""),
                            descripcion=pending_adjustment_desc,
                            moneda="ARS",
                            importe=importe,
                            persona=current_person,
                            origen="mastercard",
                        )
                    )
                    pending_adjustment_desc = None
                    continue
                if line and not set(line) <= {"-", " "}:
                    pending_adjustment_desc = None

            if not date_line_re.match(line) and is_summary_adjustment_line(up):
                amounts = find_money_amounts(line)
                desc = norm_space(strip_paren_currency_amount(strip_trailing_amounts(line)))
                if amounts:
                    importe = parse_amount(amounts[-1])
                    self.transactions.append(
                        Transaction(
                            archivo=archivo,
                            fecha=last_tx_fecha or (self.statement.fecha_hasta or ""),
                            descripcion=desc,
                            moneda="ARS",
                            importe=importe,
                            persona=current_person,
                            origen="mastercard",
                        )
                    )
                    continue
                # Only DEV lines are expected to be split as "DEV ...." + "<amount>" on the next line.
                if up.startswith("DEV "):
                    pending_adjustment_desc = desc
                    continue

            m_total = total_line_re.match(line)
            if m_total:
                saw_total_row = True
                # In some PDFs the 'TOTAL ... <name> <ars> <usd>' row appears AFTER the block of transactions,
                # so use it to backfill the persona for the pending block.
                name = norm_space(m_total.group(2))
                total_ars = parse_amount(m_total.group(3))
                total_usd = parse_amount(m_total.group(4))
                _finalize_person_block(name, total_ars, total_usd)
                current_person = "TITULAR"  # next block person name will be determined by its own TOTAL row
                continue

            m = re.match(r"(\d{2}-[A-Za-z]{3}-\d{2})\s+(.+)", line)
            if not m:
                continue

            fecha_raw, resto = m.groups()
            if is_statement_commentary_line(resto):
                continue
            fecha = parse_date_iso(fecha_raw)
            last_tx_fecha = fecha or last_tx_fecha
            resto = norm_space(resto)

            # IMPORTANT: many lines include an informational amount inside parentheses:
            #   '(DOM,USD, 39,00)' or '(USA,ARS, 4799,99)'.
            # Those are NOT reliable statement-column amounts (they can be original currency amounts),
            # and when extracted alongside the real column amount they caused duplicated transactions.
            # For column parsing, ignore the parenthetical amount.
            resto_for_amounts = strip_paren_currency_amount(resto)
            amounts = re.findall(r"(-?[\d.]+,\d{2}-?)", resto_for_amounts)
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
                pending_tx_indexes.append(len(self.transactions) - 1)
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
                    pending_tx_indexes.append(len(self.transactions) - 1)
                continue

            importe = parse_amount(amounts[-1])

            moneda = None

            # Some statements mark USD payments outside parentheses: 'SU PAGO U$S ...'
            if "U$S" in up or "U$S" in resto.upper() or re.search(r"\bUSD\b", up):
                moneda = "USD"

            # Foreign purchases often show a country hint like '(USA,ARS)' or '(DOM,DOP)'.
            # When only one column amount is extracted, it's generally the USD statement column.
            m_country = re.search(r"\(([A-Z]{2,3}),\s*(?:USD|ARS|DOP)\b", resto, re.I)
            if moneda is None and m_country and m_country.group(1).upper() not in ("ARG", "AR"):
                moneda = "USD"

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
            pending_tx_indexes.append(len(self.transactions) - 1)

        # If the file ends without a TOTAL row for the last block, keep the current persona (best-effort).
        # If this happens in practice, we'll report it so it can be reviewed.
        if saw_total_row and pending_tx_indexes:
            first = self.transactions[pending_tx_indexes[0]]
            last = self.transactions[pending_tx_indexes[-1]]
            self.warn(
                "WARNING",
                "MISSING_PERSON_TOTAL_AT_EOF",
                "Reached end of PDF without a closing TOTAL TITULAR/ADICIONAL for the last block",
                {
                    "persona_assigned": current_person,
                    "count": len(pending_tx_indexes),
                    "first_fecha": first.fecha,
                    "last_fecha": last.fecha,
                    "first_desc": first.descripcion,
                    "last_desc": last.descripcion,
                },
            )
        pending_tx_indexes.clear()

        # Reconciliation: saldo_anterior + sum(transactions) == saldo_actual (per currency)
        if m_prev_balance and m_cur_balance:
            prev_ars, prev_usd = parse_amount(m_prev_balance.group(1)), parse_amount(m_prev_balance.group(2))
            cur_ars, cur_usd = parse_amount(m_cur_balance.group(1)), parse_amount(m_cur_balance.group(2))
            sum_ars = round(sum(t.importe for t in self.transactions if t.moneda == "ARS"), 2)
            sum_usd = round(sum(t.importe for t in self.transactions if t.moneda == "USD"), 2)
            exp_ars = round(prev_ars + sum_ars, 2)
            exp_usd = round(prev_usd + sum_usd, 2)

            if exp_ars != round(cur_ars, 2) or exp_usd != round(cur_usd, 2):
                denom = max(abs(cur_ars), 1.0)
                diff_ars = round(exp_ars - round(cur_ars, 2), 2)
                diff_usd = round(exp_usd - round(cur_usd, 2), 2)
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
