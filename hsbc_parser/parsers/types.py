from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

@dataclass
class Statement:
    archivo: str
    banco: str
    origen: str  # mastercard | visa | cuenta
    numero_resumen: Optional[str]
    fecha_desde: Optional[str]
    fecha_hasta: Optional[str]
    titular_nombre: Optional[str]
    moneda: Optional[str]

@dataclass
class Transaction:
    archivo: str
    fecha: str
    descripcion: str
    moneda: str
    importe: float
    persona: str
    origen: str  # mastercard | visa | cuenta

def warn(warnings: List[Dict[str, Any]], archivo: str, level: str, code: str, message: str, context: Any = None) -> None:
    warnings.append({
        "archivo": archivo,
        "level": level,
        "code": code,
        "message": message,
        "context": context,
    })
