from __future__ import annotations
from typing import List, Dict, Any
from .types import Statement, Transaction

class BaseParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.statement: Statement | None = None
        self.transactions: List[Transaction] = []
        self.warnings: List[Dict[str, Any]] = []

    def parse(self) -> None:
        raise NotImplementedError
