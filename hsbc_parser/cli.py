from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List

from .dispatcher import parse_pdf
from .export import export_csv
from .logging_utils import configure_logging


def _collect_pdfs(path: Path) -> List[Path]:
    if path.is_dir():
        return sorted(p for p in path.glob("*.pdf"))
    return [path]


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Parse HSBC PDFs (Mastercard / Visa / Savings account) and export CSV."
    )
    parser.add_argument("input", help="A folder containing PDFs or a single PDF")
    parser.add_argument(
        "--out",
        default="data/output",
        help="Output folder for CSV files (recommended to keep out of git).",
    )
    parser.add_argument(
        "--tipo",
        "--type",
        choices=["auto", "mastercard", "visa", "cuenta", "account"],
        default="auto",
        help="Force parser type (default: auto)",
    )
    parser.add_argument(
        "--log-file",
        default="data/logs/hsbc_parser.log",
        help="Log file path (default: data/logs/hsbc_parser.log)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Log level (default: INFO)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    configure_logging(log_file=args.log_file, level=args.log_level)

    in_path = Path(args.input)
    pdfs = _collect_pdfs(in_path)

    parsers = []
    for pdf in pdfs:
        tipo = None if args.tipo == "auto" else ("cuenta" if args.tipo == "account" else args.tipo)
        parsers.append(parse_pdf(str(pdf), tipo))

    export_csv(parsers, args.out)
    print(f"OK: processed {len(pdfs)} PDFs. CSVs in: {args.out}")


if __name__ == "__main__":
    main()
