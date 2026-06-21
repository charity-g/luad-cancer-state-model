"""Pathway Graph Builder — transforms pathway JSON into a protein/gene interaction graph.

Implements the tools defined in pathway_graph_agent.json:
  Parse_Pathway_JSON -> Extract_Gene_Nodes -> Build_Interaction_Graph
  -> Annotate_Graph -> Export_Graph
"""

import json
from collections import defaultdict
from pathlib import Path

REQUIRED_NODE_FIELDS = {"id", "label", "type", "key_genes"}
REQUIRED_EDGE_FIELDS = {"id", "source", "target", "type"}
VALID_NODE_TYPES = {"pathway", "gene"}
VALID_EDGE_TYPES = {
    "crosstalk", "shared_DEG", "activates", "represses", "downstream_of",
}
VALID_STATUSES = {"activated", "repressed", "crosstalk_hub", "nsclc_enriched"}


def parse_pathway_json(file_path: str, validate_strict: bool = True) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    meta = data.get("meta", {})

    if validate_strict:
        node_ids = {n["id"] for n in nodes if "id" in n}
        for i, node in enumerate(nodes):
            missing = REQUIRED_NODE_FIELDS - set(node.keys())
            if missing:
                errors.append(f"Node {i}: missing fields {missing}")
            if node.get("type") and node["type"] not in VALID_NODE_TYPES:
                errors.append(f"Node {i}: unknown type '{node['type']}'")

        for i, edge in enumerate(edges):
            missing = REQUIRED_EDGE_FIELDS - set(edge.keys())
            if missing:
                errors.append(f"Edge {i}: missing fields {missing}")
            if edge.get("source") not in node_ids:
                errors.append(f"Edge {i} ({edge.get('id')}): source '{edge.get('source')}' not in nodes")
            if edge.get("target") not in node_ids:
                errors.append(f"Edge {i} ({edge.get('id')}): target '{edge.get('target')}' not in nodes")

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": meta,
        "validation_errors": errors,
    }


def extract_gene_nodes(parsed_data: dict, include_gene_ids: bool = True, deduplicate: bool = True) -> list[dict]:
    gene_map: dict[str, dict] = {}

    for pathway_node in parsed_data["nodes"]:
        if pathway_node.get("type") != "pathway":
            continue
        pathway_id = pathway_node["id"]
        status = pathway_node.get("status")

        for gene_symbol in pathway_node.get("key_genes", []):
            if gene_symbol in gene_map:
                gene_map[gene_symbol]["properties"]["pathway_memberships"].append(pathway_id)
                if status and status not in gene_map[gene_symbol]["properties"].get("inherited_statuses", []):
                    gene_map[gene_symbol]["properties"]["inherited_statuses"].append(status)
            else:
                gene_map[gene_symbol] = {
                    "id": f"gene_{gene_symbol}",
                    "label": gene_symbol,
                    "type": "gene",
                    "status": None,
                    "properties": {
                        "pathway_memberships": [pathway_id],
                        "inherited_statuses": [status] if status else [],
                        "degree_centrality": 0.0,
                        "is_hub": False,
                    },
                }

    for edge in parsed_data["edges"]:
        for gene_symbol in edge.get("shared_genes", []):
            gene_ids = edge.get("gene_ids", [])
            if gene_symbol not in gene_map:
                gene_map[gene_symbol] = {
                    "id": f"gene_{gene_symbol}",
                    "label": gene_symbol,
                    "type": "gene",
                    "status": None,
                    "properties": {
                        "pathway_memberships": [],
                        "inherited_statuses": [],
                        "degree_centrality": 0.0,
                        "is_hub": False,
                    },
                }
            if include_gene_ids and gene_ids:
                idx = edge["shared_genes"].index(gene_symbol)
                if idx < len(gene_ids):
                    gene_map[gene_symbol]["properties"]["gene_id"] = gene_ids[idx]

    return list(gene_map.values())


