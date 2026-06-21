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

import backend.agents.classifier.graph_lookup as graph_lookup
import backend.agents.classifier.gap_detector as gap_detector
import backend.agents.classifier.ml_classifier as ml_classifier

# Lazily built and cached: loading the graph and training the (tiny) model is
# done once per process, on first use, so server startup and mutation-free
# requests stay fast.
_graph_cache = None
_model_cache = None  # (clf, encoders, pathway_support)

# The hydrated profile uses 'activating'/'inactivating'; accept the
# gain/loss-of-function synonyms too so either vocabulary routes.
_DRIVER_EFFECTS = {"activating", "gain_of_function"}
_LOF_EFFECTS = {"inactivating", "loss_of_function"}
_REAL_EFFECTS = _DRIVER_EFFECTS | _LOF_EFFECTS


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


def _variant_token(hgvs_protein, mutation_id, justification, gene="") -> str:
    """Extract the protein-level variant (e.g. ``L858R``) used in the graph's
    mutation keys, preferring the explicit hgvs_protein, then the annotation,
    then the mutation id. Tolerates ``p.L858R``, ``EGFR:p.L858R``, ``EGFR L858R``."""
    raw = hgvs_protein or ""
    if not raw and isinstance(justification, dict):
        raw = justification.get("hgvs_protein") or ""
    if not raw:
        raw = mutation_id or ""
    raw = str(raw).strip()
    # Drop a leading gene prefix ("EGFR:p.L858R" / "EGFR L858R" -> "p.L858R" / "L858R").
    if gene and raw.upper().startswith(gene.upper()):
        raw = raw[len(gene):]
    raw = raw.lstrip(" :_-")
    if raw[:2].lower() == "p.":   # "p.L858R" -> "L858R"
        raw = raw[2:]
    return raw.strip()


def _resolve_key(graph, gene, hgvs_protein, mutation_id, effect, justification):
    """Map an uploaded mutation to a graph mutation_index key.

    Returns (key, kind) where kind is 'exact', 'lof', or None when unmatched.
    We never guess a different variant of the same gene, because variant-
    specific drugs (e.g. sotorasib is KRAS G12C-only) would then be misapplied.
    """
    mi = graph["mutation_index"]
    variant = _variant_token(hgvs_protein, mutation_id, justification, gene)
    candidate = f"{gene} {variant}".strip()
    if variant and candidate in mi:
        return candidate, "exact"
    if effect in _LOF_EFFECTS and f"{gene} loss" in mi:
        return f"{gene} loss", "lof"
    return None, None


_FEATURE_KEYS = ("is_hotspot", "is_lof", "is_high_impact",
                 "oncogene_high_impact", "tsg_high_impact")


def _features(effect, explicit=None):
    """ML features. Prefer the REAL DepMap annotation flags forwarded from the
    profile (Hotspot, OncogeneHighImpact, etc. — exactly what the model was
    trained on). Fall back to a conservative heuristic from the effect call when
    those aren't available."""
    if explicit:
        return {k: bool(explicit.get(k, False)) for k in _FEATURE_KEYS}
    gof = effect in _DRIVER_EFFECTS
    lof = effect in _LOF_EFFECTS
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


def _ml_predictions(graph, gene, pathway_ids, feats):
    """Run the classifier for each pathway id. Pathway IDs (e.g. 'MAPK_signaling')
    are exactly the names the model was trained on."""
    clf, encoders, support = _model()
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


def _candidates(mutations, context):
    """Genes to route, the selected context first (it's the question's subject),
    then profile mutations. Deduped by gene, preferring whichever resolves to a
    real graph variant key so we don't lose variant-specific drugs."""
    graph = _graph()
    rows = list(context or []) + list(mutations or [])

    by_gene = {}
    for m in rows:
        # Prefer the gene symbol (HugoSymbol) forwarded from the profile; fall
        # back to the display protein / context selection.
        gene = m.get("gene") or m.get("protein")
        if not gene or gene not in graph["gene_index"]:
            continue
        effect = m.get("estimated_effect") or m.get("effect")
        features = m.get("features")
        key, kind = _resolve_key(graph, gene, m.get("hgvs_protein"),
                                 m.get("mutation_id"), effect, m.get("justification"))
        # The classifier is a fallback for REAL mutations. Route only entries with
        # genuine signal — a resolved graph variant key, a driver effect call, or
        # a real impact flag (hotspot / oncogene- or TSG-high-impact). A bare gene
        # selection with no variant, effect, or flag carries nothing to classify.
        has_flag = bool(features) and any(
            features.get(k) for k in ("is_hotspot", "oncogene_high_impact", "tsg_high_impact", "is_lof")
        )
        if not key and effect not in _REAL_EFFECTS and not has_flag:
            continue
        prev = by_gene.get(gene)
        # Keep the first (context-first order); upgrade only if a later row
        # resolves a variant key where the kept one did not.
        if prev is None or (key and not prev["key"]):
            by_gene[gene] = {"gene": gene, "effect": effect, "features": features,
                             "mutation_id": m.get("mutation_id"), "key": key, "kind": kind}
    return list(by_gene.values())


def route(mutations, context=None):
    """Per-gene drug routing: direct drugs + ML pathway-vulnerability.

    Routes the selected context protein(s) and the uploaded profile mutations.
    Returns a list of dicts; genes unknown to the drug graph are skipped.
    """
    graph = _graph()
    items = []
    for cand in _candidates(mutations, context):
        gene = cand["gene"]
        mutation_id = cand["mutation_id"]
        key, kind = cand["key"], cand["kind"]
        feats = _features(cand["effect"], cand.get("features"))

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
                "ml_predictions": _ml_predictions(graph, gene, ml_ids, feats) if not direct else [],
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
                "ml_predictions": _ml_predictions(graph, gene, [pid for pid, _ in active], feats),
                "note": "variant not in drug graph; gene-level pathway prediction only",
            })
    return items


def evidence_text(mutations, context=None):
    """Compact text block for the reasoner prompt, or '' if nothing to add."""
    items = route(mutations, context)
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
