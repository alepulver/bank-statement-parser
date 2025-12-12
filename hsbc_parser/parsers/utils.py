from __future__ import annotations

def parse_amount(s: str) -> float:
    # HSBC PDFs use thousands '.' and decimal ','
    return float(s.replace(".", "").replace(",", "."))

def norm_space(s: str) -> str:
    return " ".join(s.split()).strip()
