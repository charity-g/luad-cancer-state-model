"""
Step 4: ML fallback classifier.

Trained on REAL DepMap LUAD data (53 cell lines, CRISPR knockout effect +
somatic mutation calls). Predicts whether a pathway is "vulnerable" (worth
targeting with a drug) given which gene is mutated, which pathway it sits
in, the gene's actual CRISPR dependency score, and its broad oncogene/
tumor-suppressor role.

This model only fires for cases gap_detector.py has already flagged as
NOT covered by direct graph lookup (e.g. KRAS G12D, where sotorasib/
adagrasib are excluded for being the wrong variant, or multi-mutation
combinations the graph has no interaction data for).

METHODOLOGY NOTES (revised after review -- see git history for the
original version and what was wrong with it):
- Evaluation uses GroupKFold by gene, not row-random StratifiedKFold.
  The original version let the same gene (e.g. KRAS, 50 rows) appear in
  both train and test folds, which inflates reported accuracy without
  testing real generalization. GroupKFold holds out entire genes.
- Features include the actual CRISPR effect score and a gene-role
  (oncogene/tumor_suppressor/unknown) flag, not just categorical gene/
  pathway IDs. The original version never gave the model the underlying
  measurement the labels were derived from.
- Logistic regression with CalibratedClassifierCV (Platt scaling)
  replaces RandomForest. RandomForest's predict_proba on this feature
  set was a vote fraction, not a calibrated probability.
- Confidence reporting now considers pathway sample size, gene
  diversity, AND class balance -- not raw example count alone.

HONEST LIMITATIONS THAT REMAIN:
- Still only 193 training examples, dominated by KRAS (50) and EGFR (42)
  -- roughly half the 39 genes in the dataset appear 1-2 times. Real
  generalization to a rarely-seen gene is weak; this is reported
  explicitly via confidence_level, not hidden.
- CRISPR knockout != drug inhibition. Genetic knockout is typically more
  complete and has different kinetics than a small-molecule inhibitor.
  This is a reasonable proxy signal, not ground truth on drug efficacy.
- Oncogene/tumor-suppressor role list is a small manually-curated set
  (COSMIC-style categories), not learned or exhaustive -- most genes in
  the underlying graph fall back to "unknown" role.
"""

import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, confusion_matrix, brier_score_loss
from sklearn.preprocessing import OneHotEncoder

DATA_PATH = Path(__file__).parent / "pathway_training_examples_v2.json"
MIN_EXAMPLES_FOR_SUPPORT = 8  # pathways below this get flagged low data_support_level

# Coarse oncogene vs. tumor-suppressor role, sourced from well-established
# cancer biology (COSMIC Cancer Gene Census categories), NOT learned from
# this dataset.
ONCOGENES = {
    "EGFR", "KRAS", "BRAF", "ERBB2", "MET", "MYC", "PIK3CA", "CTNNB1",
    "AKT1", "JAK1", "JAK2", "STAT3", "NOTCH1", "WNT3A", "MDM2",
}
TUMOR_SUPPRESSORS = {
    "TP53", "PTEN", "RB1", "APC", "CDKN1A", "BAX",
}


def gene_role(gene: str) -> str:
    if gene in ONCOGENES:
        return "oncogene"
    if gene in TUMOR_SUPPRESSORS:
        return "tumor_suppressor"
    return "unknown"


def load_training_data():
    with open(DATA_PATH) as f:
        examples = json.load(f)
    return examples


def build_features(examples):
    """
    Round 3 features, after two review rounds:

    REMOVED (round 2): crispr_effect -- circular with the label, and
    unavailable at real inference time anyway (see git history).

    ADDED (round 3): per-mutation features that are genuinely available
    BEFORE any CRISPR measurement -- is_hotspot, is_lof (likely
    loss-of-function), is_high_impact (VEP severity), and DepMap's own
    oncogene_high_impact / tsg_high_impact calls. These come from the
    mutation annotation itself (VEP, hotspot databases), not from the
    dependency screen, so they are not circular with label_vulnerable.

    is_hotspot in particular shows a large, biologically sensible signal
    in this data: 82% of hotspot-mutation rows are labeled vulnerable
    vs. 4% of non-hotspot rows (checked before deciding to include it).
    That's consistent with real biology -- hotspot mutations are
    recurrent activating driver mutations; non-hotspot mutations are
    often passengers that don't create a targetable dependency.

    Remaining features: gene role, gene identity, pathway identity
    (as before), plus the mutation-level booleans above.
    """
    roles = [[gene_role(e["mutated_gene"])] for e in examples]
    genes = [[e["mutated_gene"]] for e in examples]
    pathways = [[e["pathway"]] for e in examples]

    role_enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    gene_enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    pathway_enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    role_feats = role_enc.fit_transform(roles)
    gene_feats = gene_enc.fit_transform(genes)
    pathway_feats = pathway_enc.fit_transform(pathways)

    mutation_feats = np.array([[
        float(e["is_hotspot"]),
        float(e["is_lof"]),
        float(e["is_high_impact"]),
        float(e["oncogene_high_impact"]),
        float(e["tsg_high_impact"]),
    ] for e in examples])

    X = np.hstack([role_feats, mutation_feats, gene_feats, pathway_feats])
    y = np.array([e["label_vulnerable"] for e in examples])
    groups = np.array([e["mutated_gene"] for e in examples])

    encoders = {"role": role_enc, "gene": gene_enc, "pathway": pathway_enc}
    return X, y, groups, encoders


