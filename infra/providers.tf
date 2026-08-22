provider "azurerm" {
  features {}
}

data "azurerm_client_config" "current" {}

provider "azuread" {}

# Autenticación recomendada durante la prueba: `az login`.
provider "databricks" {
  host                        = azurerm_databricks_workspace.this.workspace_url
  azure_workspace_resource_id = azurerm_databricks_workspace.this.id
}
