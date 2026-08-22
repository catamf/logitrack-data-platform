resource "random_password" "postgres" {
  length           = 24
  special          = true
  override_special = "!@#%_-"
}

resource "azurerm_postgresql_flexible_server" "source" {
  name                          = "psql-${local.prefix}-${random_string.suffix.result}"
  resource_group_name           = azurerm_resource_group.this.name
  location                      = azurerm_resource_group.this.location
  version                       = "17"
  public_network_access_enabled = true
  administrator_login           = var.postgres_admin_login
  administrator_password        = random_password.postgres.result
  storage_mb                    = var.postgres_storage_mb
  sku_name                      = var.postgres_sku
  auto_grow_enabled             = true
  backup_retention_days         = 7
  tags                          = local.tags
}

resource "azurerm_postgresql_flexible_server_database" "source" {
  name      = var.postgres_database
  server_id = azurerm_postgresql_flexible_server.source.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Permite conexión desde servicios de Azure, incluido ADF.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.source.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "developer" {
  count            = var.developer_public_ip == "" ? 0 : 1
  name             = "DeveloperMachine"
  server_id        = azurerm_postgresql_flexible_server.source.id
  start_ip_address = var.developer_public_ip
  end_ip_address   = var.developer_public_ip
}
