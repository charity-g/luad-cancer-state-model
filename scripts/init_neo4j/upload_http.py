#!/usr/bin/env python3
"""Load all graph sources into Neo4j over the HTTP Query API (port 443).

Same data and parsing as upload_init.py, but routed through the Aura Query API
instead of Bolt — because campus Wi-Fi blocks Bolt (7687) while allowing HTTPS
(443). Reuses upload_init's load functions via an HTTP session shim.

    NEO4J_URI=https://<id>.databases.neo4j.io \
    NEO4J_USERNAME=neo4j NEO4J_PASSWORD=... \
        python scripts/init_neo4j/upload_http.py
"""

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))            # upload_init (load functions + parsing)
sys.path.insert(0, str(ROOT / "backend"))  # neo4j_http (HttpSession)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
except ImportError:
    pass

import upload_init as ui
from neo4j_http import HttpSession

URI = os.environ["NEO4J_URI"]
USER = os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER", "neo4j")
PW = os.environ.get("NEO4J_PASSWORD") or os.environ["NEO4J_PASS"]


def main():
    print(f"Connecting (HTTP Query API): {URI}")
    sess = HttpSession(URI, USER, PW)
    t0 = time.time()
    print("Wiping database ...")
    sess.run("MATCH (n) DETACH DELETE n")
    ui.apply_schema(sess)
    ui.load_kegg_graphs(sess)
    ui.load_lung_cancer_graph(sess)
    ui.load_perturbation_layer(sess)
    ui.load_cell_lines(sess)  # skips itself if DepMap CSV is absent
    ui.print_stats(sess)
    print(f"\nDone in {time.time() - t0:.0f}s.")
    sess.close()


if __name__ == "__main__":
    main()
