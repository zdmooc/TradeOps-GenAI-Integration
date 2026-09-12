from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AZURE = ROOT / "infra" / "azure-enterprise"
TF = AZURE / "terraform"


def require(path: Path, *tokens: str) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [token for token in tokens if token not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")


def main() -> None:
    require(
        TF / "versions.tf",
        'required_version = "= 1.16.2"',
        'version = "= 5.2.0"',
        'source  = "hashicorp/azurerm"',
    )
    require(
        TF / "main.tf",
        'resource "azurerm_virtual_network" "aro"',
        'resource "azurerm_subnet" "master"',
        'resource "azurerm_subnet" "worker"',
        'resource "azurerm_user_assigned_identity" "tradeops"',
        'rbac_authorization_enabled    = true',
        'purge_protection_enabled      = true',
        'public_network_access_enabled = false',
        'role_definition_name = "Key Vault Secrets User"',
        'resource "azurerm_monitor_workspace" "main"',
        'resource "azurerm_log_analytics_workspace" "main"',
        'managed_by          = "terraform"',
        'architecture_stage  = "i11"',
    )
    require(
        ROOT / "scripts" / "i11_aro_create.sh",
        "ALLOW_AZURE_COST",
        "ALLOW_PUBLIC_LAB_ACCESS",
        "az aro validate",
        "--master-vm-size",
        "--worker-vm-size",
        "--worker-count",
        "--worker-vm-disk-size-gb",
        "--enable-mi true",
        'ARO_API_VISIBILITY="${ARO_API_VISIBILITY:-Public}"',
        'ARO_INGRESS_VISIBILITY="${ARO_INGRESS_VISIBILITY:-Public}"',
        '--apiserver-visibility "$ARO_API_VISIBILITY"',
        '--ingress-visibility "$ARO_INGRESS_VISIBILITY"',
    )
    create_text = (ROOT / "scripts" / "i11_aro_create.sh").read_text(encoding="utf-8")
    forbidden = ("--client-secret", "client_secret", "AZURE_CLIENT_SECRET")
    if any(token in create_text for token in forbidden):
        raise SystemExit("I11 ARO creation helper must not use a static client secret")

    require(
        ROOT / "scripts" / "i11_aro_destroy.sh",
        "ALLOW_AZURE_DESTROY",
        "ALLOW_AZURE_FOUNDATION_DESTROY",
        "terraform -chdir=infra/azure-enterprise/terraform plan -destroy",
        "terraform -chdir=infra/azure-enterprise/terraform apply",
    )

    require(
        ROOT / "docs" / "20-azure-aro-enterprise-target.md",
        "ARO-first",
        "managed identities",
        "workload identity",
        "Microsoft Foundry",
        "Explicit non-claims",
    )
    print("I11_AZURE_TARGET_VALIDATION_PASS")


if __name__ == "__main__":
    main()
