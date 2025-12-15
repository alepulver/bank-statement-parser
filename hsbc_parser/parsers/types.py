from __future__ import annotations
from dataclasses import dataclass
import logging
from typing import Optional, Dict, Any, List

@dataclass
class Statement:
    archivo: str
    banco: str
    origen: str  # mastercard | visa | cuenta
    fecha_desde: Optional[str]
    fecha_hasta: Optional[str]
    saldo_anterior_ars: Optional[float] = None
    saldo_anterior_usd: Optional[float] = None
    saldo_actual_ars: Optional[float] = None
    saldo_actual_usd: Optional[float] = None

@dataclass
class Transaction:
    archivo: str
    fecha: str  # ISO-8601 YYYY-MM-DD when available
    descripcion: str
    moneda: str
    importe: float
    persona: str
    origen: str  # mastercard | visa | cuenta
    operation_id: Optional[str] = None
    installment_number: Optional[int] = None
    installment_total: Optional[int] = None

def warn(
    warnings: List[Dict[str, Any]],
    archivo: str,
    level: str,
    code: str,
    message: str,
    context: Any = None,
    logger: logging.Logger | None = None,
) -> None:
    record = {
        "archivo": archivo,
        "level": level,
        "code": code,
        "message": message,
        "context": context,
    }
    warnings.append(record)

    if logger is not None:
        log_method = logger.warning
        if level.upper() in ("ERROR", "CRITICAL"):
            log_method = logger.error
        elif level.upper() == "INFO":
            log_method = logger.info

        if context is None:
            log_method("[%s] %s", code, message)
        else:
            log_method("[%s] %s | context=%r", code, message, context)
