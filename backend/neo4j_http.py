"""Neo4j HTTP Query API client (port 443).

Campus Wi-Fi blocks Bolt (7687) but allows the Aura Query API over HTTPS (443),
so this is the transport the whole team uses. Provides:

  - run_read(cypher, params) -> {rows, subgraph}   (mirrors the Bolt executor)
  - HttpSession: a minimal session with .run()/.single() so the Bolt-oriented
    loader (scripts/init_neo4j/upload_init.py) can be reused unchanged over HTTP.

A single HTTPS connection is kept alive across calls (keep-alive) so loading
thousands of statements stays reasonably fast.
"""

import base64
import http.client
import json
import time
from urllib.parse import urlparse

_QUERY_PATH = "/db/neo4j/query/v2"


class QueryAPI:
    def __init__(self, uri, user, password):
        parsed = urlparse(uri)
        self.host = parsed.netloc or parsed.path
        self._auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._conn = None

    def _connection(self):
        if self._conn is None:
            self._conn = http.client.HTTPSConnection(self.host, timeout=60)
        return self._conn

    def execute(self, cypher, params=None):
        body = json.dumps({"statement": cypher, "parameters": params or {}})
        headers = {
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        last_err = None
        for attempt in range(4):
            try:
                conn = self._connection()
                conn.request("POST", _QUERY_PATH, body=body, headers=headers)
                resp = conn.getresponse()
                raw = resp.read()
                if resp.status in (429, 502, 503, 504):  # transient — back off
                    self._conn = None
                    time.sleep(1 + attempt)
                    last_err = RuntimeError(f"{resp.status}: {raw[:200]!r}")
                    continue
                if resp.status not in (200, 202):
                    raise RuntimeError(f"Query API {resp.status}: {raw[:300]!r}")
                payload = json.loads(raw)
                if payload.get("errors"):
                    raise RuntimeError(f"Cypher error: {payload['errors']}")
                return payload
            except (http.client.HTTPException, ConnectionError, OSError) as e:
                self._conn = None  # connection dropped — reopen and retry
                last_err = e
                time.sleep(0.5 * (attempt + 1))
        raise last_err

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ---------------------------------------------------------------------------
# Value / subgraph conversion — mirror the Bolt executor's output shape.
# ---------------------------------------------------------------------------

def _is_node(v):
    return isinstance(v, dict) and "labels" in v and "properties" in v


def _is_rel(v):
    return isinstance(v, dict) and "type" in v and "startNodeElementId" in v


def _convert(v):
    if _is_node(v):
        return {"id": v["properties"].get("id"), "labels": v["labels"], **v["properties"]}
    if _is_rel(v):
        return {"type": v["type"], **v.get("properties", {})}
    if isinstance(v, list):
        return [_convert(x) for x in v]
    return v


def _subgraph(values):
    nodes, rels = {}, []

    def visit(v):
        if isinstance(v, list):
            for x in v:
                visit(x)
        elif _is_node(v):
            nodes[v["elementId"]] = {
                "id": v["properties"].get("id", v["elementId"]),
                "labels": v["labels"],
                **v["properties"],
            }
        elif _is_rel(v):
            rels.append(v)

    for row in values:
        for v in row:
            visit(v)

    def nid(eid):
        n = nodes.get(eid)
        return n["id"] if n else eid

    edges = [
        {
            "type": r["type"],
            "source": nid(r["startNodeElementId"]),
            "target": nid(r["endNodeElementId"]),
            **r.get("properties", {}),
        }
        for r in rels
    ]
    return {"nodes": list(nodes.values()), "edges": edges}


# ---------------------------------------------------------------------------
# Backend read path
# ---------------------------------------------------------------------------

_api = None


def _get_api():
    global _api
    if _api is None:
        from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
        _api = QueryAPI(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    return _api


def run_read(cypher, params=None):
    payload = _get_api().execute(cypher, params)
    data = payload.get("data", {})
    fields, values = data.get("fields", []), data.get("values", [])
    rows = [{f: _convert(v) for f, v in zip(fields, row)} for row in values]
    return {"rows": rows, "subgraph": _subgraph(values)}


# ---------------------------------------------------------------------------
# Loader reuse — a Bolt-session-shaped shim over HTTP
# ---------------------------------------------------------------------------

class HttpResult:
    def __init__(self, payload):
        data = payload.get("data", {})
        self._fields = data.get("fields", [])
        self._values = data.get("values", [])

    def __iter__(self):
        for row in self._values:
            yield {f: _convert(v) for f, v in zip(self._fields, row)}

    def single(self):
        return next(iter(self), None)


class HttpSession:
    """Drop-in for a Bolt session: supports .run(cypher, **params) and context mgmt."""

    def __init__(self, uri, user, password):
        self.api = QueryAPI(uri, user, password)

    def run(self, cypher, parameters=None, **kwargs):
        return HttpResult(self.api.execute(cypher, {**(parameters or {}), **kwargs}))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.api.close()

    def close(self):
        self.api.close()
