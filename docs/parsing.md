## Parsing overview

This project parses HSBC Argentina PDF statements and exports a unified `transactions.csv` plus `statements.csv` and `warnings.csv`.

There are three parsers:

- `hsbc_parser/parsers/mastercard.py`
- `hsbc_parser/parsers/visa.py`
- `hsbc_parser/parsers/cuenta.py` (Caja de Ahorro / account)

The CLI (`hsbc_parser/cli.py`) auto-detects the parser from the PDF text (or you can force it via `--type`).

## Common challenges / limitations

PDF text extraction is not structured:

- Column alignment may be lost (values can slide into the description, or multiple columns can merge).
- Multi-line rows can be split arbitrarily.
- Non-transaction blocks (terms, rates, installment offers, marketing, table headers) can appear in the middle of the extracted text stream.

Because of that, the parsers rely on a mix of:

- date anchors (e.g. `dd-Mmm-yy`)
- “money-looking” amounts (e.g. `123.456,78`)
- heuristics to **exclude commentary/conditions lines**

The core exclusion heuristic is `hsbc_parser/parsers/utils.py:is_statement_commentary_line`, which is intentionally conservative. If you see conditions being emitted as transactions, add/adjust patterns there.

Examples of **non-transactions** that should be excluded:

- Installment offer blocks containing rates: `TNA`, `TEA`, `TEM`, `CFT`, percent signs (`%`)
- Narrative lines like `Abonando el pago mínimo ...`
- “Con IVA / Sin IVA” financing blocks with `%`-formatted rates

## Mastercard (`hsbc_parser/parsers/mastercard.py`)

High-level flow:

1. Extract statement metadata (`fecha_hasta`, `saldo_anterior`, `saldo_actual`).
2. Parse transaction-like lines anchored by a leading date (`dd-Mmm-yy ...`).
3. Normalize description:
   - remove installment markers like `07/18` into `installment_number` + `installment_total`
   - extract `operation_id` at the end (keeps suffixes like `*`, `K`, `U`)
   - ignore embedded parenthetical “original currency” amounts like `(DOM,USD, 39,00)` when deciding the statement-column amount(s)
4. Parse additional “statement-level adjustment” lines in the consolidated summary without a leading date:
   - `DEV ... -123,45`
   - `IMPUESTO ... 123,45`
   - `PERCEP... 123,45`
   - `INT.... 123,45`
5. Persona assignment is *backfilled*: `TOTAL TITULAR/ADICIONAL <name> ...` often appears **after** the block it summarizes, so the parser assigns `<name>` to all transactions parsed since the previous total row.

Validations:

- `TOTAL TITULAR/ADICIONAL` is compared against the sum of parsed purchases for that block (excluding obvious “financial” lines like payments/interest). This is a heuristic and may require tuning for new PDFs.
- `SALDO ANTERIOR + sum(transactions) == SALDO ACTUAL` is checked per currency with a tolerance (see `warnings.csv`).

Known limitations:

- Some “summary” blocks are not clearly separable from purchases in extracted text; misclassification can happen and is reported via `warnings.csv`.

## Visa (`hsbc_parser/parsers/visa.py`)

Visa statements tend to embed additional tokens in the description:

- operation/authorization number can appear at the beginning of the description
- date fragments can also appear at the beginning of the description

The Visa parser attempts to:

- extract and normalize dates to ISO `YYYY-MM-DD`
- separate operation id from the description
- reconcile balances similarly to the other parsers (tolerance-based)

Known limitations:

- When PDF text extraction collapses columns, totals may not reconcile; this is surfaced as `BALANCE_SUM_MISMATCH`.

## Cuenta / Caja de Ahorro (`hsbc_parser/parsers/cuenta.py`)

Account statements are more “movement-based” and typically include:

- posting date
- movement description
- debit/credit amount
- resulting balance

The parser normalizes:

- dates to ISO `YYYY-MM-DD`
- amounts with `.` and `,` separators (Argentina-style)

Known limitations:

- Some PDFs omit “period start” dates; if the statement doesn’t include it, the parser cannot derive it reliably.
