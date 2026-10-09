"""AA8 synthetic CRC inventory assertions without kube API requests."""
from services.solution_architect.crc_snapshot_contract import verify_readonly_inventory


def sample():
    return {
        "scope": "d099.readonly.inventory",
        "namespace": "instant-payments-local",
        "cluster_version": "4.22.7",
        "observed_utc": "2026-10-09T13:00:00Z",
        "workloads": [
            {"kind": "Deployment", "name": "synthetic-notification", "ready": True},
        ],
        "read_only": True,
    }


def test_synthetic_readonly_inventory_is_static_not_live():
    r = verify_readonly_inventory(sample())
    assert r["status"] == "AA8_SANITIZED_SNAPSHOT_STATIC_PASS"
    assert not r["runtime_connection_made"]
    assert not r["AA8_CRC_READONLY_VALIDATED"]


def test_namespace_out_of_scope_or_kube_secret_cannot_pass():
    m = sample()
    m["namespace"] = "kube-system"
    m["workloads"].append({"kind": "Secret", "name": "password", "ready": True})
    r = verify_readonly_inventory(m)
    assert "NAMESPACE_OUT_OF_SCOPE" in r["violations"]
    assert "WORKLOAD_KIND_DENIED" in r["violations"]


def test_unreviewed_sensitive_fields_rejected():
    m = sample()
    m["workloads"][0]["env"] = [{"value": "SECRET"}]
    m["kubeconfig"] = "SENSITIVE"
    r = verify_readonly_inventory(m)
    assert "WORKLOAD_FIELDS_UNSAFE" in r["violations"]
    assert "INVENTORY_SCHEMA_NOT_ALLOWLISTED" in r["violations"]


def test_no_change_claim_or_write_allowed():
    m = sample()
    m["read_only"] = False
    assert "READ_ONLY_FALSE_OR_MISSING" in verify_readonly_inventory(m)["violations"]


def test_bad_utc_and_cluster_version_rejected():
    m = sample()
    m["cluster_version"] = "PRODUCTION_CLUSTER"
    m["observed_utc"] = "yesterday"
    r = verify_readonly_inventory(m)
    assert "CLUSTER_VERSION_INVALID" in r["violations"]
    assert "UTC_TIMESTAMP_MISSING" in r["violations"]
