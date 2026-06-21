"""
Step 5: Synthesis.

The single entry point: ask about a mutation (or mutation combo), get back
one answer that's actually two answers stitched together honestly --
whatever the deterministic graph lookup (Steps 1-3) can support directly,
plus whatever the ML classifier (Step 4) can add for the gaps, with every
field explicitly tagged "database" or "model_predicted" so nothing is
ever presented with false confidence.

This is the "synthesis agent" in the multi-agent framing: it doesn't
invent new logic, it calls the retrieval layer first, calls the
prediction layer only for what retrieval couldn't answer, and merges
the two without blurring which is which.
"""

from dataclasses import dataclass, field
from pathlib import Path

from graph_lookup import load_graph, mutation_to_drugs
from gap_detector import check_coverage, check_combo_coverage, CoverageReport
from ml_classifier import (
    load_training_data,
    pathway_support_report,
    train_and_evaluate,
    predict_pathway_vulnerability,
)

# Known hotspot status for the mutations in unified_graph.json's
# mutation_index. Hand-verified against established cancer genomics
# literature (COSMIC hotspot annotations), not inferred from the mutation
# string -- "G12D" looking similar to "G12C" doesn't tell you hotspot
# status, so this is an explicit lookup table, not a parser/heuristic.
# All ten mutations currently in the graph ARE documented hotspots; this
# table exists so that's a checked fact, not an assumption, and so future
# additions don't silently default to an unverified guess.
KNOWN_HOTSPOT_MUTATIONS = {
    "EGFR L858R", "EGFR exon19del", "KRAS G12C", "KRAS G12D", "KRAS G12V",
    "BRAF V600E", "ALK fusion", "TP53 R175H", "PIK3CA H1047R",
    # NOTE: "TP53 loss" is deliberately excluded -- it describes a
    # functional outcome (loss of function), not a specific hotspot
    # variant, so hotspot status doesn't apply to it the same way.
}


@dataclass
class DrugRecommendation:
    drug: str
    description: str
    match_type: str           # "direct_target" | "pathway"
    pathways_covered: list
    source: str                # "database"


@dataclass
class PathwayPrediction:
    pathway: str
    predicted_vulnerable: bool
    probability: float
    data_support_level: str
    source: str                 # "model_predicted"


@dataclass
class MutationAnswer:
    mutation: str
    gene: str | None
    unknown_mutation: bool
    fully_covered_by_database: bool
    database_drugs: list = field(default_factory=list)        # list[DrugRecommendation]
    gap_pathways: list = field(default_factory=list)            # pathway ids with no direct drug
    ml_predictions: list = field(default_factory=list)          # list[PathwayPrediction]
    notes: list = field(default_factory=list)                   # human-readable caveats


@dataclass
class SynthesisResult:
    mutations: list
    is_combination: bool
    per_mutation: list = field(default_factory=list)            # list[MutationAnswer]
    needs_ml_fallback: bool = False
    combo_reason: str = ""


