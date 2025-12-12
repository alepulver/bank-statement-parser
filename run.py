from __future__ import annotations
import argparse
from pathlib import Path

from hsbc_parser.dispatcher import parse_pdf
from hsbc_parser.export import export_csv

def main():
    ap = argparse.ArgumentParser(description="Parse HSBC PDFs (Mastercard / Visa / Caja de Ahorro) y exporta CSV.")
    ap.add_argument("input", help="Carpeta con PDFs o un PDF individual")
    ap.add_argument("--out", default="data/output", help="Carpeta de salida (CSV). Recomendado ignorar en git.")
    ap.add_argument("--tipo", choices=["auto", "mastercard", "visa", "cuenta"], default="auto",
                    help="Forzar tipo de parser (default: auto)")
    args = ap.parse_args()

    in_path = Path(args.input)
    pdfs = []
    if in_path.is_dir():
        pdfs = sorted([p for p in in_path.glob("*.pdf")])
    else:
        pdfs = [in_path]

    parsers = []
    for pdf in pdfs:
        p = parse_pdf(str(pdf), None if args.tipo == "auto" else args.tipo)
        parsers.append(p)

    export_csv(parsers, args.out)
    print(f"OK: procesados {len(pdfs)} PDFs. CSVs en: {args.out}")

if __name__ == "__main__":
    main()