def build_interaction_graph(
    pathway_nodes: list[dict],
    gene_nodes: list[dict],
    edges: list[dict],
    edge_types_filter: list[str] | None = None,
    min_shared_genes: int = 0,
) -> dict:
    all_nodes = []
    node_id_set = set()

    for pn in pathway_nodes:
        node = {
            "id": pn["id"],
            "label": pn.get("label", pn["id"]),
            "type": "pathway",
            "status": pn.get("status"),
            "properties": {
                "kegg_id": pn.get("kegg_id"),
                "q_value": pn.get("q_value"),
                "deg_count": pn.get("deg_count"),
                "impact_factor": pn.get("impact_factor"),
                "description": pn.get("description"),
            },
        }
        all_nodes.append(node)
        node_id_set.add(pn["id"])

    for gn in gene_nodes:
        all_nodes.append(gn)
        node_id_set.add(gn["id"])

    all_edges = []
    edge_counter = 0

    for edge in edges:
        if edge_types_filter and edge["type"] not in edge_types_filter:
            continue
        shared = edge.get("shared_genes", [])
        if len(shared) < min_shared_genes:
            continue
        if edge["source"] not in node_id_set or edge["target"] not in node_id_set:
            continue

        all_edges.append({
            "id": edge.get("id", f"pe_{edge_counter}"),
            "source": edge["source"],
            "target": edge["target"],
            "type": edge["type"],
            "properties": {
                "shared_genes": shared,
                "interaction_weight": len(shared),
                "description": edge.get("description", ""),
            },
        })
        edge_counter += 1

    for gn in gene_nodes:
        for pathway_id in gn["properties"].get("pathway_memberships", []):
            if pathway_id in node_id_set:
                all_edges.append({
                    "id": f"mem_{gn['id']}_{pathway_id}",
                    "source": gn["id"],
                    "target": pathway_id,
                    "type": "MEMBER_OF",
                    "properties": {
                        "shared_genes": [],
                        "interaction_weight": 1,
                        "description": f"{gn['label']} is a key gene in {pathway_id}",
                    },
                })

    gene_to_edges: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        for gene in edge.get("shared_genes", []):
            gene_to_edges[gene].append(edge["id"])

    gene_cooccurrence: dict[tuple, set] = defaultdict(set)
    for edge in edges:
        shared = edge.get("shared_genes", [])
        for i, g1 in enumerate(shared):
            for g2 in shared[i + 1:]:
                pair = tuple(sorted([g1, g2]))
                gene_cooccurrence[pair].add(edge["id"])

    for (g1, g2), edge_ids in gene_cooccurrence.items():
        gid1, gid2 = f"gene_{g1}", f"gene_{g2}"
        if gid1 in node_id_set and gid2 in node_id_set:
            all_edges.append({
                "id": f"interact_{g1}_{g2}",
                "source": gid1,
                "target": gid2,
                "type": "INTERACTS_WITH",
                "properties": {
                    "shared_genes": [g1, g2],
                    "interaction_weight": len(edge_ids),
                    "description": f"{g1} and {g2} co-occur in {len(edge_ids)} pathway interaction(s)",
                },
            })

    return {
        "nodes": all_nodes,
        "edges": all_edges,
        "stats": {
            "total_nodes": len(all_nodes),
            "pathway_nodes": sum(1 for n in all_nodes if n["type"] == "pathway"),
            "gene_nodes": sum(1 for n in all_nodes if n["type"] == "gene"),
            "total_edges": len(all_edges),
        },
    }


def annotate_graph(graph: dict) -> dict:
    degree: dict[str, int] = defaultdict(int)
    for edge in graph["edges"]:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1

    max_degree = max(degree.values()) if degree else 1
    hub_genes = []

    for node in graph["nodes"]:
        d = degree.get(node["id"], 0)
        centrality = d / max_degree if max_degree > 0 else 0
        node["properties"]["degree_centrality"] = round(centrality, 4)
        node["properties"]["degree"] = d
        node["properties"]["is_hub"] = d > 3

        if node["type"] == "gene" and d > 3:
            hub_genes.append({"symbol": node["label"], "degree": d})

    hub_genes.sort(key=lambda x: x["degree"], reverse=True)
    graph["stats"]["hub_genes"] = [h["symbol"] for h in hub_genes]
    graph["stats"]["hub_details"] = hub_genes

    return graph


