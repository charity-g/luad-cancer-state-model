"""Backend configuration — all secrets and connection info live here, server-side.

Read from environment variables with local-dev defaults. The frontend never sees
any of this; it only talks to the FastAPI endpoints in main.py.
"""

import os

# Load a local .env if present (team drops shared Aura creds there). Soft dep.
try:
    from dotenv import load_dotenv

    load_dotenv()
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
