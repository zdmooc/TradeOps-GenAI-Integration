from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "d090_patch_prometheus_config.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("d090_patch_prometheus_config", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adds_ai_access_to_multiline_tradeops_job():
    helper = load_helper()
    source = """global:
  scrape_interval: 15s
scrape_configs:
  - job_name: tradeops-apis
    static_configs:
      - targets:
          - market-data:8011
          - workflow-api:8012
          - genai-api:8013
          - rag-api:8014
"""
    rendered, changed = helper.ensure_ai_access_scrape(source)
    assert changed is True
    assert rendered.count("ai-access-policy:8020") == 1
    assert "job_name: ai-access-policy" in rendered


def test_adds_ai_access_when_existing_targets_use_inline_yaml():
    helper = load_helper()
    source = """global:
  scrape_interval: 5s
rule_files:
  - /etc/prometheus/alerts.yml
scrape_configs:
  - job_name: genai-api
    static_configs:
      - targets: ["genai-api:8013"]
  - job_name: rag-api
    static_configs:
      - targets: ["rag-api:8014"]
"""
    rendered, changed = helper.ensure_ai_access_scrape(source)
    assert changed is True
    assert 'targets: ["ai-access-policy:8020"]' in rendered


def test_inserts_before_next_top_level_section():
    helper = load_helper()
    source = """global:
  scrape_interval: 15s
scrape_configs:
  - job_name: genai-api
    static_configs:
      - targets: ["genai-api:8013"]
alerting:
  alertmanagers: []
"""
    rendered, changed = helper.ensure_ai_access_scrape(source)
    assert changed is True
    assert rendered.index("job_name: ai-access-policy") < rendered.index("alerting:")


def test_is_idempotent():
    helper = load_helper()
    source = """scrape_configs:
  - job_name: ai-access-policy
    static_configs:
      - targets: ["ai-access-policy:8020"]
"""
    rendered, changed = helper.ensure_ai_access_scrape(source)
    assert changed is False
    assert rendered == source


def test_fails_closed_without_scrape_configs():
    helper = load_helper()
    try:
        helper.ensure_ai_access_scrape("global:\n  scrape_interval: 15s\n")
    except ValueError as exc:
        assert "scrape_configs" in str(exc)
    else:
        raise AssertionError("missing scrape_configs must fail closed")
