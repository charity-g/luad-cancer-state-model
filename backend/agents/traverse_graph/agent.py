"""Agent orchestration — the single seam the backend wraps.

run(question, profile_id, mutations, context, history) -> {
    question, cypher, plan_source, mode, report, verdict, subgraph, rows,
    cited_pathways, drug_routing, ttd_drugs
}

Two-mode pipeline, selected by planner.classify(question):

  lookup  — pure information retrieval ("show me", "list", "what is X")
            LLM generates Cypher → execute → graph + 1-3 sentence summary.
            No heavy reasoning; the Agent Graph IS the answer.

  reason  — mechanistic / intervention question ("should I inhibit X?",
            "how does TP53 loss cause resistance?")
            Full plan → execute → reasoner pipeline as before.

When profile_id is supplied the stored Neo4j profile graph is fetched and
injected as grounded memory into both the planner and the reasoner.
If no profile_id is given we fall back to the in-memory SSE mutations list.
"""

import backend.neo4j_http as neo4j_http
from backend.agents import drug_routing, ttd, ttd_writer
from backend.agents.traverse_graph import cypher, planner, reasoner


def _fetch_profile_memory(profile_id: str) -> str:
    """Query the stored profile subgraph and format it as a plain-text block
    to ground the planner and reasoner in the patient's actual mutations,
    affected proteins, and implicated pathways."""
    try:
        result = neo4j_http.run_read(
            """
            MATCH (prof:Profile {profile_id: $pid})
            OPTIONAL MATCH (prof)-[:HAS_MUTATION]->(m:Mutation)
            OPTIONAL MATCH (m)-[:AFFECTS]->(p:Protein)
            OPTIONAL MATCH (p)-[:INVOLVED_IN]->(pw:Pathway)
            RETURN m.mutation_id    AS mutation_id,
                   m.estimated_effect AS effect,
                   p.gene_symbol    AS protein,
                   pw.name          AS pathway
            """,
            {"pid": profile_id},
        )
    except Exception:
        return ""

    rows = result.get("rows") or []
    if not rows:
        return ""

    mut_effect: dict[str, str] = {}
    mut_proteins: dict[str, set[str]] = {}
    protein_pathways: dict[str, set[str]] = {}
    for row in rows:
        mid = row.get("mutation_id") or ""
        eff = row.get("effect") or "uncertain"
        prot = row.get("protein") or ""
        pw = row.get("pathway") or ""
        if mid:
            mut_effect.setdefault(mid, eff)
            mut_proteins.setdefault(mid, set())
            if prot:
                mut_proteins[mid].add(prot)
        if prot and pw:
            protein_pathways.setdefault(prot, set()).add(pw)

    lines = [f"STORED PROFILE [{profile_id}]:"]
    for mid, prots in mut_proteins.items():
        eff = mut_effect.get(mid, "uncertain")
        prot_strs = []
        for pr in sorted(prots):
            pws = protein_pathways.get(pr, set())
            pw_str = f" → {', '.join(sorted(pws))}" if pws else ""
            prot_strs.append(f"{pr}{pw_str}")
        lines.append(f"  {mid} ({eff}): {'; '.join(prot_strs) or 'no proteins linked'}")

    return "\n".join(lines)


def _profile_text(mutations, context, profile_memory: str = ""):
    # The user's current selection (context) is the PRIMARY subject; the stored
    # profile graph (profile_memory) or in-memory SSE mutations are background.
    parts = []

    if profile_memory:
        # Stored graph from Neo4j — complete, persisted, authoritative.
        parts.append(profile_memory)
    else:
        muts = []
        for m in mutations or []:
            name = m.get("protein") or m.get("mutation_id") or "?"
            eff = m.get("estimated_effect") or m.get("effect") or "?"
            muts.append(f"{name} ({eff})")
        if muts:
            parts.append(
                "Background sample mutations (context only, not the subject unless asked): "
                + "; ".join(muts)
            )

    proteins = [c["protein"] for c in (context or []) if c.get("protein")]
    if proteins:
        parts.append(
            f"PRIMARY SUBJECT: {', '.join(proteins)} (the user's current selection). "
            f"Interpret 'this'/'it' as {proteins[0]} unless the question names "
            f"something else. Answer about the PRIMARY SUBJECT."
        )

    return "\n".join(parts)


def _history_text(history):
    lines = []
    for turn in (history or [])[-6:]:
        role = turn.get("role", "?")
        content = (turn.get("content") or "").strip()[:500]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _enrich_edges(subgraph):
    """Add every relationship that exists among the subgraph's nodes."""
    ids = [n["id"] for n in subgraph["nodes"] if n.get("id")]
    if len(ids) < 2:
        return subgraph
    extra = cypher.run_read(
        "MATCH (a)-[r]->(b) WHERE elementId(a) IN $ids AND elementId(b) IN $ids "
        "RETURN a, r, b",
        {"ids": ids},
    )["subgraph"]
    nodes_by = {n["id"]: n for n in subgraph["nodes"]}
    for n in extra["nodes"]:
        nodes_by.setdefault(n["id"], n)
    seen = {(e["source"], e["target"], e["type"]) for e in subgraph["edges"]}
    edges = list(subgraph["edges"])
    for e in extra["edges"]:
        key = (e["source"], e["target"], e["type"])
        if key not in seen:
            seen.add(key)
            edges.append(e)
    return {"nodes": list(nodes_by.values()), "edges": edges}


