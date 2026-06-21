
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
from backend.agents.create_graph.extract_mutations_from_profile import extract_mutations_from_profile
from backend.agents.create_graph.hydrate_mutation import hydrate_mutation
from backend.agents.create_graph.extract_protein_for_mutation import extract_protein_for_mutation
from backend.agents.create_graph.extract_pathways_for_protein import extract_pathways_for_protein
from backend.agents.create_graph.process_pathways import (
    fetch_pathway_information,
)
from backend.agents.create_graph.graph import (
    init_graph,
    add_mutation_node,
    add_protein_node,
    link_mutation_to_protein,
    update_pathway) 



router = APIRouter()

def print_debug(s):
    print(s)

def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def protein_graph_id(protein: ProteinRecord) -> str:
    return (
        protein.kegg_gene_id
        or protein.kegg_ko_id
        or protein.uniprot_id
        or protein.gene_symbol
        or protein.query
    )


@router.post("/profiles/test")
def test_endpoint():
    return init_graph("test")


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

        mutations = extract_mutations_from_profile(profile_bytes)

        yield sse(
            "mutations_extracted",
            {
                "profile_id": profile_id,
                "count": len(mutations),
                "mutations": mutations,
                "message": f"Extracted {len(mutations)} mutation profiles.",
            },
        )

        profile_pathway: list[dict[str, Any]] = init_graph(profile_id)

        for mutation in mutations:
            time.sleep(1)
            hydrated_mutation = await hydrate_mutation(mutation)

            yield sse(
                "mutation_hydrated",
                {
                    "profile_id": profile_id,
                    "mutation": mutation,
                    "hydrated": hydrated_mutation.model_dump(),
                    "message": f"Hydrated mutation {mutation.get('mutation_id', '')}.",
                },
            )
            print_debug(hydrated_mutation)
            add_mutation_node(hydrated_mutation, profile_id)

            protein = None
            try:
                protein = await extract_protein_for_mutation(hydrated_mutation)
            except Exception as exc:
                yield sse(
                    "error",
                    {
                        "profile_id": profile_id,
                        "mutation": mutation,
                        "message": f"Unable to map mutation {mutation.get('mutation_id', '')} to a protein: {exc}",
                    },
                )
                continue

            yield sse(
                "protein_extracted",
                {
                    "profile_id": profile_id,
                    "mutation": mutation,
                    "protein": protein.model_dump(),
                    "message": f"Mapped mutation {mutation.get('mutation_id', '')} to protein {protein_graph_id(protein)}.",
                },
            )
            print_debug(protein)
            add_protein_node(protein, profile_id)
            link_mutation_to_protein(hydrated_mutation, protein)

            pathway_ids = await extract_pathways_for_protein(protein)
            

            yield sse(
                "pathways_extracted",
                {
                    "profile_id": profile_id,
                    "protein": protein.model_dump(),
                    "pathways": pathway_id,
                    "message": f"Found {len(pathway_id)} pathways for {protein_graph_id(protein)}.",
                },
            )

            for pathway_id in pathway_ids:
                pathway_information = await fetch_pathway_information(pathway_id)
                print_debug(pathway_information)
                update_pathway(pathway_information, profile_id)

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
