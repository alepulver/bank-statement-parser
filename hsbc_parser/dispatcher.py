from __future__ import annotations
import pdfplumber

from .parsers.mastercard import HSBCMastercardParser
from .parsers.visa import HSBCVisaParser
from .parsers.cuenta import HSBCCajaAhorroParser
from .logging_utils import get_logger

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
    """Parse an HSBC PDF.

    Args:
        pdf_path: path to the PDF
        tipo: 'visa' | 'mastercard' | 'cuenta' | None (auto)

    Returns:
        parser: parser instance used (has .statement, .transactions, .warnings)
    """
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    kind = tipo or detect_type(text)

    logger = get_logger("parse").getChild(kind)
    if kind == "cuenta":
        p = HSBCCajaAhorroParser(pdf_path, logger=logger)
    elif kind == "visa":
        p = HSBCVisaParser(pdf_path, logger=logger)
    else:
        p = HSBCMastercardParser(pdf_path, logger=logger)

    p.parse()
    return p
