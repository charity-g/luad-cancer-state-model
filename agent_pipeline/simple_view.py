"""
Simple end-user view: ask about a mutation, get a short answer and a
clean list of drugs at the bottom. This is the "what does the user
actually see" layer, built on top of synthesizer.py (Steps 1-5).

No paragraphs of caveats up front -- just: here's what we found, here's
what to consider, source-tagged so it's still honest, but skimmable.
"""

from synthesizer import Synthesizer

PATHWAY_DISPLAY_NAMES = {
    "MAPK_signaling": "MAPK signaling",
    "RAS_RAF_MEK_ERK": "RAS-RAF-MEK-ERK signaling",
    "PI3K_Akt": "PI3K-Akt signaling",
    "EGFR_signaling": "EGFR signaling",
    "endocytosis": "endocytosis",
    "JAK_STAT3": "JAK-STAT3 signaling",
    "Wnt_signaling": "Wnt signaling",
    "Notch_signaling": "Notch signaling",
    "VEGF_signaling": "VEGF signaling",
}


def _pathway_name(pid: str) -> str:
    return PATHWAY_DISPLAY_NAMES.get(pid, pid.replace("_", " "))


def show_result(synth: Synthesizer, mutations: list[str]):
    result = synth.answer(mutations)

    print(f"\n{'='*60}")
    print(f"  {' + '.join(mutations)}")
    print(f"{'='*60}")

    for ans in result.per_mutation:
        if ans.unknown_mutation:
            print(f"\n  Not recognized: '{ans.mutation}'")
            continue

        if not ans.database_drugs and not ans.ml_predictions:
            print(f"\n  {ans.mutation}: no drug option found for this mutation.")
            continue

        # one-line headline
        n_drugs = len(ans.database_drugs)
        n_predicted = sum(1 for p in ans.ml_predictions if p.predicted_vulnerable)
        if n_drugs:
            print(f"\n  {ans.mutation}: {n_drugs} confirmed drug option(s) found.")
        elif n_predicted:
            print(f"\n  {ans.mutation}: no confirmed drug, but {n_predicted} pathway(s) "
                  f"flagged as likely targetable -- see notes below.")
        else:
            print(f"\n  {ans.mutation}: no confirmed or predicted options found.")

        # the actual list
        print(f"  ---------------------------")
        for d in ans.database_drugs:
            short_desc = d.description.split(".")[0]  # first sentence only
            print(f"  ✓ {d.drug:<15} (confirmed)   {short_desc}")
        for p in ans.ml_predictions:
            if p.predicted_vulnerable:
                tag = "low confidence" if p.data_support_level in ("low", "very_low") else "predicted"
                print(f"  ? {_pathway_name(p.pathway):<15} ({tag})   "
                      f"model suggests this pathway may still be worth targeting")

    if result.is_combination:
        print(f"\n  Note: multiple mutations present -- the graph doesn't have "
              f"data on combining these drugs together. Treat each list above "
              f"as independent options, not a combined regimen.")


if __name__ == "__main__":
    synth = Synthesizer()

    show_result(synth, ["EGFR L858R"])
    show_result(synth, ["KRAS G12D"])
    show_result(synth, ["TP53 loss"])
    show_result(synth, ["EGFR L858R", "KRAS G12D"])
    show_result(synth, ["FAKE_GENE Q999X"])
