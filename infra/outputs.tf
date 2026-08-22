output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "storage_account_name" {
  value = azurerm_storage_account.lake.name
}

output "data_factory_name" {
  value = azurerm_data_factory.this.name
}

output "databricks_workspace_url" {
  value = azurerm_databricks_workspace.this.workspace_url
}

output "postgresql_fqdn" {
  value = azurerm_postgresql_flexible_server.source.fqdn
}

output "postgresql_database" {
  value = azurerm_postgresql_flexible_server_database.source.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}

output "log_analytics_workspace_name" {
  value = azurerm_log_analytics_workspace.this.name
}

output "action_group_name" {
  value = azurerm_monitor_action_group.pipeline.name
}

output "unity_catalog_name" {
  value = var.enable_unity_catalog ? databricks_catalog.logitrack[0].name : "disabled"
}

output "sql_warehouse_id" {
  value = var.enable_sql_warehouse ? databricks_sql_endpoint.gold[0].id : "disabled"
}

output "notifications_enabled" {
  value = var.enable_notifications
}
