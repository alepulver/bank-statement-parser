from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional
from .types import Statement, Transaction
from .types import warn as _warn

class BaseParser:
    def __init__(self, pdf_path: str, *, pages: Optional[List[str]] = None, logger: logging.Logger | None = None):
        self.pdf_path = pdf_path
        self._pages_override = pages
        self.logger = logger or logging.getLogger("hsbc_parser").getChild(self.__class__.__name__)
        self.statement: Statement | None = None
        self.transactions: List[Transaction] = []
        self.warnings: List[Dict[str, Any]] = []

    def warn(self, level: str, code: str, message: str, context: Any = None) -> None:
        archivo = (self.pdf_path or "").split("/")[-1]
        _warn(self.warnings, archivo, level, code, message, context=context, logger=self.logger)

    def parse(self) -> None:
        raise NotImplementedError
