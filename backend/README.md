# Backend

FastAPI service for the LUAD Cell-State GraphRAG backend.

The application entrypoint is [backend/main.py](main.py), which exposes:

- `GET /health`
- `GET /graph`
- `POST /query`
- `POST /profiles/stream`

## Prerequisites

- Python 3.11+ recommended
- A virtual environment in the repo, for example `.venv`
- Neo4j running locally or remotely
- Optional: `ANTHROPIC_API_KEY` for live LLM reasoning

## Install

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

## Environment Variables

The backend reads these variables from the environment:

- `NEO4J_URI` - Neo4j connection URI, for example `bolt://localhost:7687` or `neo4j+s://<aura_id>.databases.neo4j.io`
- `NEO4J_USER` - Neo4j username, usually `neo4j`
- `NEO4J_PASSWORD` - Neo4j password
- `ANTHROPIC_API_KEY` - optional; enables live Claude-backed reasoning
- `PLANNER_MODEL` - optional; defaults to `claude-opus-4-8`
- `REASONER_MODEL` - optional; defaults to `claude-opus-4-8`

Example PowerShell session:

```powershell
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "password"
# optional
$env:ANTHROPIC_API_KEY = "..."
```

## Run

Start the API from the repo root:

```powershell
uvicorn backend.main:app --reload
```

If you are already inside the `backend` folder, use:

```powershell
uvicorn main:app --reload
```

The server typically runs at `http://127.0.0.1:8000`.

## API

### Health

```http
GET /health
```

Returns:

```json
{"status": "ok"}
```

### Graph

```http
GET /graph
```

Returns the full Neo4j graph subgraph used by the frontend.

### Query

```http
POST /query
```

Body:

```json
{"question": "What pathways are active in LUAD?"}
```

Returns the agent response plus graph context.

### Profile stream

```http
POST /profiles/stream
```

Uploads a profile file and streams progress updates as server-sent events.

## Tests

Run the backend test suite from the repo root:

```powershell
pytest backend\tests
```

## Notes

- The backend includes a deterministic fallback path when `ANTHROPIC_API_KEY` is not set.
- The Neo4j connection settings are shared with the graph-reading code in `backend/agents/traverse_graph`.