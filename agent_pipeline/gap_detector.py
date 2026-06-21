"""Step 3: decide whether graph lookup fully answers a mutation profile or needs ML."""

from __future__ import annotations

from typing import Any

from graph_lookup import ACTIVE_STATUSES, load_graph, mutation_to_drugs, mutation_to_pathways

# Hub/meta pathways have no drug targets by design — exclude from coverage accounting.
EXCLUDED_FROM_COVERAGE = {"crosstalk_hub"}


def _targetable_pathways(graph: dict, pathway_rows: list[dict]) -> list[dict]:
    out = []
    for p in pathway_rows:
        if not p.get("active"):
            continue
        node = graph["pathways_by_id"].get(p["id"], {})
        if node.get("status") in EXCLUDED_FROM_COVERAGE:
            continue
        out.append(p)
    return out


def _drugs_covering_pathway(graph: dict, mutation: str, pathway_id: str) -> list[str]:
    result = mutation_to_drugs(graph, mutation)
    covering = []
    for d in result["drugs"]:
        if pathway_id in d["pathways_covered"]:
            covering.append(d["drug"])
    return covering


def analyze_mutation(graph: dict, mutation: str) -> dict[str, Any]:
    pathways = mutation_to_pathways(graph, mutation)
    if pathways["unknown_mutation"]:
        return {
            "mutation": mutation,
            "unknown_mutation": True,
            "has_targetable_pathways": False,
            "fully_covered": False,
            "needs_ml_fallback": True,
            "gap_pathways": [],
            "covered_pathways": [],
            "reason": "mutation not in mutation_index",
        }

    targetable = _targetable_pathways(graph, pathways["pathways"])
    gap_pathways = []
    covered_pathways = []

    for p in targetable:
        drugs = _drugs_covering_pathway(graph, mutation, p["id"])
        row = {"id": p["id"], "label": p["label"], "covering_drugs": drugs}
        if drugs:
            covered_pathways.append(row)
        else:
            gap_pathways.append(row)

    has_targetable = len(targetable) > 0
    fully_covered = has_targetable and len(gap_pathways) == 0
    needs_ml = (not has_targetable) or (len(gap_pathways) > 0)

    if not has_targetable:
        reason = "no targetable activated pathways in graph for this mutation"
    elif gap_pathways:
        reason = f"{len(gap_pathways)} activated pathway(s) have no graph-covered drug"
    else:
        reason = "all targetable pathways have at least one drug in graph"

    return {
        "mutation": mutation,
        "gene": pathways["gene"],
        "unknown_mutation": False,
        "activated_pathways": pathways["pathways"],
        "targetable_pathways": targetable,
        "has_targetable_pathways": has_targetable,
        "fully_covered": fully_covered,
        "needs_ml_fallback": needs_ml,
        "gap_pathways": gap_pathways,
        "covered_pathways": covered_pathways,
        "reason": reason,
    }


def analyze_combo(graph: dict, mutations: list[str]) -> dict[str, Any]:
    per_mutation = [analyze_mutation(graph, m) for m in mutations]
    unknown = [m for m in per_mutation if m["unknown_mutation"]]

    combined_gaps: dict[str, dict] = {}
    combined_covered: dict[str, dict] = {}

    for m in per_mutation:
        for g in m["gap_pathways"]:
            combined_gaps.setdefault(g["id"], {**g, "from_mutations": []})["from_mutations"].append(
                m["mutation"]
            )
        for c in m["covered_pathways"]:
            combined_covered.setdefault(c["id"], {**c, "from_mutations": []})["from_mutations"].append(
                m["mutation"]
            )

    has_targetable = any(m["has_targetable_pathways"] for m in per_mutation)
    any_single_gap = any(m["needs_ml_fallback"] for m in per_mutation)
    multi_mutation = len(mutations) > 1

    needs_ml = bool(unknown) or any_single_gap or multi_mutation

    if unknown:
        reason = "unknown mutation(s) in profile"
    elif multi_mutation:
        reason = "multi-mutation combination — graph has no interaction model"
    elif not has_targetable:
        reason = "no targetable pathways across profile"
    elif combined_gaps:
        reason = f"{len(combined_gaps)} pathway gap(s) across profile"
    else:
        reason = "single mutation, fully graph-covered"

    return {
        "mutations": mutations,
        "per_mutation": per_mutation,
        "combined_gap_pathways": list(combined_gaps.values()),
        "combined_covered_pathways": list(combined_covered.values()),
        "has_targetable_pathways": has_targetable,
        "fully_covered": has_targetable and not combined_gaps and not multi_mutation and not unknown,
        "needs_ml_fallback": needs_ml,
        "reason": reason,
    }


if __name__ == "__main__":
    g = load_graph()

    cases = [
        ["EGFR L858R"],
        ["TP53 loss"],
        ["KRAS G12D"],
        ["EGFR L858R", "KRAS G12D"],
    ]

    for muts in cases:
        r = analyze_combo(g, muts)
        label = " + ".join(muts)
        print(f"\n=== {label} ===")
        print(f"  needs_ml_fallback: {r['needs_ml_fallback']}")
        print(f"  fully_covered:     {r['fully_covered']}")
        print(f"  reason:            {r['reason']}")
        if r["combined_gap_pathways"]:
            print(f"  gaps: {[g['id'] for g in r['combined_gap_pathways']]}")
