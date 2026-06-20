import pytest

from backend.agent import cypher


def test_guard_allows_reads():
    assert cypher.is_read_only("MATCH (n) RETURN n")
    assert cypher.is_read_only("MATCH (p:Pathway)-[r]->(q) RETURN p, r, q LIMIT 5")


@pytest.mark.parametrize("query", [
    "MATCH (n) CREATE (x)",
    "MATCH (n) DETACH DELETE n",
    "MATCH (n) SET n.x = 1",
    "MERGE (a:Gene {symbol: 'X'})",
    "DROP CONSTRAINT c",
    "LOAD CSV FROM 'f' AS line RETURN line",
])
def test_guard_blocks_writes(query):
    assert not cypher.is_read_only(query)


def test_run_read_rejects_write():
    with pytest.raises(ValueError):
        cypher.run_read("MATCH (n) DELETE n")


def test_run_read_returns_rows_and_subgraph():
    result = cypher.run_read("MATCH (p:Pathway) RETURN p LIMIT 3")
    assert len(result["rows"]) == 3
    assert len(result["subgraph"]["nodes"]) == 3
    assert all("Pathway" in n["labels"] for n in result["subgraph"]["nodes"])


def test_full_graph_has_complete_counts():
    g = cypher.full_graph()
    assert len(g["nodes"]) == 157
    assert len(g["edges"]) == 298


def test_schema_text_is_the_team_doc():
    text = cypher.schema_text()
    assert "Node Labels" in text and "PERTURBS" in text