def _ttd_evidence_text(drug_hits: list) -> str:
    """Format TTD drug hits as a plain-text block for the reasoner."""
    if not drug_hits:
        return ""
    by_gene: dict[str, list] = {}
    for d in drug_hits:
        by_gene.setdefault(d["gene_symbol"], []).append(d)
    lines = ["TTD DRUG EVIDENCE (from Therapeutic Target Database):"]
    for gene, drugs in by_gene.items():
        lines.append(f"  {gene}:")
        for d in drugs:
            status = d.get("approval_status") or "unknown"
            mech = d.get("mechanism") or ""
            name = d.get("drug_name") or "?"
            lines.append(f"    • {name} [{status}]{' — ' + mech if mech else ''}")
    return "\n".join(lines)


def run(question, profile_id=None, mutations=None, context=None, history=None):
    # Fetch stored profile memory from Neo4j when a profile_id is known.
    # Falls back gracefully to "" so nothing downstream breaks.
    profile_memory = _fetch_profile_memory(profile_id) if profile_id else ""

    # TTD enrichment: when the question is drug-related, look up drugs for
    # each protein in the context selection.  Results are written to Neo4j
    # (idempotent) and injected into the reasoner as grounded evidence.
    ttd_drug_hits: list = []
    if ttd.is_drug_question(question):
        context_proteins = [c["protein"] for c in (context or []) if c.get("protein")]
        # Also include proteins from the profile when no explicit context card
        # is selected (user asked a general drug question about the profile).
        if not context_proteins and profile_memory:
            # Extract unique protein names from the first line of each mutation
            # entry in the profile memory block.
            import re as _re
            context_proteins = list(dict.fromkeys(
                _re.findall(r"\b([A-Z][A-Z0-9]{1,7})\b", profile_memory)
            ))[:5]  # cap at 5 to avoid runaway API calls
        for protein in context_proteins:
            # Resolve protein_change from context card if present
            protein_change = next(
                (c.get("hgvs_protein") or c.get("protein_change")
                 for c in (context or []) if c.get("protein") == protein),
                None,
            )
            hits = ttd.fetch_target_drugs(protein, protein_change=protein_change)
            ttd_drug_hits.extend(hits)
        if ttd_drug_hits:
            ttd_writer.upsert_drugs(ttd_drug_hits)

    profile = _profile_text(mutations, context, profile_memory=profile_memory)
    convo   = _history_text(history)

    # ── Classify: lookup (graph retrieval) vs reason (mechanistic analysis) ──
    mode = planner.classify(question)

    # ── Plan: LLM or deterministic fallback → Cypher ─────────────────────────
    plan = planner.plan(question, profile=profile, history=convo)
    try:
        result = cypher.run_read(plan["cypher"], plan["params"])
    except (RuntimeError, ValueError):
        result = None

    if result is None or (not result["subgraph"]["nodes"] and not result["rows"]):
        cy, params = planner._fallback(question)
        plan   = {"cypher": cy, "params": params, "source": "fallback"}
        result = cypher.run_read(cy, params)

    # Pull every relationship between the returned nodes so the Agent Graph
    # is fully wired regardless of what the query happened to SELECT.
    result["subgraph"] = _enrich_edges(result["subgraph"])

    # ── Report: summarize (lookup) or full mechanistic reasoning (reason) ─────
    if mode == "lookup":
        report = reasoner.summarize(result, profile=profile)
        routing, evidence = [], ""
    else:
        try:
            routing = drug_routing.route(mutations, context)
            evidence = drug_routing.evidence_text(mutations, context)
        except Exception:
            routing, evidence = [], ""

        ttd_block = _ttd_evidence_text(ttd_drug_hits)
        if ttd_block:
            evidence = f"{evidence}\n\n{ttd_block}".strip() if evidence else ttd_block

        report = reasoner.reason(question, result, profile=profile, history=convo, evidence=evidence)

    pathway_ids = [
        n.get("key") or n.get("label") or n["id"]
        for n in result["subgraph"]["nodes"]
        if "Pathway" in n.get("labels", [])
    ]
    return {
        "question":    question,
        "cypher":      plan["cypher"],
        "plan_source": plan["source"],
        "mode":        mode,           # "lookup" | "reason" — tells the frontend which path ran
        "report":      report["report"],
        "verdict":     report.get("verdict"),
        "subgraph":    result["subgraph"],
        "rows":        result["rows"],
        "cited_pathways": pathway_ids,
        "drug_routing":   routing,
        "ttd_drugs":      ttd_drug_hits,
    }