def export_graph(graph: dict, fmt: str = "d3_json") -> dict:
    if fmt == "d3_json":
        return _export_d3(graph)
    if fmt == "neo4j_cypher":
        return _export_neo4j(graph)
    if fmt == "adjacency_list":
        return _export_adjacency(graph)
    return {"error": f"Unsupported format: {fmt}. Supported: d3_json, neo4j_cypher, adjacency_list"}


def _export_d3(graph: dict) -> dict:
    status_colors = {
        "activated": "#1D9E75",
        "repressed": "#E24B4A",
        "crosstalk_hub": "#7F77DD",
        "nsclc_enriched": "#BA7517",
    }
    d3_nodes = []
    for node in graph["nodes"]:
        d3_node = {
            "id": node["id"],
            "label": node["label"],
            "group": node["type"],
            "radius": 6 + (node["properties"].get("degree", 1) * 2) if node["type"] == "gene" else 10 + (node["properties"].get("degree", 1) * 1.5),
            "color": status_colors.get(node.get("status"), "#4a5568"),
        }
        d3_node.update(node["properties"])
        d3_nodes.append(d3_node)

    d3_links = []
    for edge in graph["edges"]:
        d3_links.append({
            "source": edge["source"],
            "target": edge["target"],
            "type": edge["type"],
            "weight": edge["properties"].get("interaction_weight", 1),
            "label": ", ".join(edge["properties"].get("shared_genes", [])),
        })

    return {
        "output": {"nodes": d3_nodes, "links": d3_links},
        "summary": (
            f"D3 graph: {len(d3_nodes)} nodes, {len(d3_links)} links. "
            f"Hub genes: {', '.join(graph['stats'].get('hub_genes', []))}"
        ),
    }


def _export_neo4j(graph: dict) -> dict:
    statements = []
    for node in graph["nodes"]:
        label = "Pathway" if node["type"] == "pathway" else "Gene"
        props = {k: v for k, v in node.get("properties", {}).items() if v is not None}
        props["label"] = node["label"]
        if node.get("status"):
            props["status"] = node["status"]
        props_str = ", ".join(f"{k}: {json.dumps(v)}" for k, v in props.items())
        statements.append(f'CREATE (:{label} {{id: "{node["id"]}", {props_str}}})')

    for edge in graph["edges"]:
        rel_type = edge["type"].upper().replace(" ", "_")
        props = edge.get("properties", {})
        props_clean = {k: v for k, v in props.items() if v is not None and v != ""}
        props_str = ""
        if props_clean:
            inner = ", ".join(f"{k}: {json.dumps(v)}" for k, v in props_clean.items())
            props_str = f" {{{inner}}}"
        statements.append(
            f'MATCH (a {{id: "{edge["source"]}"}}), (b {{id: "{edge["target"]}"}}) '
            f"CREATE (a)-[:{rel_type}{props_str}]->(b)"
        )

    return {
        "output": "\n".join(statements),
        "summary": f"Generated {len(statements)} Cypher statements ({len(graph['nodes'])} nodes, {len(graph['edges'])} relationships)",
    }


def _export_adjacency(graph: dict) -> dict:
    adj: dict[str, list[dict]] = defaultdict(list)
    for edge in graph["edges"]:
        adj[edge["source"]].append({
            "target": edge["target"],
            "type": edge["type"],
            "weight": edge["properties"].get("interaction_weight", 1),
        })
    return {
        "output": dict(adj),
        "summary": f"Adjacency list: {len(adj)} source nodes",
    }


