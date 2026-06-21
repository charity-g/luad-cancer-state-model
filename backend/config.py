"""Backend configuration — all secrets and connection info live here, server-side.

Read from environment variables with local-dev defaults. The frontend never sees
any of this; it only talks to the FastAPI endpoints in main.py.
"""

import os

# Load backend/.env if present (team drops shared Aura creds there). Explicit
# path so it works regardless of the current working directory. Soft dep.
try:
    from pathlib import Path
    from dotenv import load_dotenv

    _here = Path(__file__).resolve().parent  # backend/
    # Try backend/.env first, then fall back to project root .env
    if not load_dotenv(_here / ".env"):
        load_dotenv(_here.parent / ".env")
except ImportError:
    pass

# Neo4j connection. The URI scheme selects transport:
#   https://...            -> HTTP Query API (port 443, works on campus Wi-Fi)
#   bolt://, neo4j+s://...  -> Bolt driver (port 7687, blocked on campus)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
# Accept both the Aura convention (USERNAME/PASSWORD) and the older USER/PASS.
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD") or os.environ.get("NEO4J_PASS", "password")

# Anthropic — if unset, the classifier and reasoner fall back to deterministic
# stubs so the whole pipeline still runs locally without a key.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Planner generates Cypher (hard task -> capable model); reasoner synthesizes.
PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "claude-opus-4-8")
REASONER_MODEL = os.environ.get("REASONER_MODEL", "claude-opus-4-8")

# Therapeutic Target Database (TTD) API.
# Set TTD_BASE_URL to the real endpoint and TTD_API_KEY to your bearer token.
# When TTD_API_KEY is unset the TTD lookup is silently skipped.
TTD_BASE_URL = os.environ.get("TTD_BASE_URL", "https://api.example.org/v1")
TTD_API_KEY  = os.environ.get("TTD_API_KEY", "")
