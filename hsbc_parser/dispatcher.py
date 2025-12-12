from __future__ import annotations
import pdfplumber

from .parsers.mastercard import HSBCMastercardParser
from .parsers.visa import HSBCVisaParser
from .parsers.cuenta import HSBCCajaAhorroParser

def detect_type(text: str) -> str:
    up = text.upper()
    if "CAJA DE AHORRO" in up and "DETALLE DE OPERACIONES" in up:
        return "cuenta"
    if "VISA" in up:
        return "visa"
    if "MASTERCARD" in up:
        return "mastercard"
    # fallback
    return "mastercard"

def parse_pdf(pdf_path: str, tipo: str | None = None):
    """Parsea un PDF de HSBC.

    Args:
        pdf_path: ruta al PDF
        tipo: 'visa' | 'mastercard' | 'cuenta' | None (auto)

    Returns:
        parser: instancia del parser usado (tiene .statement, .transactions, .warnings)
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    kind = tipo or detect_type(text)

    if kind == "cuenta":
        p = HSBCCajaAhorroParser(pdf_path)
    elif kind == "visa":
        p = HSBCVisaParser(pdf_path)
    else:
        p = HSBCMastercardParser(pdf_path)

    p.parse()
    return p
