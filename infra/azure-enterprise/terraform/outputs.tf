output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "vnet_name" {
  value = azurerm_virtual_network.aro.name
}

output "master_subnet_id" {
  value = azurerm_subnet.master.id
}

output "worker_subnet_id" {
  value = azurerm_subnet.worker.id
}

output "workload_identity_client_id" {
  value = azurerm_user_assigned_identity.tradeops.client_id
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.main.id
}

output "azure_monitor_workspace_id" {
  value = azurerm_monitor_workspace.main.id
}
