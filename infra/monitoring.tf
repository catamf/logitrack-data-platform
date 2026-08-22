resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_monitor_action_group" "pipeline" {
  name                = "ag-${local.prefix}"
  resource_group_name = azurerm_resource_group.this.name
  short_name          = substr("ag${var.environment}", 0, 12)
  tags                = local.tags

  email_receiver {
    name                    = "pipeline-email"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "adf" {
  name                       = "diag-adf"
  target_resource_id         = azurerm_data_factory.this.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "PipelineRuns"
  }
  enabled_log {
    category = "ActivityRuns"
  }
  enabled_log {
    category = "TriggerRuns"
  }
  enabled_metric {
    category = "AllMetrics"
  }
}

# Notificación inmediata ante cualquier fallo de pipeline ADF.
resource "azurerm_monitor_metric_alert" "adf_failure" {
  name                = "alert-${local.prefix}-pipeline-failure"
  resource_group_name = azurerm_resource_group.this.name
  scopes              = [azurerm_data_factory.this.id]
  description         = "Fallo detectado en Azure Data Factory para LogiTrack"
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"
  enabled             = true

  criteria {
    metric_namespace = "Microsoft.DataFactory/factories"
    metric_name      = "PipelineFailedRuns"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action {
    action_group_id = azurerm_monitor_action_group.pipeline.id
  }
}

# Auditoría de Azure Databricks. Las categorías se consultan dinámicamente para evitar
# depender de una lista fija que pueda variar por región o versión del servicio.
data "azurerm_monitor_diagnostic_categories" "databricks" {
  resource_id = azurerm_databricks_workspace.this.id
}

resource "azurerm_monitor_diagnostic_setting" "databricks" {
  name                       = "diag-databricks"
  target_resource_id         = azurerm_databricks_workspace.this.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  dynamic "enabled_log" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.databricks.log_category_types)
    content {
      category = enabled_log.value
    }
  }
}
