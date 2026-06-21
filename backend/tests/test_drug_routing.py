"""Drug-routing wiring: graph lookup + ML fallback, independent of Neo4j/LLM."""

from backend.agents import drug_routing


def _muts(*specs):
    # spec: (protein, mutation_id, estimated_effect)
    return [
        {"protein": p, "mutation_id": mid, "estimated_effect": eff}
        for p, mid, eff in specs
    ]


def test_egfr_l858r_routes_to_direct_drug():
    items = drug_routing.route(_muts(("EGFR", "EGFR:p.L858R", "gain_of_function")))
    assert len(items) == 1
    egfr = items[0]
    assert egfr["mutation"] == "EGFR L858R"
    assert "osimertinib" in egfr["direct_drugs"]


def test_kras_g12d_has_no_variant_drug_but_gets_ml_fallback():
    items = drug_routing.route(_muts(("KRAS", "KRAS:p.G12D", "gain_of_function")))
    kras = items[0]
    assert kras["mutation"] == "KRAS G12D"
    # sotorasib/adagrasib are G12C-only — must not be claimed for G12D.
    assert "sotorasib" not in kras["direct_drugs"]
    assert "adagrasib" not in kras["direct_drugs"]
    # With no direct drug, the ML fallback should produce predictions.
    assert kras["ml_predictions"], "expected ML fallback predictions for the gap"
    p = kras["ml_predictions"][0]
    assert 0.0 <= p["probability"] <= 1.0
    assert p["pathway_id"] in {"MAPK_signaling", "RAS_RAF_MEK_ERK", "pathways_in_cancer"}


def test_unknown_gene_is_skipped():
    items = drug_routing.route(_muts(("ZZZ9", "ZZZ9:p.A1B", "gain_of_function")))
    assert items == []


def test_evidence_text_mentions_ml_for_kras_and_drug_for_egfr():
    text = drug_routing.evidence_text(
        _muts(
            ("EGFR", "EGFR:p.L858R", "gain_of_function"),
            ("KRAS", "KRAS:p.G12D", "gain_of_function"),
        )
    )
    assert "DRUG-ROUTING EVIDENCE" in text
    assert "osimertinib" in text
    assert "KRAS G12D" in text
    assert "ML" in text  # ML fallback cited for the KRAS gap


def test_bare_gene_selection_without_mutation_signal_is_not_routed():
    # Clicking KRAS on the graph with no variant and no effect carries nothing
    # for the classifier to do — it must NOT emit a gene-level guess.
    ctx = [{"protein": "KRAS", "effect": "no_effect", "mutation_id": ""}]
    assert drug_routing.route([], ctx) == []
    assert drug_routing.evidence_text([], ctx) == ""


def test_selected_context_with_real_effect_is_routed():
    # A selected node that carries a real driver call (gain_of_function) is a
    # legitimate mutation input even without a variant string.
    ctx = [{"protein": "KRAS", "effect": "gain_of_function", "mutation_id": ""}]
    items = drug_routing.route([], ctx)
    assert len(items) == 1 and items[0]["gene"] == "KRAS"
    assert items[0]["ml_predictions"], "a real driver call should produce ML predictions"


def test_profile_variant_preferred_over_bare_context_for_same_gene():
    # KRAS selected (no variant) AND KRAS G12D in the profile -> use the variant.
    ctx = [{"protein": "KRAS", "effect": "no_effect", "mutation_id": ""}]
    muts = _muts(("KRAS", "KRAS:p.G12D", "gain_of_function"))
    items = drug_routing.route(muts, ctx)
    kras = [i for i in items if i["gene"] == "KRAS"]
    assert len(kras) == 1
    assert kras[0]["mutation"] == "KRAS G12D"


def test_empty_inputs_no_evidence():
    assert drug_routing.route([]) == []
    assert drug_routing.route([], []) == []
    assert drug_routing.evidence_text([], []) == ""
