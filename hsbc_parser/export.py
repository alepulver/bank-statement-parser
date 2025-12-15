from __future__ import annotations
import csv
import json
from dataclasses import asdict
from pathlib import Path
import pandas as pd

def export_csv(parsers, out_dir: str | Path):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    statements = []
    transactions = []
    warnings = []

    for p in parsers:
        statements.append(asdict(p.statement))
        transactions.extend(asdict(t) for t in p.transactions)
        for w in p.warnings:
            # ensure json-serializable context
            if isinstance(w.get("context"), (dict, list)):
                w = dict(w)
                w["context"] = json.dumps(w["context"], ensure_ascii=False)
            warnings.append(w)

    df_s = pd.DataFrame(statements)
    df_t = pd.DataFrame(transactions)
    df_w = pd.DataFrame(
        warnings,
        columns=["archivo", "level", "code", "message", "context"],
    )

    df_s.to_csv(out / "statements.csv", index=False, quoting=csv.QUOTE_NONNUMERIC)
    df_t.to_csv(out / "transactions.csv", index=False, quoting=csv.QUOTE_NONNUMERIC)
    df_w.to_csv(out / "warnings.csv", index=False, quoting=csv.QUOTE_NONNUMERIC)

    return df_s, df_t, df_w
