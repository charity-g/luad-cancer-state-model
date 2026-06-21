"""REST endpoint for the identifier harmonization platform.

POST /harmonize          — batch-resolve mixed identifier types
GET  /harmonize/gene/{q} — resolve a single gene
GET  /harmonize/drug/{q} — resolve a single drug
GET  /harmonize/pathway/{q} — resolve a single pathway
GET  /harmonize/cache    — cache statistics
DELETE /harmonize/cache  — flush the cache (dev/testing)
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.harmonizer import harmonizer
from backend.harmonizer.models import HarmonizeRequest, HarmonizeResponse

router = APIRouter(prefix="/harmonize", tags=["harmonizer"])


@router.post("", response_model=HarmonizeResponse)
async def harmonize_batch(req: HarmonizeRequest) -> HarmonizeResponse:
    """Batch-resolve genes, variants, drugs, and pathways in one call."""
    return await harmonizer.harmonize_batch(req)


@router.get("/gene/{query}")
async def resolve_gene(query: str):
    result = await harmonizer.resolve_gene(query)
    return result.model_dump()


@router.get("/drug/{query}")
async def resolve_drug(query: str):
    result = await harmonizer.resolve_drug(query)
    return result.model_dump()


@router.get("/pathway/{query}")
async def resolve_pathway(query: str):
    result = await harmonizer.resolve_pathway(query)
    return result.model_dump()


@router.get("/cache")
def cache_stats():
    return harmonizer.cache_stats()


@router.delete("/cache")
def clear_cache():
    harmonizer.clear_cache()
    return {"cleared": True}