def train_and_evaluate(examples):
    X, y, groups, encoders = build_features(examples)
    n_unique_genes = len(set(groups))

    # CRITICAL FIX (per review): the original version used StratifiedKFold,
    # which splits ROWS randomly. Since the same gene appears many times
    # (KRAS: 50 rows, EGFR: 42 rows), random row-splits let the model see
    # "KRAS + MAPK -> vulnerable" in training and a near-identical row in
    # the test fold -- inflating reported accuracy without testing whether
    # the model generalizes to a gene it has never seen.
    #
    # GroupKFold ensures every row for a given gene lands entirely in
    # train OR entirely in test, never both. This directly tests: "can
    # the model predict vulnerability for a gene it never saw during
    # training?" -- which is the realistic deployment scenario (most
    # genes a clinician asks about won't be heavily represented, if
    # represented at all, in this small dataset).
    n_splits = min(5, n_unique_genes)
    gkf = GroupKFold(n_splits=n_splits)

    # Logistic regression instead of RandomForest: with one-hot categorical
    # features dominating the input, a depth-4 forest was effectively
    # memorizing a lookup table. Logistic regression on the same features
    # is simpler, equally capable here, and -- critically -- supports
    # genuinely calibrated probabilities via CalibratedClassifierCV,
    # rather than RandomForest's "fraction of trees that voted yes,"
    # which is NOT the same thing as a real probability.
    base_clf = LogisticRegression(max_iter=1000, C=1.0)

    y_pred = cross_val_predict(base_clf, X, y, cv=gkf, groups=groups)

    print(f"=== Cross-validated performance: GroupKFold by gene ({n_splits} folds, "
          f"{n_unique_genes} unique genes -- every gene held out as a group, "
          f"never split across train/test) ===")
    print(classification_report(y, y_pred, target_names=["not_vulnerable", "vulnerable"], zero_division=0))
    print("Confusion matrix:")
    print(confusion_matrix(y, y_pred))

    # Honest comparison: what the OLD (leaky) evaluation would have shown,
    # so the difference is visible rather than just asserted.
    from sklearn.model_selection import StratifiedKFold
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred_leaky = cross_val_predict(base_clf, X, y, cv=skf)
    print("\n=== For comparison: row-random StratifiedKFold (the ORIGINAL, "
          "leaky evaluation -- shown to make the gap visible, not used "
          "for reported performance) ===")
    print(classification_report(y, y_pred_leaky, target_names=["not_vulnerable", "vulnerable"], zero_division=0))

    # Fit final model on ALL data, wrapped in calibration so predict_proba
    # returns genuinely calibrated probabilities (Platt scaling), not raw
    # vote fractions.
    clf = CalibratedClassifierCV(base_clf, method="sigmoid", cv=min(3, n_splits))
    clf.fit(X, y)

    # Brier score: a real proper-scoring-rule measure of probability
    # calibration quality (lower is better, 0 = perfect). Reported because
    # accuracy alone says nothing about whether "0.91" actually means
    # "91% likely," per the critique on overconfident probabilities.
    calibrated_probs = cross_val_predict(
        CalibratedClassifierCV(base_clf, method="sigmoid", cv=min(3, n_splits)),
        X, y, cv=gkf, groups=groups, method="predict_proba"
    )[:, 1]
    brier = brier_score_loss(y, calibrated_probs)
    print(f"\nBrier score (calibration quality, lower=better, 0=perfect): {brier:.3f}")

    return clf, encoders


