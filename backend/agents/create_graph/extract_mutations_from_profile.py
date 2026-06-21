
from __future__ import annotations
import csv
import io
import json
from typing import Any, List
from backend.agents.create_graph.model import GuessMutation
import hashlib


def extract_mutations_from_profile(profile_bytes: bytes) -> List[GuessMutation]:
    """Best-effort CSV/line parser for uploaded mutation profiles."""
    text = profile_bytes.decode("utf-8", errors="ignore").strip()
    if not text:
        return []

    rows: list[dict[str, Any]] = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for index, row in enumerate(reader, start=1):
            mutation_id = row.get("mutation_id") or hashlib.md5(
                json.dumps(row.to_dict(), sort_keys=True, default=str).encode()
            ).hexdigest()[:12]
            additional = {}
            if row.get('UniprotID'):
                additional["uniprot_ac"] = row.get('UniprotID')
            if row.get("effect"):
                additional["estimated_effect"] = row.get('effect')
            rows.append(
                {
                    "mutation_id": mutation_id,
                    "protein": row.get("protein") or row.get("gene") or row.get("Gene"),
                    "raw": row,
                    **additional
                }
            )
    except Exception:
        for index, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            rows.append(
                {
                    "mutation_id":  "mutation_"
                    + hashlib.sha256(
                        row.encode("utf-8")
                    ).hexdigest()[:16],
                    "protein": "",
                    "estimated_effect": "no_effect",
                    "raw": {"line": line},
                }
            )

    return rows