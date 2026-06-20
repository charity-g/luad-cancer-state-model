"""Backend configuration — all secrets and connection info live here, server-side.

Read from environment variables with local-dev defaults. The frontend never sees
any of this; it only talks to the FastAPI endpoints in main.py.
"""

import os

# Neo4j (same connection the loader uses)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# Anthropic — if unset, the classifier and reasoner fall back to deterministic
# stubs so the whole pipeline still runs locally without a key.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Planner generates Cypher (hard task -> capable model); reasoner synthesizes.
PLANNER_MODEL = os.environ.get("PLANNER_MODEL", "claude-opus-4-8")
REASONER_MODEL = os.environ.get("REASONER_MODEL", "claude-opus-4-8")
