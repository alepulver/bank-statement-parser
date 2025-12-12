# hsbc-parser

Parser de PDFs de HSBC Argentina para:
- Tarjetas **Mastercard** (formato moderno 2024–2025)
- Tarjetas **Visa**
- **Caja de Ahorro** (extracto / resumen)

Genera CSVs:
- `statements.csv` (1 fila por PDF)
- `transactions.csv` (movimientos unificados)
- `warnings.csv` (auditoría del parseo)

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

Procesar una carpeta con PDFs:

```bash
python run.py data/input --out data/output
```

Procesar un PDF individual:

```bash
python run.py "data/input/HSBC MasterCard 2025-01.pdf" --out data/output
```

Forzar el tipo:

```bash
python run.py data/input --tipo visa --out data/output
```

## Salida

Los CSVs se generan en la carpeta indicada por `--out`.

⚠️ Recomendación: mantener `data/` fuera del repo usando `.gitignore` (incluido).

## Esquema

Ver `docs/schema.md`.

## Sanity tests (básicos)

Ejecutar:

```bash
python -m unittest -q
```

Estos tests no validan montos contra el banco; validan que:
- se extraigan transacciones
- no haya transacciones con `moneda` vacía
- no se cuelen headers de tabla como movimientos (Visa)
- no haya warnings `ERROR` (si los hay, alertan cambio de formato o bug)
