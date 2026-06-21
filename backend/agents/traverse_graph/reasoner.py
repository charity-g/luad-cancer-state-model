"""Reasoner — turns the retrieved subgraph into a cell-state / intervention report.

Uses Claude when ANTHROPIC_API_KEY is set; otherwise produces a deterministic
report from the subgraph so the pipeline runs end-to-end without a key. For
intervention questions it also returns a verdict.
"""

import re

import anthropic
from pydantic import BaseModel

from backend.config import ANTHROPIC_API_KEY, REASONER_MODEL

VERDICTS = ("beneficial", "harmful", "negligible", "uncertain")

_INTERVENTION = re.compile(
    r"\b(inhibit|block|suppress|knock|knockout|knockdown|target|drug|treat|"
    r"reverse|activat|overexpress|effect|help|improve|resist)\b", re.I
)

_SYSTEM = (
    "You are a cancer systems-biology reasoner for lung adenocarcinoma (LUAD). "
    "You are given mutation profile for a given patient"
    "(with LUAD status / inferred_state), Gene nodes (with CRISPR essentiality), "
    "and Mutation nodes, connected by typed causal relationships. Reason ONLY "
    "from the provided subgraph, cite nodes by name, and be mechanistic. Do not "
    "invent entities."
)


def summarize(result: dict, profile: str = "", evidence: str = "") -> dict:
    """Lightweight summary for lookup queries — describes the returned graph in
    1-3 sentences without mechanistic inference.  Much cheaper than reason().
    Falls back to a deterministic node-count description if no API key.
    """
    sub = result["subgraph"]
    if not sub["nodes"]:
        base = "No matching nodes found in the graph."
        if evidence:
            base += f"\n\n{evidence}"
        return {"report": base, "verdict": None}

    if ANTHROPIC_API_KEY:
        try:
            return _summarize_llm(sub, profile, evidence)
        except Exception:
            pass

    # Deterministic fallback — just enumerate what was found.
    by_label: dict[str, list[str]] = {}
    for n in sub["nodes"]:
        label = (n.get("labels") or ["Node"])[0]
        name  = n.get("label") or n.get("symbol") or n.get("name") or n.get("id") or "?"
        by_label.setdefault(label, []).append(str(name))
    parts = [
        f"**{lbl}** ({len(names)}): {', '.join(names[:5])}{'…' if len(names) > 5 else ''}"
        for lbl, names in by_label.items()
    ]
    report = "Graph contains " + "; ".join(parts) + f". ({len(sub['edges'])} edges total)"
    if evidence:
        report += f"\n\n{evidence}"
    return {"report": report, "verdict": None}


def _summarize_llm(subgraph: dict, profile: str, evidence: str = "") -> dict:
    client = anthropic.Anthropic()
    ctx = _context(subgraph)
    preamble = f"{profile}\n\n" if profile else ""
    if evidence:
        preamble += evidence + "\n\n"
    resp = client.messages.create(
        model=REASONER_MODEL,
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": (
            f"{preamble}Neo4j subgraph:\n{ctx}\n\n"
            "Write 1-3 sentences describing what this graph contains. "
            "Name the key entities. Do not infer mechanisms — only describe what was returned."
            + (" Include any drug-routing / ML pathway findings from the evidence above."
               if evidence else "")
        )}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {"report": text, "verdict": None}


def reason(question, result, profile="", history="", evidence=""):
    intervention = bool(_INTERVENTION.search(question))
    if ANTHROPIC_API_KEY:
        try:
            return _reason_llm(question, result, intervention, profile, history, evidence)
        except Exception:
            pass
    return _reason_stub(question, result, intervention, evidence)


def _context(subgraph):
    lines = ["NODES:"]
    for n in subgraph["nodes"]:
        label = (n.get("labels") or ["?"])[0]
        name = n.get("label") or n.get("symbol") or n.get("id")
        extra = []
        if n.get("status"):
            extra.append(f"status={n['status']}")
        if n.get("inferred_state"):
            extra.append(f"inferred={n['inferred_state']}")
        if n.get("is_essential_luad") is not None:
            extra.append(f"essential={n['is_essential_luad']}")
        if n.get("effect_direction"):
            extra.append(n["effect_direction"])
        lines.append(f"- ({label}) {name}" + (f" [{', '.join(extra)}]" if extra else ""))
    lines.append("\nEDGES:")
    names = {n.get("id"): (n.get("label") or n.get("symbol") or n.get("id")) for n in subgraph["nodes"]}
    for e in subgraph["edges"]:
        lines.append(f"- {names.get(e['source'], e['source'])} "
                     f"--{e['type']}--> {names.get(e['target'], e['target'])}")
    return "\n".join(lines)


