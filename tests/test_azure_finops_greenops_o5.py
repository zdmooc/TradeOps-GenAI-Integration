from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "o5_azure_finops_greenops_capture.sh"


def test_o5_azure_capture_is_read_only_and_fail_closed():
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'AZURE_SUBSCRIPTION_ID:?required' in text
    assert 'ARO_RESOURCE_GROUP:?required' in text
    assert 'ARO_CLUSTER_NAME:?required' in text
    assert 'O5_COST_START_UTC:?required' in text
    assert 'O5_COST_END_UTC:?required' in text
    assert "az aro create" not in text
    assert "az aro delete" not in text
    assert "terraform apply" not in text


def test_o5_azure_capture_queries_provider_cost_and_carbon_apis():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "Microsoft.CostManagement/query?api-version=2025-03-01" in text
    assert '"type": "ActualCost"' in text
    assert "Microsoft.Carbon/queryCarbonEmissionDataAvailableDateRange?api-version=2025-04-01" in text
    assert "Microsoft.Carbon/carbonEmissionReports?api-version=2025-04-01" in text
    assert '"reportType": "ItemDetailsReport"' in text
    assert '"carbonScopeList": ["Scope1", "Scope2", "Scope3"]' in text
    assert '"categoryType": "ResourceGroup"' in text


def test_o5_azure_capture_redacts_subscription_and_resource_group():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "subscription_fingerprint=sha256:" in text
    assert "<redacted-subscription>" in text
    assert "<redacted-resource-group>" in text
    assert 'grep -R -F "$AZURE_SUBSCRIPTION_ID" "$OUT"' in text
    assert 'grep -R -F "$ARO_RESOURCE_GROUP" "$OUT"' in text
    assert "O5_AZURE_EVIDENCE_REDACTION_PASS" in text


def test_o5_azure_capture_never_auto_satisfies_graduation_gate():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "full_resilience_finops_greenops_gate_claim=false" in text
    assert "provider_cost_claim=REQUIRES_REVIEW_BEFORE_GRADUATION" in text
    assert "provider_cost_claim=NOT_MEASURED" in text
    assert "automatic_graduation_claim=false" in text
    assert "evidence_ready_for_manual_gate_review=true" in text


def test_o5_azure_capture_documents_provider_data_lag():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "NO_ROWS_OR_PROVIDER_LAG" in text
    assert "same-day lab emissions may not yet exist in Carbon Optimization" in text
    assert "SET_O5_CARBON_MONTH_WHEN_PROVIDER_MONTH_IS_AVAILABLE" in text
