
from __future__ import annotations
import csv
import io
from typing import Any


def extract_mutations_from_profile(profile_bytes: bytes) -> list[dict[str, Any]]:
    """Best-effort CSV/line parser for uploaded mutation profiles."""
    text = profile_bytes.decode("utf-8", errors="ignore").strip()
    if not text:
        return []

    rows: list[dict[str, Any]] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for index, row in enumerate(reader, start=1):
            mutation_id = row.get("mutation_id") or row.get("id") or row.get("MutationID")
            rows.append(
                {
                    "mutation_id": mutation_id or f"mutation_{index}",
                    "protein": row.get("protein") or row.get("gene") or row.get("Gene") or "",
                    "estimated_effect": row.get("estimated_effect") or row.get("effect") or "no_effect",
                    "raw": row,
                }
            )
    except Exception:
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            rows.append(
                {
                    "mutation_id": f"mutation_{index}",
                    "protein": "",
                    "estimated_effect": "no_effect",
                    "raw": {"line": line},
                }
            )

    return rows