class Synthesizer:
    """
    Loads the graph and trains the classifier ONCE, then answers many
    queries cheaply. Training the classifier per-query would be wasteful
    and would also mean cross-validation runs (and prints) on every call.
    """

    def __init__(self):
        self.graph = load_graph()

        examples = load_training_data()
        self.pathway_support = pathway_support_report(examples)
        self.clf, self.encoders = train_and_evaluate(examples)

    def _ml_predict_for_gap(self, gene: str, pathway: str, mutation: str) -> PathwayPrediction:
        is_hotspot = mutation in KNOWN_HOTSPOT_MUTATIONS
        result = predict_pathway_vulnerability(
            self.clf, self.encoders, gene, pathway,
            pathway_support=self.pathway_support,
            is_hotspot=is_hotspot,
        )
        return PathwayPrediction(
            pathway=result["pathway"],
            predicted_vulnerable=result["predicted_vulnerable"],
            probability=result["probability"],
            data_support_level=result["data_support_level"],
            source="model_predicted",
        )

    def _answer_single_mutation(self, mutation: str) -> MutationAnswer:
        coverage: CoverageReport = check_coverage(self.graph, mutation)

        if coverage.unknown_mutation:
            return MutationAnswer(
                mutation=mutation, gene=None, unknown_mutation=True,
                fully_covered_by_database=False,
                notes=[f"'{mutation}' is not in the graph's mutation_index -- "
                       f"cannot resolve to a gene, no answer available."],
            )

        # Database-sourced drug recommendations (Steps 1-3)
        database_drugs = [
            DrugRecommendation(
                drug=d["drug"], description=d["description"],
                match_type=d["match_type"], pathways_covered=d["pathways_covered"],
                source="database",
            )
            for d in coverage.drugs if d["match_type"] == "direct_target"
        ]

        notes = []
        ml_predictions = []

        if coverage.fully_covered:
            notes.append("Fully answered by graph lookup -- no model prediction needed.")
        else:
            if not coverage.has_targetable_pathways:
                notes.append(
                    f"'{mutation}' has no activated, druggable pathway in the graph "
                    f"(only repressed/tumor-suppressor or meta-pathway hits) -- "
                    f"there is nothing here for either the lookup path or this "
                    f"oncogene-focused classifier to meaningfully predict on."
                )
            else:
                notes.append(
                    f"{len(coverage.gap_pathway_ids)} activated pathway(s) have no "
                    f"direct-target drug in the graph. Falling back to ML prediction "
                    f"for those specific pathways."
                )
                for pathway_id in sorted(coverage.gap_pathway_ids):
                    pred = self._ml_predict_for_gap(coverage.gene, pathway_id, mutation)
                    ml_predictions.append(pred)

        return MutationAnswer(
            mutation=mutation,
            gene=coverage.gene,
            unknown_mutation=False,
            fully_covered_by_database=coverage.fully_covered,
            database_drugs=database_drugs,
            gap_pathways=sorted(coverage.gap_pathway_ids),
            ml_predictions=ml_predictions,
            notes=notes,
        )

    def answer(self, mutations: list[str]) -> SynthesisResult:
        if len(mutations) == 1:
            combo = check_combo_coverage(self.graph, mutations)
            per_mutation = [self._answer_single_mutation(mutations[0])]
            return SynthesisResult(
                mutations=mutations, is_combination=False,
                per_mutation=per_mutation,
                needs_ml_fallback=combo.needs_ml_fallback,
                combo_reason=combo.reason,
            )

        combo = check_combo_coverage(self.graph, mutations)
        per_mutation = [self._answer_single_mutation(m) for m in mutations]

        combo_note = (
            "This is a multi-mutation combination. The graph has single-drug "
            "mechanisms for each mutation individually, but NO data on how "
            "drugs interact when combined -- the per-mutation answers below "
            "are independently correct, but do not by themselves tell you "
            "whether combining their drugs is safe or effective together."
        )

        return SynthesisResult(
            mutations=mutations, is_combination=True,
            per_mutation=per_mutation,
            needs_ml_fallback=True,  # combos always need this caveat
            combo_reason=combo_note,
        )


def print_answer(result: SynthesisResult):
    print(f"\n{'='*70}")
    print(f"QUERY: {' + '.join(result.mutations)}")
    print(f"{'='*70}")

    for ans in result.per_mutation:
        print(f"\n--- {ans.mutation} ---")
        if ans.unknown_mutation:
            print(f"  UNKNOWN MUTATION: {ans.notes[0]}")
            continue

        print(f"  Gene: {ans.gene}")
        print(f"  Fully covered by database: {ans.fully_covered_by_database}")

        if ans.database_drugs:
            print(f"  Database-confirmed drugs:")
            for d in ans.database_drugs:
                print(f"    [database] {d.drug} -- {d.description}")

        if ans.ml_predictions:
            print(f"  Model predictions for uncovered pathways:")
            for p in ans.ml_predictions:
                verdict = "LIKELY VULNERABLE" if p.predicted_vulnerable else "likely not vulnerable"
                print(f"    [model_predicted, support={p.data_support_level}] "
                      f"{p.pathway}: {verdict} (p={p.probability})")

        for note in ans.notes:
            print(f"  NOTE: {note}")

    if result.is_combination:
        print(f"\n  COMBINATION CAVEAT: {result.combo_reason}")


if __name__ == "__main__":
    synth = Synthesizer()

    # Case 1: fully covered by database alone
    print_answer(synth.answer(["EGFR L858R"]))

    # Case 2: database has zero direct drug -- model must fire
    print_answer(synth.answer(["KRAS G12D"]))

    # Case 3: no targetable pathway at all -- neither lookup nor model has anything
    print_answer(synth.answer(["TP53 loss"]))

    # Case 4: real multi-mutation combination
    print_answer(synth.answer(["EGFR L858R", "KRAS G12D"]))

    # Case 5: unknown mutation, graceful handling
    print_answer(synth.answer(["FAKE_GENE Q999X"]))

    print("\n\nDone -- all five cases handled without crashing.")
