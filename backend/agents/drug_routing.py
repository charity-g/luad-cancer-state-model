"""Drug-routing evidence — wires the agent_pipeline classifier into the chat.

For the uploaded mutation profile this runs the deterministic graph lookup
(direct-target drugs) and, where the graph has no covering drug, the ML
fallback classifier that predicts which activated pathway is a vulnerability.
The result is folded into the reasoner's prompt as extra evidence so chat
answers can cite ML predictions — it does NOT replace the Neo4j subgraph path.

The pipeline lives in the top-level ``agent_pipeline/`` package, which is run
standalone by its author with bare imports (``from graph_lookup import ...``).
We add that directory to ``sys.path`` rather than refactoring it, so their
standalone workflow keeps working.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[2] / "agent_pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

import graph_lookup  # noqa: E402  (agent_pipeline, via sys.path above)
import gap_detector  # noqa: E402
import ml_classifier  # noqa: E402

# Lazily built and cached: loading the graph and training the (tiny) model is
# done once per process, on first use, so server startup and mutation-free
# requests stay fast.
_graph_cache = None
_model_cache = None  # (clf, encoders, pathway_support)


def _graph():
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = graph_lookup.load_graph()
    return _graph_cache


def _model():
    global _model_cache
    if _model_cache is None:
        examples = ml_classifier.load_training_data()
        # train_and_evaluate / pathway_support_report print evaluation tables;
        # silence them so they don't spam the server log.
        with contextlib.redirect_stdout(io.StringIO()):
            clf, encoders = ml_classifier.train_and_evaluate(examples)
            support = ml_classifier.pathway_support_report(examples)
        _model_cache = (clf, encoders, support)
    return _model_cache


def _variant_token(mutation_id, justification) -> str:
    """Best-effort extract the protein-level variant (e.g. ``L858R``) used in
    the graph's mutation keys, from the hydrated annotation or mutation id."""
    raw = ""
    if isinstance(justification, dict):
        raw = justification.get("hgvs_protein") or ""
    if not raw:
        raw = mutation_id or ""
    raw = str(raw)
    if ":" in raw:           # "EGFR:p.L858R" -> "p.L858R"
        raw = raw.split(":", 1)[1]
    raw = raw.strip()
    if raw[:2].lower() == "p.":   # "p.L858R" -> "L858R"
        raw = raw[2:]
    return raw.strip()


def _resolve_key(graph, gene, mutation_id, effect, justification):
    """Map an uploaded mutation to a graph mutation_index key.

    Returns (key, kind) where kind is 'exact', 'lof', or None when unmatched.
    We never guess a different variant of the same gene, because variant-
    specific drugs (e.g. sotorasib is KRAS G12C-only) would then be misapplied.
    """
    mi = graph["mutation_index"]
    variant = _variant_token(mutation_id, justification)
    candidate = f"{gene} {variant}".strip()
    if variant and candidate in mi:
        return candidate, "exact"
    if effect == "loss_of_function" and f"{gene} loss" in mi:
        return f"{gene} loss", "lof"
    return None, None


def _features(effect):
    """Mutation-level ML features from the hydrated effect call. Conservative
    heuristics: gain-of-function driver calls behave like activating hotspots,
    which is the model's strongest signal."""
    gof = effect == "gain_of_function"
    lof = effect == "loss_of_function"
    high_impact = gof or lof
    return {
        "is_hotspot": gof,
        "is_lof": lof,
        "is_high_impact": high_impact,
        "oncogene_high_impact": high_impact,  # role gate applied inside the model
        "tsg_high_impact": high_impact,
    }


def _gene_active_pathways(graph, gene):
    """[(pathway_id, label)] for the gene's pathways that are active/enriched."""
    out = []
    for pid in graph["gene_index"].get(gene, []):
        node = graph["pathways_by_id"].get(pid)
        if node and node.get("status") in graph_lookup.ACTIVE_STATUSES:
            out.append((pid, node.get("label", pid)))
    return out


