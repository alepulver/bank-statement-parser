# hsbc-parser

PDF statement parser for HSBC Argentina:
- Credit cards: **Mastercard** (modern format 2024–2025) and **Visa**
- Bank account: **Savings account** (Caja de Ahorro)

Outputs CSVs:
- `statements.csv` (1 row per PDF)
- `transactions.csv` (unified movements)
- `warnings.csv` (parsing audit)

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional: install the package (and create the `hsbc-parser` command)
pip install -e . --no-build-isolation
```

## Usage

Parse a folder of PDFs:

```bash
python -m hsbc_parser.cli test_pdfs --out data/output
# or if you installed the entrypoint:
hsbc-parser test_pdfs --out data/output
# compatibility: python run.py test_pdfs --out data/output
```

Parse a single PDF:

```bash
hsbc-parser "data/input/HSBC MasterCard 2025-01.pdf" --out data/output
```

Force parser type:

```bash
hsbc-parser data/input --type visa --out data/output
```

Logging (console + file by default):

```bash
hsbc-parser test_pdfs --out data/output --log-file outputs/hsbc_parser.log --log-level INFO
```

## Output

CSV files are written to the folder passed via `--out`.

Recommendation: keep local `data/` and `outputs/` out of git (see `.gitignore`).

## Schema

See `docs/schema.md`.

## Known issues

- **Visa totals may not reconcile** in some PDFs when text extraction collapses/merges table columns; this shows up as `BALANCE_SUM_MISMATCH` in `warnings.csv`.
- Some statement metadata is best-effort and may be missing; missing fields are reported as `MISSING_STATEMENT_FIELD`.
- Do not commit real bank statements to git. Use sanitized fixtures/tests and keep local PDFs in `data/` or another ignored folder.

## Tests

Run:

```bash
python -m unittest discover -s tests -q
```

Tests are sanity-level: they validate extraction and basic invariants, not bank-grade reconciliation.
