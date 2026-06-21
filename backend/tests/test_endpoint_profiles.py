import json

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def _parse_sse(text: str) -> dict[str, list[dict]]:
  events: dict[str, list[dict]] = {}
  for block in text.strip().split("\n\n"):
    event_name = None
    payload = None
    for line in block.splitlines():
      if line.startswith("event: "):
        event_name = line[len("event: ") :].strip()
      elif line.startswith("data: "):
        payload = json.loads(line[len("data: ") :])
    if event_name and payload is not None:
      events.setdefault(event_name, []).append(payload)
  return events


def test_profiles_stream_endpoint_returns_sse_events():
  csv_content = (
    "mutation_id,gene,estimated_effect\n"
    "mut_EGFR_L858R,EGFR,activating\n"
    "mut_KRAS_G12D,KRAS,activating\n"
  )

  response = client.post(
    "/profiles/stream",
    files={"file": ("profile.csv", csv_content, "text/csv")},
  )

  assert response.status_code == 200
  assert response.headers["content-type"].startswith("text/event-stream")

  events = _parse_sse(response.text)

  assert "started" in events
  assert events["mutations_extracted"][0]["count"] == 2
  assert len(events["mutation_hydrated"]) == 2
  assert len(events["protein_extracted"]) == 2
  assert len(events["pathways_extracted"]) == 2
  assert len(events["pathway_updated"]) == 2
  assert events["complete"][0]["profile_id"]
  assert len(events["complete"][0]["profile_pathway"]) == 2