def query_subgraph(
    graph: dict,
    query: str,
    max_hops: int = 2,
    edge_type_filter: list[str] | None = None,
    status_filter: str | None = None,
) -> dict:
    query_lower = query.lower()
    seed_ids = set()
    for node in graph["nodes"]:
        if (query_lower in node["id"].lower()
                or query_lower in node["label"].lower()
                or query_lower in node.get("label", "").lower()):
            seed_ids.add(node["id"])
        if node["type"] == "gene" and query.upper() == node["label"]:
            seed_ids.add(node["id"])

    if not seed_ids:
        return {
            "subgraph": {"nodes": [], "edges": []},
            "explanation": f"No nodes matched query '{query}'.",
        }

    reachable = set(seed_ids)
    frontier = set(seed_ids)
    edge_index = defaultdict(list)
    for edge in graph["edges"]:
        edge_index[edge["source"]].append(edge)
        edge_index[edge["target"]].append(edge)

    for _ in range(max_hops):
        next_frontier = set()
        for nid in frontier:
            for edge in edge_index[nid]:
                if edge_type_filter and edge["type"] not in edge_type_filter:
                    continue
                neighbor = edge["target"] if edge["source"] == nid else edge["source"]
                if neighbor not in reachable:
                    next_frontier.add(neighbor)
        reachable |= next_frontier
        frontier = next_frontier
        if not frontier:
            break

    sub_nodes = [n for n in graph["nodes"] if n["id"] in reachable]
    if status_filter:
        sub_nodes = [n for n in sub_nodes if n.get("status") == status_filter]
        reachable = {n["id"] for n in sub_nodes}

    sub_edges = [
        e for e in graph["edges"]
        if e["source"] in reachable and e["target"] in reachable
    ]

    return {
        "subgraph": {"nodes": sub_nodes, "edges": sub_edges},
        "explanation": (
            f"Found {len(seed_ids)} seed node(s) for '{query}', expanded {max_hops} hops. "
            f"Subgraph: {len(sub_nodes)} nodes, {len(sub_edges)} edges."
        ),
    }


def run(file_path: str, output_format: str = "d3_json", query: str | None = None) -> dict:
    parsed = parse_pathway_json(file_path)
    if parsed.get("error"):
        return {
            "response_type": "validation_error",
            "message_to_user": parsed["error"],
            "graph": None,
            "stats": None,
        }

    if parsed["validation_errors"]:
        return {
            "response_type": "validation_error",
            "message_to_user": f"Validation failed with {len(parsed['validation_errors'])} error(s).",
            "errors": parsed["validation_errors"],
            "graph": None,
            "stats": None,
        }

    gene_nodes = extract_gene_nodes(parsed)
    graph = build_interaction_graph(parsed["nodes"], gene_nodes, parsed["edges"])
    graph = annotate_graph(graph)

    if query:
        sub = query_subgraph(graph, query)
        sub_graph = sub["subgraph"]
        sub_graph["stats"] = {
            "total_nodes": len(sub_graph["nodes"]),
            "pathway_nodes": sum(1 for n in sub_graph["nodes"] if n["type"] == "pathway"),
            "gene_nodes": sum(1 for n in sub_graph["nodes"] if n["type"] == "gene"),
            "total_edges": len(sub_graph["edges"]),
            "hub_genes": [n["label"] for n in sub_graph["nodes"] if n.get("properties", {}).get("is_hub")],
        }
        exported = export_graph(sub_graph, output_format)
        return {
            "response_type": "graph_result",
            "message_to_user": sub["explanation"],
            "graph": sub_graph,
            "exported": exported,
            "stats": sub_graph["stats"],
        }

    exported = export_graph(graph, output_format)
    return {
        "response_type": "graph_result",
        "message_to_user": exported["summary"],
        "graph": {"nodes": graph["nodes"], "edges": graph["edges"]},
        "exported": exported,
        "stats": graph["stats"],
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "/Users/shrutishah/AIHackathon2026/luad-cancer-state-model/pathways/lung_cancer_pathways_graph.json"
    fmt = sys.argv[2] if len(sys.argv) > 2 else "d3_json"
    q = sys.argv[3] if len(sys.argv) > 3 else None

    result = run(path, fmt, q)
    print(json.dumps(result, indent=2, default=str))


'''Lang graph and lang chain, knowledge base, knowledge graph 
- terminology should be in your knowledge base 
- iterativ modeling 
- build out the function then develop the claude skill, multiple protein to gene mapping 
- ask claude to develop the skill
- using this skill map this protein 
- graph function to retrieve knowledge base - creating tool to call it 
- build own MCP - knowledge base built on it
- 
- main orchestrator 
- call a tool 
- while loop of a chat bot - functoins it could call'''