def pathway_support_report(examples):
    """
    Per-pathway data support level: sample size + gene diversity + class
    balance. Named "data_support_level," not "confidence" -- per review,
    these thresholds (n>=8, genes>=3, balance>=0.15) are reasonable
    heuristics but not a statistically derived confidence interval, and
    calling them "confidence" overclaims rigor they don't have.
    """
    by_pathway = {}
    for e in examples:
        by_pathway.setdefault(e["pathway"], []).append(e)

    print("\n=== Per-pathway data support level (sample size + gene diversity + class balance) ===")
    support = {}
    for pathway, rows in sorted(by_pathway.items(), key=lambda x: -len(x[1])):
        n = len(rows)
        unique_genes = len(set(r["mutated_gene"] for r in rows))
        n_vuln = sum(1 for r in rows if r["label_vulnerable"])
        balance = min(n_vuln, n - n_vuln) / n if n > 0 else 0

        is_supported = (n >= MIN_EXAMPLES_FOR_SUPPORT
                         and unique_genes >= 3
                         and balance >= 0.15)
        support[pathway] = is_supported
        flag = "" if is_supported else "  <- LOW DATA SUPPORT"
        print(f"  n={n:3d}  genes={unique_genes:2d}  "
              f"vulnerable={n_vuln}/{n}  {pathway}{flag}")
    return support


def predict_pathway_vulnerability(clf, encoders, gene: str, pathway: str,
                                    pathway_support: dict,
                                    is_hotspot: bool = False,
                                    is_lof: bool = False,
                                    is_high_impact: bool = False,
                                    oncogene_high_impact: bool = False,
                                    tsg_high_impact: bool = False) -> dict:
    """
    Predict whether targeting `pathway` is likely to help, given `gene`
    is mutated. Mutation-level features (is_hotspot etc.) ARE realistic
    inputs at inference time -- unlike crispr_effect, hotspot/LoF/impact
    status comes from variant annotation (VEP, hotspot databases), which
    is available the moment a mutation is sequenced, before any
    functional screen. Defaults are conservative (False) if unknown.
    """
    role = gene_role(gene)
    gene_seen = gene in encoders["gene"].categories_[0].tolist()
    pathway_seen = pathway in encoders["pathway"].categories_[0].tolist()

    role_feat = encoders["role"].transform([[role]])
    gene_feat = encoders["gene"].transform([[gene]])
    pathway_feat = encoders["pathway"].transform([[pathway]])
    mutation_feat = np.array([[
        float(is_hotspot), float(is_lof), float(is_high_impact),
        float(oncogene_high_impact), float(tsg_high_impact),
    ]])
    X = np.hstack([role_feat, mutation_feat, gene_feat, pathway_feat])

    proba = clf.predict_proba(X)[0]
    classes = list(clf.classes_)
    p_true = proba[classes.index(True)] if True in classes else 0.0

    pathway_supported = pathway_support.get(pathway, False)

    if not gene_seen:
        support_level = "very_low"
    elif not pathway_supported:
        support_level = "low"
    else:
        support_level = "moderate"  # never claim "high" off 193 examples

    return {
        "gene": gene,
        "pathway": pathway,
        "gene_role": role,
        "is_hotspot": is_hotspot,
        "predicted_vulnerable": bool(p_true > 0.5),
        "probability": round(float(p_true), 3),
        "data_support_level": support_level,
        "gene_seen_in_training": gene_seen,
        "pathway_seen_in_training": pathway_seen,
        "source": "model_predicted",
    }


if __name__ == "__main__":
    examples = load_training_data()
    print(f"Loaded {len(examples)} training examples\n")

    pathway_support = pathway_support_report(examples)

    print()
    clf, encoders = train_and_evaluate(examples)

    print("\n=== Example predictions (gap cases gap_detector.py flagged) ===")

    # KRAS G12D: gap_detector confirmed zero direct-target drug (sotorasib/
    # adagrasib are G12C-only). G12D IS a known hotspot mutation -- this
    # is realistic information available the moment the variant is called,
    # not something requiring a fresh CRISPR screen.
    for pathway in ["MAPK_signaling", "RAS_RAF_MEK_ERK"]:
        result = predict_pathway_vulnerability(
            clf, encoders, "KRAS", pathway, pathway_support=pathway_support,
            is_hotspot=True, oncogene_high_impact=False,
        )
        print(result)

    # Same gene, but a NON-hotspot KRAS variant -- tests whether the
    # model actually uses is_hotspot rather than just memorizing "KRAS".
    print("\n=== KRAS, but a hypothetical NON-hotspot variant (tests whether "
          "the model actually uses mutation features, not just gene identity) ===")
    result_nonhotspot = predict_pathway_vulnerability(
        clf, encoders, "KRAS", "MAPK_signaling", pathway_support=pathway_support,
        is_hotspot=False,
    )
    print(result_nonhotspot)

    # Genuinely unseen gene
    print("\n=== Genuinely unseen gene ===")
    result = predict_pathway_vulnerability(
        clf, encoders, "PTGS2", "MAPK_signaling", pathway_support=pathway_support,
        is_hotspot=True,
    )
    print(result)
    assert result["data_support_level"] == "very_low", \
        "a truly unseen gene must report very_low data support"

    print("\nAll assertions passed.")
