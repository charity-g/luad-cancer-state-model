
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
from backend.agents.create_graph.extract_pathways_for_protein import extract_pathways_for_protein_async as extract_pathways_for_protein
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
        print_debug("@stream started")

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
        print_debug("@stream mutations_extracted")

        try:
            profile_pathway: list[dict[str, Any]] = await asyncio.to_thread(init_graph, profile_id)
        except Exception as exc:
            yield sse("graph_warning", {"profile_id": profile_id, "message": f"Graph init failed (Neo4j unreachable?): {exc}"})
            profile_pathway = []
        
        print_debug("@stream profile_pathway created")

        pathway_ids_set = set()
        for mutation in mutations:
            await asyncio.sleep(1)
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
            try:
                await asyncio.to_thread(add_mutation_node, hydrated_mutation, profile_id)
            except Exception as exc:
                print_debug(f"Graph write failed for mutation {mutation.get('mutation_id', '')}: {exc}")

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
            try:
                await asyncio.to_thread(add_protein_node, protein, profile_id)
                await asyncio.to_thread(link_mutation_to_protein, hydrated_mutation, protein)
            except Exception as exc:
                print_debug(f"Graph write failed for protein {protein_graph_id(protein)}: {exc}")

            pathway_ids = await extract_pathways_for_protein(protein)
            
            yield sse(
                "pathways_extracted",
                {
                    "profile_id": profile_id,
                    "protein": protein.model_dump(),
                    "pathways": pathway_ids,
                    "message": f"Found {len(pathway_ids)} pathways for {protein_graph_id(protein)}.",
                },
            )

            for pw_id in pathway_ids:
                pathway_ids_set.add(pw_id)
                
        for pw_id in list(pathway_ids_set):
            pathway_information = await fetch_pathway_information(pw_id)
            try:
                await asyncio.to_thread(update_pathway, pathway_information, profile_id)
            except Exception as exc:
                print_debug(f"Graph write failed for pathway {pw_id}: {exc}")

            profile_pathway.append(pathway_information)

            yield sse(
                "pathway_updated",
                {
                    "profile_id": profile_id,
                    "pathway": pathway_information,
                    "message": f"Updated pathway {pathway_information.get('pathway_id', pw_id)}.",
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
