from services.genai_api.rag import SimpleRAG
import tempfile
from pathlib import Path
import json

def test_rag_returns_docs():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "a.md").write_text("risk rule: max exposure 100", encoding="utf-8")
        Path(d, "b.md").write_text("runbook kafka lag consumer", encoding="utf-8")
        rag = SimpleRAG(d)
        rag.load()
        hits = rag.query("max exposure", top_k=2)
        assert hits
        assert hits[0][0] in ("a.md","b.md")

def test_event_schema_files_parse():
    schema_dir = Path("schemas/events")
    files = list(schema_dir.glob("*.schema.json"))
    assert files, "no schema files"
    for fp in files:
        json.loads(fp.read_text(encoding="utf-8"))