def _ml_predictions(graph, gene, pathway_ids, effect):
    """Run the classifier for each pathway id. Pathway IDs (e.g. 'MAPK_signaling')
    are exactly the names the model was trained on."""
    clf, encoders, support = _model()
    feats = _features(effect)
    preds = []
    for pid in pathway_ids:
        node = graph["pathways_by_id"].get(pid) or {}
        out = ml_classifier.predict_pathway_vulnerability(
            clf, encoders, gene, pid, support, **feats
        )
        preds.append({
            "pathway_id": pid,
            "pathway": node.get("label", pid),
            "predicted_vulnerable": out["predicted_vulnerable"],
            "probability": out["probability"],
            "data_support_level": out["data_support_level"],
        })
    # Most actionable (vulnerable, high probability) first.
    preds.sort(key=lambda p: (not p["predicted_vulnerable"], -p["probability"]))
    return preds


def route(mutations):
    """Per-mutation drug routing: direct drugs + ML pathway-vulnerability.

    Returns a list of dicts; mutations that map to no known gene are skipped.
    """
    if not mutations:
        return []
    graph = _graph()
    items = []
    for m in mutations:
        gene = m.get("protein")
        if not gene or gene not in graph["gene_index"]:
            continue
        effect = m.get("estimated_effect") or m.get("effect")
        mutation_id = m.get("mutation_id")
        key, kind = _resolve_key(graph, gene, mutation_id, effect, m.get("justification"))

        if key:
            cov = gap_detector.check_coverage(graph, key)
            direct = sorted({d["drug"] for d in cov.direct_drugs})
            gap_ids = list(cov.gap_pathway_ids)
            # ML adds value where the graph has a gap; if there's none but the
            # mutation still has targetable pathways, predict over those.
            ml_ids = gap_ids or [p["id"] for p in cov.pathways
                                 if p["status"] in gap_detector.TARGETABLE_STATUSES]
            items.append({
                "mutation": key,
                "gene": gene,
                "match": kind,
                "direct_drugs": direct,
                "ml_predictions": _ml_predictions(graph, gene, ml_ids, effect) if not direct else [],
            })
        else:
            # Variant not in the drug graph — still offer gene-level pathway ML,
            # but make no variant-specific drug claim.
            active = _gene_active_pathways(graph, gene)
            items.append({
                "mutation": f"{gene} ({mutation_id})" if mutation_id else gene,
                "gene": gene,
                "match": None,
                "direct_drugs": [],
                "ml_predictions": _ml_predictions(graph, gene, [pid for pid, _ in active], effect),
                "note": "variant not in drug graph; gene-level pathway prediction only",
            })
    return items


def evidence_text(mutations):
    """Compact text block for the reasoner prompt, or '' if nothing to add."""
    items = route(mutations)
    if not items:
        return ""
    lines = [
        "DRUG-ROUTING EVIDENCE (deterministic graph drug lookup + ML fallback "
        "classifier trained on DepMap LUAD data). Cite direct drugs as graph "
        "lookups and pathway-vulnerability calls explicitly as ML-predicted "
        "(with probability and data support level):",
    ]
    for it in items:
        if it["direct_drugs"]:
            lines.append(
                f"- {it['mutation']}: direct-target drug(s) in graph: "
                f"{', '.join(it['direct_drugs'])}."
            )
            continue
        vuln = [p for p in it["ml_predictions"] if p["predicted_vulnerable"]]
        head = f"- {it['mutation']}: no direct-target drug in the graph for this variant."
        if vuln:
            preds = "; ".join(
                f"{p['pathway']} (ML p={p['probability']}, support={p['data_support_level']})"
                for p in vuln[:4]
            )
            lines.append(f"{head} ML fallback predicts vulnerable pathway(s): {preds}.")
        elif it["ml_predictions"]:
            best = it["ml_predictions"][0]
            lines.append(
                f"{head} ML fallback predicts no clearly vulnerable pathway "
                f"(top: {best['pathway']} p={best['probability']})."
            )
        else:
            lines.append(head)
    return "\n".join(lines)
