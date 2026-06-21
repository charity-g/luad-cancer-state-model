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
from backend.agents.classifier.graph_lookup import load_graph, mutation_to_drugs

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


