"""
Step 3: Gap detector.

Router between the deterministic lookup path (graph_lookup.py) and the
ML fallback (Step 4, not built yet). Rewritten to match the dict-based
interface that graph_lookup.py currently uses on this branch (mutation_to_drugs
returns a dict with 'pathways' and 'drugs' keys, not dataclass objects).

A pathway counts as COVERED if at least one drug has match_type
'direct_target' against it. crosstalk_hub pathways are excluded from
gap/coverage accounting -- checked against the graph data, ZERO drugs
have an inhibits edge to ANY crosstalk_hub pathway, so counting them
as gaps would mean every mutation always shows a gap (noise, not signal).
"""

from dataclasses import dataclass, field
from graph_lookup import load_graph, mutation_to_drugs

TARGETABLE_STATUSES = ("activated", "nsclc_enriched")


@dataclass
class CoverageReport:
    mutation: str
    gene: str | None
    pathways: list[dict] = field(default_factory=list)
    drugs: list[dict] = field(default_factory=list)
    covered_pathway_ids: set = field(default_factory=set)
    gap_pathway_ids: set = field(default_factory=set)
    unknown_mutation: bool = False

    @property
    def direct_drugs(self) -> list[dict]:
        return [d for d in self.drugs if d["match_type"] == "direct_target"]

    @property
    def has_targetable_pathways(self) -> bool:
        """Does this mutation activate any pathway that's a real drug
        target in this graph (excluding crosstalk_hub meta-pathways)?"""
        return any(p["status"] in TARGETABLE_STATUSES for p in self.pathways)

    @property
    def fully_covered(self) -> bool:
        """
        True only if there's at least one targetable pathway AND every
        one of them is covered by a direct_target drug. A mutation with
        NO targetable pathways (e.g. TP53 loss, which only touches
        repressed/crosstalk_hub pathways) is NOT "fully covered" --
        there's nothing for the lookup path to answer, which should
        route to fallback rather than reporting a silent empty success.
        """
        return self.has_targetable_pathways and len(self.gap_pathway_ids) == 0


def check_coverage(graph: dict, mutation: str) -> CoverageReport:
    result = mutation_to_drugs(graph, mutation)

    if result.get("unknown_mutation"):
        return CoverageReport(mutation=mutation, gene=None, unknown_mutation=True)

    pathways = result["pathways"]
    drugs = result["drugs"]

    direct_drugs = [d for d in drugs if d["match_type"] == "direct_target"]
    covered_ids = set()
    for d in direct_drugs:
        covered_ids.update(d["pathways_covered"])

    targetable_ids = {p["id"] for p in pathways if p["status"] in TARGETABLE_STATUSES}
    gap_ids = targetable_ids - covered_ids

    return CoverageReport(
        mutation=mutation,
        gene=result["gene"],
        pathways=pathways,
        drugs=drugs,
        covered_pathway_ids=covered_ids,
        gap_pathway_ids=gap_ids,
    )


@dataclass
class ComboCoverageReport:
    mutations: list
    per_mutation: list = field(default_factory=list)
    combined_active_pathways: set = field(default_factory=set)
    combined_covered_pathways: set = field(default_factory=set)
    combined_gap_pathways: set = field(default_factory=set)

    @property
    def needs_ml_fallback(self) -> bool:
        """
        True if any of:
          (a) any individual mutation has gap pathways, OR
          (b) more than one mutation (graph has single-drug mechanisms,
              no combination-interaction data), OR
          (c) no mutation in the set has any targetable pathway at all
              (e.g. TP53 loss alone) -- nothing for lookup to answer.
        """
        if self.combined_gap_pathways:
            return True
        if len(self.mutations) > 1:
            return True
        if not any(r.has_targetable_pathways for r in self.per_mutation):
            return True
        return False

    @property
    def reason(self) -> str:
        if self.combined_gap_pathways:
            return (f"{len(self.combined_gap_pathways)} activated pathway(s) "
                    f"have no direct-target drug in the graph.")
        if len(self.mutations) > 1:
            return ("Multiple mutations present -- graph has single-drug "
                    "mechanisms but no data on combination effects.")
        if not any(r.has_targetable_pathways for r in self.per_mutation):
            return ("No targetable (activated/nsclc_enriched) pathway found "
                    "for this mutation -- nothing for the lookup path to "
                    "match against a drug.")
        return "Fully covered by direct-target lookups."


def check_combo_coverage(graph: dict, mutations: list) -> ComboCoverageReport:
    reports = [check_coverage(graph, m) for m in mutations]

    combined_active, combined_covered, combined_gap = set(), set(), set()
    for r in reports:
        active_ids = {p["id"] for p in r.pathways if p["status"] in TARGETABLE_STATUSES}
        combined_active |= active_ids
        combined_covered |= r.covered_pathway_ids
        combined_gap |= r.gap_pathway_ids

    return ComboCoverageReport(
        mutations=mutations,
        per_mutation=reports,
        combined_active_pathways=combined_active,
        combined_covered_pathways=combined_covered,
        combined_gap_pathways=combined_gap,
    )


# ---------- tests (now asserts, not just prints, so CI/teammates catch regressions) ----------

if __name__ == "__main__":
    g = load_graph()

    r1 = check_coverage(g, "EGFR L858R")
    print(f"EGFR L858R -> fully_covered={r1.fully_covered}, gaps={r1.gap_pathway_ids}")
    assert r1.direct_drugs, "EGFR L858R should have at least one direct_target drug (osimertinib)"
    assert any(d["drug"] == "osimertinib" for d in r1.direct_drugs), "osimertinib should be direct_target for EGFR L858R"

    r2 = check_coverage(g, "KRAS G12D")
    print(f"KRAS G12D -> fully_covered={r2.fully_covered}, direct_drugs={[d['drug'] for d in r2.direct_drugs]}")
    assert not any(d["drug"] in ("sotorasib", "adagrasib") for d in r2.direct_drugs), \
        "sotorasib/adagrasib are G12C-only and must NOT be direct_target for G12D"
    assert not r2.fully_covered, \
        "KRAS G12D has no valid direct-target drug in this graph -- must NOT be fully_covered"

    r3 = check_coverage(g, "KRAS G12C")
    print(f"KRAS G12C -> fully_covered={r3.fully_covered}, direct_drugs={[d['drug'] for d in r3.direct_drugs]}")
    assert any(d["drug"] == "sotorasib" for d in r3.direct_drugs), \
        "sotorasib SHOULD be direct_target for the matching variant, G12C"

    r4 = check_coverage(g, "FAKE_GENE Q999X")
    assert r4.unknown_mutation, "unrecognized mutation should be flagged unknown_mutation"
    print("Unknown mutation handled correctly.")

    combo = check_combo_coverage(g, ["TP53 loss"])
    print(f"TP53 loss alone -> needs_ml_fallback={combo.needs_ml_fallback}, reason={combo.reason}")
    assert combo.needs_ml_fallback, \
        "TP53 loss has no targetable pathway in this graph and must require fallback, not report false success"

    combo2 = check_combo_coverage(g, ["EGFR L858R", "KRAS G12D"])
    print(f"EGFR L858R + KRAS G12D -> needs_ml_fallback={combo2.needs_ml_fallback}, reason={combo2.reason}")
    assert combo2.needs_ml_fallback, "multi-mutation combo must always require fallback (no interaction data in graph)"

    print("\nAll assertions passed.")
