from __future__ import annotations

import re
from datetime import date, timedelta

def parse_amount(s: str) -> float:
    """Parse monetary strings that may use '.' or ',' as thousands/decimal separators."""
    raw = s.strip()
    if not raw:
        return 0.0

    negative = raw.startswith("-") or raw.endswith("-")
    raw = raw.strip(" -")

    # Decide decimal separator: choose the rightmost of '.' or ',' as decimal marker.
    last_dot = raw.rfind(".")
    last_comma = raw.rfind(",")
    if last_dot == -1 and last_comma == -1:
        dec = "."
    else:
        dec = "." if last_dot > last_comma else ","

    if dec == ",":
        normalized = raw.replace(".", "").replace(",", ".")
    else:
        normalized = raw.replace(",", "")

    value = float(normalized)
    return -value if negative else value

def norm_space(s: str) -> str:
    return " ".join(s.split()).strip()


_SPACED_NUMBER_RE = re.compile(r"(?<![\d/])(\d[\d\s.,]*\d)")


def compact_spaced_numbers(s: str) -> str:
    """Remove OCR/extraction spaces inside numbers like '4 2 5 . 4 7 1 , 3 5' -> '425.471,35'.

    Intentionally avoids compacting when the match is preceded by '/' to avoid patterns like '05/06 200,00'
    becoming '05/06200,00'.
    """

    def repl(m: re.Match[str]) -> str:
        chunk = m.group(1)
        if " " not in chunk:
            return chunk
        # Only compact when the number is clearly split into multiple parts (many spaces).
        if chunk.count(" ") < 2:
            return chunk
        # Avoid touching dates like 23.12.23 or other dot-only tokens.
        if "," not in chunk:
            return chunk
        # Avoid merging two separate decimal numbers like '9,88 0,00'.
        if re.search(r"\d[.,]\d{2}\s+\d", chunk):
            return chunk
        return chunk.replace(" ", "")

    return _SPACED_NUMBER_RE.sub(repl, s)


_MONTHS = {
    "JAN": 1,
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "AGO": 8,
    "SEP": 9,
    "SET": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
    "DIC": 12,
}


def parse_date_iso(date_str: str, *, default_year: int | None = None) -> str:
    """Parse common HSBC date formats into ISO-8601 (YYYY-MM-DD)."""
    s = norm_space(date_str)
    if not s:
        return ""

    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        dd, mm, yyyy = map(int, m.groups())
        return f"{yyyy:04d}-{mm:02d}-{dd:02d}"

    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{2})$", s)
    if m:
        dd, mm, yy = map(int, m.groups())
        year = 2000 + yy
        return f"{year:04d}-{mm:02d}-{dd:02d}"

    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{2})$", s)
    if m:
        dd = int(m.group(1))
        mon = _MONTHS.get(m.group(2).upper())
        yy = int(m.group(3))
        if mon is None:
            return ""
        year = 2000 + yy
        return f"{year:04d}-{mon:02d}-{dd:02d}"

    m = re.match(r"^(\d{2})-([A-Za-z]{3})-(\d{2})$", s)
    if m:
        dd = int(m.group(1))
        mon = _MONTHS.get(m.group(2).upper())
        yy = int(m.group(3))
        if mon is None:
            return ""
        year = 2000 + yy
        return f"{year:04d}-{mon:02d}-{dd:02d}"

    m = re.match(r"^(\d{2})-([A-Za-z]{3})$", s)
    if m and default_year is not None:
        dd = int(m.group(1))
        mon = _MONTHS.get(m.group(2).upper())
        if mon is None:
            return ""
        return f"{default_year:04d}-{mon:02d}-{dd:02d}"

    return ""


def add_days_iso(iso_date: str, days: int) -> str:
    if not iso_date:
        return ""
    yyyy, mm, dd = map(int, iso_date.split("-"))
    d = date(yyyy, mm, dd) + timedelta(days=days)
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def compact_spaced_month_letters(s: str) -> str:
    """Fix spaced month abbreviations like 'D i c' -> 'Dic'."""
    return re.sub(r"\b([A-Za-z])\s+([A-Za-z])\s+([A-Za-z])\b", r"\1\2\3", s)


