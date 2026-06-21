
from __future__ import annotations
import time
import asyncio
import csv
import hashlib
import io
import json
from typing import Any

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse

from backend.agents.create_graph.model import MutationProteinEffect, ProteinRecord

router = APIRouter()

def print_debug(s):
    print(s)

def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def extract_mutation_profiles(profile_bytes: bytes) -> list[dict[str, Any]]:
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


def hydrate_mutation(mutation: dict[str, Any]) -> MutationProteinEffect:
    return MutationProteinEffect(
        mutation_id=str(mutation.get("mutation_id", "")),
        protein=str(mutation.get("protein", "")),
        estimated_effect=str(mutation.get("estimated_effect", "no_effect")),
        justification={
            "raw": mutation.get("raw", {}),
            "notes": mutation.get("notes", []),
        },
    )


def extract_protein_for_mutation(mutation: dict[str, Any]) -> ProteinRecord:
    protein_symbol = str(mutation.get("protein", "")).strip()
    protein_symbol = protein_symbol or "EGFR"
    return ProteinRecord(
        kegg_id=f"hsa:{protein_symbol}",
        ids={
            "mutation_id": str(mutation.get("mutation_id", "")),
            "protein_symbol": protein_symbol,
        },
        semantic={
            "estimated_effect": mutation.get("estimated_effect", "no_effect"),
            "source_mutation": mutation,
        },
    )


def extract_pathways_for_protein(protein: ProteinRecord) -> list[dict[str, Any]]:
    return [
        {
            "kegg_id": protein.kegg_id,
            "name": protein.ids.get("protein_symbol", protein.kegg_id),
            "evidence": protein.semantic.get("estimated_effect", "no_effect"),
        }
    ]


def fetch_pathway_information(pathway: dict[str, Any]) -> dict[str, Any]:
    return {
        "kegg_id": pathway.get("kegg_id", ""),
        "name": pathway.get("name", ""),
        "evidence": pathway.get("evidence", "no_effect"),
        "source": "upload-profile-stream",
    }


def update_pathway(pathway_information: dict[str, Any]) -> dict[str, Any]:
    return pathway_information


@router.post("/profiles/stream")
async def process_profile(file: UploadFile = File(...)):
    profile_bytes = await file.read()
    profile_id = hashlib.sha256(profile_bytes).hexdigest()[:16]

    async def stream():
        yield sse(
            "started",
            {
                "profile_id": profile_id,
                "message": "Profile received. Starting mutation analysis.",
            },
        )

        mutations = extract_mutation_profiles(profile_bytes)

        yield sse(
            "mutations_extracted",
            {
                "profile_id": profile_id,
                "count": len(mutations),
                "message": f"Extracted {len(mutations)} mutation profiles.",
            },
        )

        profile_pathway: list[dict[str, Any]] = []

        for mutation in mutations:
            time.sleep(1)
            hydrated_mutation = hydrate_mutation(mutation)
            
            yield sse(
                "mutation_hydrated",
                {
                    "profile_id": profile_id,
                    "mutation": mutation,
                    "hydrated": hydrated_mutation.model_dump(),
                    "message": f"Hydrated mutation {mutation.get('mutation_id', '')}.",
                },
            )

            protein = extract_protein_for_mutation(mutation)

            yield sse(
                "protein_extracted",
                {
                    "profile_id": profile_id,
                    "mutation": mutation,
                    "protein": protein.model_dump(),
                    "message": f"Mapped mutation {mutation.get('mutation_id', '')} to protein {protein.kegg_id}.",
                },
            )

            pathways = extract_pathways_for_protein(protein)

            yield sse(
                "pathways_extracted",
                {
                    "profile_id": profile_id,
                    "protein": protein.model_dump(),
                    "pathways": pathways,
                    "message": f"Found {len(pathways)} pathways for {protein.kegg_id}.",
                },
            )

            for pathway in pathways:
                pathway_information = fetch_pathway_information(pathway)
                update_pathway(pathway_information)

                profile_pathway.append(pathway_information)

                yield sse(
                    "pathway_updated",
                    {
                        "profile_id": profile_id,
                        "pathway": pathway,
                        "message": f"Updated pathway {pathway.get('kegg_id', '')}.",
                    },
                )

            await asyncio.sleep(0)

        yield sse(
            "complete",
            {
                "profile_id": profile_id,
                "profile_pathway": profile_pathway,
                "message": "Scientific reasoning workspace is ready.",
            },
        )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )