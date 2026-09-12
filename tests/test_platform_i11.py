from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF = ROOT / "infra" / "azure-enterprise" / "terraform"


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_i11_terraform_versions_are_pinned():
    value = text("infra/azure-enterprise/terraform/versions.tf")
    assert '= 1.16.2' in value
    assert '= 5.2.0' in value


def test_i11_aro_has_dedicated_master_and_worker_subnets():
    value = text("infra/azure-enterprise/terraform/main.tf")
    assert 'azurerm_subnet" "master' in value
    assert 'azurerm_subnet" "worker' in value
    assert "10.60.0.0/23" in value
    assert "10.60.2.0/23" in value


def test_i11_key_vault_is_private_rbac_and_purge_protected():
    value = text("infra/azure-enterprise/terraform/main.tf")
    assert "rbac_authorization_enabled    = true" in value
    assert "purge_protection_enabled      = true" in value
    assert "public_network_access_enabled = false" in value


def test_i11_key_vault_uses_private_endpoint_and_dns():
    value = text("infra/azure-enterprise/terraform/main.tf")
    assert 'resource "azurerm_private_endpoint" "key_vault"' in value
    assert "privatelink.vaultcore.azure.net" in value


def test_i11_workload_identity_is_least_privilege_for_secrets():
    value = text("infra/azure-enterprise/terraform/main.tf")
    assert 'resource "azurerm_user_assigned_identity" "tradeops"' in value
    assert 'role_definition_name = "Key Vault Secrets User"' in value


def test_i11_observability_foundation_exists():
    value = text("infra/azure-enterprise/terraform/main.tf")
    assert 'azurerm_log_analytics_workspace' in value
    assert 'azurerm_monitor_workspace' in value


def test_i11_required_finops_tags_exist():
    value = text("infra/azure-enterprise/terraform/main.tf")
    for tag in ("workload", "environment", "cost_center", "data_classification", "managed_by"):
        assert tag in value


def test_i11_aro_target_is_private_managed_identity_and_explicitly_sized():
    value = text("scripts/i11_aro_create.sh")
    assert "--enable-mi true" in value
    assert "--apiserver-visibility Private" in value
    assert "--ingress-visibility Private" in value
    assert 'ARO_MASTER_VM_SIZE="${ARO_MASTER_VM_SIZE:-Standard_D8s_v5}"' in value
    assert 'ARO_WORKER_VM_SIZE="${ARO_WORKER_VM_SIZE:-Standard_D4s_v5}"' in value
    assert 'ARO_WORKER_COUNT="${ARO_WORKER_COUNT:-3}"' in value
    assert 'ARO_WORKER_DISK_GB="${ARO_WORKER_DISK_GB:-128}"' in value
    assert "--master-vm-size" in value
    assert "--worker-vm-size" in value
    assert "--worker-count" in value
    assert "--worker-vm-disk-size-gb" in value


def test_i11_aro_creation_is_fail_closed_for_cost():
    value = text("scripts/i11_aro_create.sh")
    assert 'ALLOW_AZURE_COST:-0' in value
    assert "Refusing paid Azure creation" in value
    assert "az aro validate" in value


def test_i11_aro_destroy_is_fail_closed_and_can_destroy_foundation():
    value = text("scripts/i11_aro_destroy.sh")
    assert 'ALLOW_AZURE_DESTROY:-0' in value
    assert 'ALLOW_AZURE_FOUNDATION_DESTROY:-0' in value
    assert "terraform -chdir=infra/azure-enterprise/terraform plan -destroy" in value
    assert "terraform -chdir=infra/azure-enterprise/terraform apply" in value


def test_i11_aro_target_has_no_static_client_secret():
    value = text("scripts/i11_aro_create.sh")
    assert "--client-secret" not in value
    assert "AZURE_CLIENT_SECRET" not in value


def test_i11_preflight_uses_aro_validate_and_version_check():
    value = text("scripts/i11_aro_preflight.sh")
    assert "az aro validate" in value
    assert "az aro get-versions" in value


def test_i11_foundry_is_optional_not_default_deployment():
    value = text("docs/20-azure-aro-enterprise-target.md")
    assert "Microsoft Foundry is optional" in value
    assert "No Foundry resource is automatically created" in value


def test_i11_reference_reuse_is_explicit():
    value = text("docs/20-azure-aro-enterprise-target.md")
    assert "mayabank-azure-cloud-ai-platform" in value
    assert "dfe3909dc6904ac502aac857eb55f8ac2a0d1309" in value
