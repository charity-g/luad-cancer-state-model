
from __future__ import annotations

from typing import  Optional

import requests
from backend.agents.create_graph.model import MutationProteinEffect, ProteinResolutionError, ProteinRecord

def _extract_gene_symbol(mutation: MutationProteinEffect) -> str:
    """
    Resolve the best possible gene/protein symbol from the mutation object.
    """

    # priority order
    candidates = [
        mutation.identifiers.get("gene_symbol"),
        mutation.identifiers.get("hugo_symbol"),
        mutation.identifiers.get("symbol"),
        mutation.protein,
    ]

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise ProteinResolutionError(
        f"Could not determine protein/gene symbol for mutation "
        f"{mutation.mutation_id}"
    )


def _query_kegg_gene(symbol: str) -> tuple[str, str]:
    """
    Query KEGG genes endpoint.

    Returns:
        (kegg_gene_id, raw_line)
    """

    url = f"https://rest.kegg.jp/find/genes/{symbol}"

    response = requests.get(url, timeout=15)

    if response.status_code != 200:
        raise ProteinResolutionError(
            f"KEGG request failed with status {response.status_code}"
        )

    text = response.text.strip()

    if not text:
        raise ProteinResolutionError(
            f"No KEGG gene entry found for symbol: {symbol}"
        )

    # take first match
    first_line = text.splitlines()[0]

    # example:
    # hsa:1956    EGFR; epidermal growth factor receptor
    kegg_gene_id = first_line.split("\t")[0]

    return kegg_gene_id, first_line


def _query_kegg_ko(kegg_gene_id: str) -> Optional[str]:
    """
    Resolve KEGG Orthology (KO) identifier from KEGG gene entry.
    """

    url = f"https://rest.kegg.jp/get/{kegg_gene_id}"

    response = requests.get(url, timeout=15)

    if response.status_code != 200:
        return None

    text = response.text

    for line in text.splitlines():
        if line.startswith("ORTHOLOGY"):
            # example:
            # ORTHOLOGY  K04361  epidermal growth factor receptor
            parts = line.split()

            for part in parts:
                if part.startswith("K"):
                    return part

    return None


def extract_protein_for_mutation(
    mutation: MutationProteinEffect,
) -> ProteinRecord:
    """
    Map a mutation interpretation object to a KEGG protein/gene record.

    Workflow:
        mutation -> gene/protein symbol -> KEGG gene -> optional KO mapping

    Raises:
        ProteinResolutionError if no valid mapping exists.
    """

    symbol = _extract_gene_symbol(mutation)

    kegg_gene_id, raw_line = _query_kegg_gene(symbol)

    ko_id = _query_kegg_ko(kegg_gene_id)

    # parse description
    description = None

    if "\t" in raw_line:
        description = raw_line.split("\t", 1)[1]

    return ProteinRecord(
        query=symbol,
        gene_symbol=symbol,
        uniprot_id=mutation.identifiers.get("uniprot_ac") or mutation.identifiers.get("uniprot_id"),
        entrez_gene_id=mutation.identifiers.get("entrez_gene_id"),
        kegg_gene_id=kegg_gene_id,
        kegg_ko_id=ko_id,
        kegg_description=description,
        raw_response=raw_line,
    )