# --- Claude-backed --------------------------------------------------------

class _Report(BaseModel):
    verdict: str
    report: str


def _reason_llm(question, result, intervention, profile="", history="", evidence=""):
    client = anthropic.Anthropic()
    context = _context(result["subgraph"]) or f"(rows: {result['rows'][:20]})"
    # Ground the answer in the uploaded sample profile and the conversation so far.
    preamble = ""
    if profile:
        preamble += profile + "\n\n"
    if history:
        preamble += f"Recent conversation:\n{history}\n\n"
    if evidence:
        preamble += evidence + "\n\n"
    # The drug-routing block is an allowed source beyond the subgraph; flag it
    # so the model uses it and attributes ML predictions honestly.
    extra = (" You may also use the DRUG-ROUTING EVIDENCE above; when you rely on "
             "it, cite ML pathway-vulnerability calls explicitly as ML-predicted "
             "(state the probability and data support level)." if evidence else "")
    if intervention:
        resp = client.messages.parse(
            model=REASONER_MODEL,
            max_tokens=2000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": (
                f"{preamble}Question: {question}\n\nSubgraph:\n{context}\n\n"
                "Decide whether the intervention is beneficial, harmful, negligible, "
                "or uncertain for the LUAD cell state, and write a markdown report "
                "explaining the mechanism." + extra
            )}],
            output_format=_Report,
        )
        p = resp.parsed_output
        verdict = p.verdict if p and p.verdict in VERDICTS else "uncertain"
        return {"report": p.report if p else "", "verdict": verdict}

    resp = client.messages.create(
        model=REASONER_MODEL,
        max_tokens=2000,
        system=_SYSTEM,
        messages=[{"role": "user", "content":
                   f"{preamble}Question: {question}\n\nSubgraph:\n{context}\n\n"
                   "Write a concise markdown cell-state report answering the question." + extra}],
    )
    return {"report": "".join(b.text for b in resp.content if b.type == "text"),
            "verdict": None}


# --- deterministic fallback ----------------------------------------------

def _reason_stub(question, result, intervention, evidence=""):
    note = "_(Generated without an LLM — set ANTHROPIC_API_KEY for full reasoning.)_"
    ev = f"\n\n{evidence}" if evidence else ""
    sub = result["subgraph"]
    if not sub["nodes"]:
        return {"report": f"No matching graph context found.{ev}\n\n{note}",
                "verdict": "uncertain" if intervention else None}
    context = _context(sub)
    if not intervention:
        return {"report": f"## LUAD cell-state report\n\n**Question:** {question}\n\n{context}{ev}\n\n{note}",
                "verdict": None}
    verdict, why = _heuristic_verdict(question, sub)
    return {"report": f"## Predicted effect\n\n**Verdict:** {verdict}\n\n{why}\n\n"
                      f"### Supporting subgraph\n{context}{ev}\n\n{note}",
            "verdict": verdict}


def _heuristic_verdict(question, subgraph):
    """Crude placeholder for the LLM reasoner: inhibiting an activated/GoF-driven
    oncogenic pathway is likely beneficial."""
    q = question.lower()
    inhibiting = bool(re.search(r"inhibit|block|suppress|knock|reduce", q))
    states = {n.get("status") for n in subgraph["nodes"]} | {n.get("inferred_state") for n in subgraph["nodes"]}
    gof = any(n.get("effect_direction") == "gain_of_function" for n in subgraph["nodes"])
    if inhibiting and ("activated" in states or gof):
        return "beneficial", ("Inhibiting a pathway that is activated (or driven by a "
                              "gain-of-function mutation) in LUAD counters an oncogenic driver.")
    if inhibiting:
        return "uncertain", ("The targeted context is not clearly oncogenic in the "
                             "retrieved subgraph; effect is unclear without LLM reasoning.")
    return "uncertain", "Insufficient signal in the subgraph for a confident call without LLM reasoning."
