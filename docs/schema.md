# Output schema (CSV)

This project generates **3 CSVs**:

## 1) `statements.csv` (1 fila por PDF)

| Column | Type | Description |
|---|---:|---|
| `archivo` | string | Source PDF filename |
| `banco` | string | `"HSBC"` |
| `origen` | string | `"mastercard"`, `"visa"`, `"cuenta"` |
| `fecha_desde` | string/null | Period start (best-effort) |
| `fecha_hasta` | string/null | Period end / closing date (best-effort) |
| `saldo_anterior_ars` | number/null | Previous balance (ARS) when detectable |
| `saldo_anterior_usd` | number/null | Previous balance (USD) when detectable |
| `saldo_actual_ars` | number/null | Current/final balance (ARS) when detectable |
| `saldo_actual_usd` | number/null | Current/final balance (USD) when detectable |

## 2) `transactions.csv` (N filas por PDF)

| Column | Type | Description |
|---|---:|---|
| `archivo` | string | Source PDF filename |
| `fecha` | string | ISO-8601 date `YYYY-MM-DD` (empty if not available) |
| `descripcion` | string | Cleaned description (without amounts/ids/installment tokens) |
| `moneda` | string | `"ARS"`, `"USD"` (and occasionally others) |
| `importe` | number | **Signed**: debit negative / credit positive |
| `persona` | string | Person (holder/additional where detected) |
| `origen` | string | `"mastercard"`, `"visa"`, `"cuenta"` |
| `operation_id` | string/null | Trailing operation/authorization id when detected |
| `installment_number` | int/null | Installment number when detected |
| `installment_total` | int/null | Total installments when detected |

Notes:
- For cards, `importe` is taken as-is from the statement line (no FX conversion).
- For savings accounts, `importe` is inferred from running balances when needed.

## 3) `warnings.csv` (auditoría del parseo)

| Column | Type | Description |
|---|---:|---|
| `archivo` | string | Source PDF filename |
| `level` | string | `"INFO"`, `"WARNING"`, `"ERROR"` |
| `code` | string | Stable warning code |
| `message` | string | Human message |
| `context` | string/json/null | Best-effort context |