def parse_date_iso_loose(s: str) -> str:
    """Parse dates even when day/month/year tokens contain internal spaces like '0 2 E n e 2 4'."""
    raw = norm_space(s)
    if not raw:
        return ""

    # Fast path: already supported formats.
    direct = parse_date_iso(raw)
    if direct:
        return direct

    compact = re.sub(r"\s+", "", raw)
    m = re.search(r"(\d{1,2})([A-Za-z]{3})(\d{2})", compact)
    if m:
        return parse_date_iso(f"{m.group(1)} {m.group(2)} {m.group(3)}")

    m = re.search(r"(\d{2})-([A-Za-z]{3})-(\d{2})", compact)
    if m:
        return parse_date_iso(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")

    return ""


_INSTALLMENT_RE = re.compile(r"\bC\.(\d{1,2})/(\d{1,2})\b|\b(\d{1,2})/(\d{1,2})\b")


def extract_installments(s: str) -> tuple[str, int | None, int | None]:
    """Extract installment info like 'C.07/18' or '07/18' from a description."""
    text = norm_space(s)
    installment_number = installment_total = None
    for m in _INSTALLMENT_RE.finditer(text):
        a = m.group(1) or m.group(3)
        b = m.group(2) or m.group(4)
        if a and b:
            try:
                installment_number, installment_total = int(a), int(b)
            except ValueError:
                continue
    cleaned = _INSTALLMENT_RE.sub("", text)
    cleaned = norm_space(cleaned)
    return cleaned, installment_number, installment_total


_TRAILING_AMOUNTS_RE = re.compile(r"(?:\s+-?[\d.]+,\d{2}-?){1,2}\s*$")


def strip_trailing_amounts(s: str) -> str:
    return norm_space(_TRAILING_AMOUNTS_RE.sub("", s))


def extract_trailing_operation_id(s: str) -> tuple[str, str | None]:
    """Extract trailing operation/authorization ids.

    Usually 4-10 digits, sometimes with a trailing suffix like `*`, `K`, or `U`.
    """
    text = norm_space(s)
    m = re.search(r"(?:^|\s)(\d{4,10}(?:[A-Z]|\*)?)\s*$", text)
    if not m:
        return text, None
    op_id = m.group(1)
    cleaned = norm_space(text[: m.start()].rstrip("- ").strip())
    return cleaned, op_id


_PARENS_CURRENCY_AMOUNT_RE = re.compile(r"\(([^)]*?),(?:\s*)(USD|ARS|DOP),(?:\s*)[-\d.]+,\d{2}\)")


def strip_paren_currency_amount(s: str) -> str:
    """Remove embedded amounts inside parenthesis like '(USA,ARS, 4799,99)' -> '(USA,ARS)'."""
    return _PARENS_CURRENCY_AMOUNT_RE.sub(r"(\1,\2)", s)


def is_statement_commentary_line(text: str) -> bool:
    """Heuristic: ignore non-transaction lines (rates, plans, conditions, etc.)."""
    up = norm_space(text).upper()
    if not up:
        return False

    # Common finance/conditions blocks
    if any(tok in up for tok in ("TNA:", "TEA:", "CFT", "COSTO FINANCIERO", "TASA", "TIP:")):
        return True
    if "PLAN V" in up or "PAGO MINIMO" in up and "ABONANDO" in up:
        return True

    # Installment plan offers (not card purchases)
    if "CUOTAS" in up and "%" in up:
        return True
    if ("CON IVA" in up or "SIN IVA" in up) and "CUOTAS" in up and "%" in up:
        return True
    if re.search(r"\bCUOTAS?\s+DE\s+\\$", up) and ("TNA:" in up or "TEA:" in up or "CFT" in up):
        return True

    return False
