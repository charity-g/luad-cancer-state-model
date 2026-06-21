
def gap_detector():
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


def test_graph_lookup():
    g = load_graph()
    for w in validate_graph(g):
        print("WARN:", w)

    for mut in ["EGFR L858R", "KRAS G12D", "KRAS G12C", "BRAF V600E", "ALK fusion", "TP53 loss"]:
        result = mutation_to_drugs(g, mut)
        print(f"\n=== {mut} (gene={result.get('gene')}) ===")
        for d in result["drugs"][:6]:
            tag = "direct" if d["match_type"] == "direct_target" else "pathway"
            print(f"  [{tag}] {d['drug']}: {d['pathways_covered']}")
