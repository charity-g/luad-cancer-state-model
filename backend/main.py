"""FastAPI backend — the only surface the frontend talks to.

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

app = FastAPI(title="LUAD Cell-State GraphRAG")

app.include_router(profiles_router)

# Open CORS for local frontend dev. Tighten allow_origins before any deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/graph")
def graph():
    return cypher.full_graph()


@app.post("/query")
def query(req: QueryRequest):
    return agent.run(req.question)

