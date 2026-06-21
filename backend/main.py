"""FastAPI backend — the only surface the frontend talks to.
from backend.observability import init_tracing
init_tracing()

  POST /query  {question}  -> agent report + subgraph
  GET  /graph              -> full pathway graph (for the static viz)
  GET  /health             -> liveness check

Run from the repo root:
    pip install -r backend/requirements.txt
    uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agents.traverse_graph import agent, cypher
from backend.endpoints.profiles.stream import router as profiles_router
from backend.endpoints.profiles.profile_graph import router as profile_graph_router
from backend.endpoints.protein.protein import protein_router
from backend.endpoints.harmonize import router as harmonize_router

app = FastAPI(title="LUAD Cell-State GraphRAG")

app.include_router(profiles_router)
app.include_router(profile_graph_router)
app.include_router(protein_router)
app.include_router(harmonize_router)

# Open CORS for local frontend dev. Tighten allow_origins before any deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# In production the frontend (a different origin) calls "<backend>/api/...".
# Strip the /api prefix here so every existing route keeps its bare path
# ("/query"), which also leaves the local dev proxy (it already strips /api)
# untouched. Pure ASGI (not BaseHTTPMiddleware) so it never buffers the SSE
# /profiles/stream response.
class _StripApiPrefix:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
                raw = scope.get("raw_path")
                if raw:
                    scope["raw_path"] = raw.replace(b"/api", b"", 1)
        await self.app(scope, receive, send)


app.add_middleware(_StripApiPrefix)


class QueryRequest(BaseModel):
    question: str
    profile_id: str | None = None  # active profile — used to load graph memory from Neo4j
    mutations: list[dict] = []     # uploaded sample profile (gene/effect)
    context: list[dict] = []       # selected pathway/protein context cards
    history: list[dict] = []       # prior chat turns: [{role, content}]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/graph")
def graph():
    return cypher.full_graph()


@app.post("/query")
def query(req: QueryRequest):
    return agent.run(
        req.question,
        profile_id=req.profile_id,
        mutations=req.mutations,
        context=req.context,
        history=req.history,
    )

