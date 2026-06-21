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


def test_empty_mutations_no_evidence_and_no_model_load():
    assert drug_routing.route([]) == []
    assert drug_routing.evidence_text([]) == ""
