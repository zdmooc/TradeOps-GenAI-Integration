locals {
  name = lower("${var.prefix}-${var.environment}")
  tags = {
    workload            = "tradeops-agentic-ai"
    environment         = var.environment
    cost_center         = var.cost_center
    data_classification = var.data_classification
    managed_by          = "terraform"
    architecture_stage  = "i11"
  }
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "aro" {
  name                = "vnet-${local.name}-aro"
  address_space       = ["10.60.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_subnet" "master" {
  name                 = "snet-aro-master"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.aro.name
  address_prefixes     = ["10.60.0.0/23"]
}

resource "azurerm_subnet" "worker" {
  name                 = "snet-aro-worker"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.aro.name
  address_prefixes     = ["10.60.2.0/23"]
}

resource "azurerm_subnet" "shared" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.aro.name
  address_prefixes     = ["10.60.4.0/24"]
}

resource "azurerm_user_assigned_identity" "tradeops" {
  name                = "id-${local.name}-workload"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_key_vault" "main" {
  name                          = substr(replace("${var.prefix}${var.environment}kv", "-", ""), 0, 24)
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 30
  public_network_access_enabled = false
  tags                          = local.tags
}

resource "azurerm_role_assignment" "tradeops_key_vault_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.tradeops.principal_id
}

resource "azurerm_private_dns_zone" "key_vault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "key_vault" {
  name                 = "link-${local.name}-kv"
  private_dns_zone_id  = azurerm_private_dns_zone.key_vault.id
  virtual_network_id   = azurerm_virtual_network.aro.id
  registration_enabled = false
  tags                 = local.tags
}

resource "azurerm_private_endpoint" "key_vault" {
  name                = "pe-${local.name}-kv"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.shared.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-${local.name}-kv"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.key_vault.id]
  }
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${local.name}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_monitor_workspace" "main" {
  name                          = "amw-${local.name}"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  public_network_access_enabled = false
  tags                          = local.tags
}
