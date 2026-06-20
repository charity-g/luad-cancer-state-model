#!/usr/bin/env python3

"""
Download and export a set of full KEGG human pathways for Neo4j import.

The KEGG web pages the user sees are the human pathway entries listed below.
The downloadable KGML data for each pathway is:
    https://rest.kegg.jp/get/<hsa pathway id>/kgml

Outputs:
    - pathways/<hsa pathway id>/<pathway id>.html
    - pathways/<hsa pathway id>/<pathway id>.kgml.xml
    - pathways/<hsa pathway id>/<pathway id>_graph.json
    - pathways/<hsa pathway id>/<pathway id>_nodes.csv
    - pathways/<hsa pathway id>/<pathway id>_edges.csv
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://rest.kegg.jp"

PATHWAY_SPECS = [
    {"label": "EGFR tyrosine kinase inhibitor resistance", "entry_page_id": "hsa01521"},
    {"label": "MAPK signaling pathway", "entry_page_id": "hsa04010"},
    {"label": "ErbB signaling pathway", "entry_page_id": "hsa04012"},
    {"label": "Ras signaling pathway", "entry_page_id": "hsa04014"},
    {"label": "FoxO signaling pathway", "entry_page_id": "hsa04068"},
    {"label": "mTOR signaling pathway", "entry_page_id": "hsa04150"},
    {"label": "PI3K-Akt signaling pathway", "entry_page_id": "hsa04151"},
    {"label": "p53 signaling pathway", "entry_page_id": "hsa04115"},
]

ROOT_DIR = Path(__file__).resolve().parents[2]


def fetch_text(url: str) -> str:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.text


def download_entry_page(entry_page_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{entry_page_id}.html"
    html = fetch_text(f"https://www.kegg.jp/entry/{entry_page_id}")
    html_path.write_text(html, encoding="utf-8")
    return html_path


def download_kgml(entry_page_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    kgml_path = output_dir / f"{entry_page_id}.kgml.xml"
    kgml = fetch_text(f"{BASE_URL}/get/{entry_page_id}/kgml")
    kgml_path.write_text(kgml, encoding="utf-8")
    return kgml_path


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _graphics_payload(entry: ET.Element) -> dict:
    graphics = entry.find("graphics")
    if graphics is None:
        return {}

    return {
        "name": graphics.get("name"),
        "type": graphics.get("type"),
        "fgcolor": graphics.get("fgcolor"),
        "bgcolor": graphics.get("bgcolor"),
        "x": _int_or_none(graphics.get("x")),
        "y": _int_or_none(graphics.get("y")),
        "width": _int_or_none(graphics.get("width")),
        "height": _int_or_none(graphics.get("height")),
    }


def parse_kgml(kgml_path: Path, label: str, entry_page_id: str) -> tuple[list[dict], list[dict], dict]:
    root = ET.fromstring(kgml_path.read_text(encoding="utf-8"))

    nodes: list[dict] = []
    edges: list[dict] = []

    for entry in root.findall("entry"):
        entry_id = entry.get("id")
        if entry_id is None:
            continue

        node_id = f"entry_{entry_id}"
        names = (entry.get("name") or "").split()
        graphics = _graphics_payload(entry)
        node = {
            "id": node_id,
            "entry_id": _int_or_none(entry_id),
            "label": graphics.get("name") or (names[0] if names else node_id),
            "type": entry.get("type"),
            "name": entry.get("name"),
            "link": entry.get("link"),
            "graphics": graphics,
            "component_entry_ids": [
                _int_or_none(component.get("id"))
                for component in entry.findall("component")
                if component.get("id") is not None
            ],
        }
        nodes.append(node)

    for relation_idx, relation in enumerate(root.findall("relation"), start=1):
        entry1 = relation.get("entry1")
        entry2 = relation.get("entry2")
        if entry1 is None or entry2 is None:
            continue

        edges.append({
            "id": f"relation_{relation_idx}",
            "source": f"entry_{entry1}",
            "target": f"entry_{entry2}",
            "type": relation.get("type"),
            "subtypes": [
                {"name": subtype.get("name"), "value": subtype.get("value")}
                for subtype in relation.findall("subtype")
            ],
            "source_entry_id": _int_or_none(entry1),
            "target_entry_id": _int_or_none(entry2),
        })

    component_edge_idx = 0
    for entry in root.findall("entry"):
        entry_id = entry.get("id")
        if entry_id is None:
            continue

        for component in entry.findall("component"):
            component_id = component.get("id")
            if component_id is None:
                continue

            component_edge_idx += 1
            edges.append({
                "id": f"component_{component_edge_idx}",
                "source": f"entry_{entry_id}",
                "target": f"entry_{component_id}",
                "type": "component_of",
                "subtypes": [],
                "source_entry_id": _int_or_none(entry_id),
                "target_entry_id": _int_or_none(component_id),
            })

    meta = {
        "title": f"KEGG {label}",
        "entry_page": f"https://www.kegg.jp/entry/{entry_page_id}",
        "kgml_url": f"{BASE_URL}/get/{entry_page_id}/kgml",
        "reference_entry_id": entry_page_id,
        "pathway_id": entry_page_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }

    return nodes, edges, meta


def write_outputs(nodes: list[dict], edges: list[dict], meta: dict, output_dir: Path, entry_page_id: str) -> tuple[Path, Path, Path]:
    graph_json_path = output_dir / f"{entry_page_id}_graph.json"
    nodes_csv_path = output_dir / f"{entry_page_id}_nodes.csv"
    edges_csv_path = output_dir / f"{entry_page_id}_edges.csv"

    graph = {
        "meta": meta,
        "nodes": nodes,
        "edges": edges,
    }

    graph_json_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    node_rows = []
    for node in nodes:
        row = dict(node)
        row["graphics"] = json.dumps(row["graphics"], ensure_ascii=True)
        row["component_entry_ids"] = json.dumps(row["component_entry_ids"], ensure_ascii=True)
        node_rows.append(row)

    edge_rows = []
    for edge in edges:
        row = dict(edge)
        row["subtypes"] = json.dumps(row["subtypes"], ensure_ascii=True)
        edge_rows.append(row)

    pd.DataFrame(node_rows).to_csv(nodes_csv_path, index=False)
    pd.DataFrame(edge_rows).to_csv(edges_csv_path, index=False)

    return graph_json_path, nodes_csv_path, edges_csv_path


def main() -> None:
    for spec in PATHWAY_SPECS:
        entry_page_id = spec["entry_page_id"]
        label = spec["label"]
        output_dir = ROOT_DIR / "pathways" / entry_page_id

        print(f"Downloading KEGG entry page: {entry_page_id}")
        html_path = download_entry_page(entry_page_id, output_dir)

        print(f"Downloading KGML pathway: {entry_page_id}")
        kgml_path = download_kgml(entry_page_id, output_dir)

        print("Parsing KGML pathway graph...")
        nodes, edges, meta = parse_kgml(kgml_path, label, entry_page_id)
        graph_json_path, nodes_csv_path, edges_csv_path = write_outputs(
            nodes,
            edges,
            meta,
            output_dir,
            entry_page_id,
        )

        print("Done.")
        print(f"  Nodes: {len(nodes)}")
        print(f"  Edges: {len(edges)}")
        print(f"  HTML:  {html_path}")
        print(f"  KGML:  {kgml_path}")
        print(f"  JSON:  {graph_json_path}")
        print(f"  CSV:   {nodes_csv_path}")
        print(f"  CSV:   {edges_csv_path}")


if __name__ == "__main__":
    main()