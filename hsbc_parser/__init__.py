from __future__ import annotations

import logging

__all__ = ["parse_pdf", "export_csv"]

logging.getLogger("hsbc_parser").addHandler(logging.NullHandler())


def parse_pdf(*args, **kwargs):
    from .dispatcher import parse_pdf as _parse_pdf

    return _parse_pdf(*args, **kwargs)


def export_csv(*args, **kwargs):
    from .export import export_csv as _export_csv

    return _export_csv(*args, **kwargs)
