resource "azurerm_data_factory" "this" {
  name                = "adf-${local.prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "adf_storage" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_data_factory.this.identity[0].principal_id
}

resource "azurerm_role_assignment" "adf_key_vault" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_data_factory.this.identity[0].principal_id
}

resource "azurerm_role_assignment" "adf_databricks" {
  scope                = azurerm_databricks_workspace.this.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_data_factory.this.identity[0].principal_id
}

resource "azurerm_data_factory_linked_service_key_vault" "this" {
  name            = "ls_key_vault"
  data_factory_id = azurerm_data_factory.this.id
  key_vault_id    = azurerm_key_vault.this.id
  depends_on      = [azurerm_role_assignment.adf_key_vault]
}

resource "azurerm_data_factory_linked_service_data_lake_storage_gen2" "lake" {
  name                 = "ls_adls_gen2"
  data_factory_id      = azurerm_data_factory.this.id
  url                  = azurerm_storage_account.lake.primary_dfs_endpoint
  use_managed_identity = true
  depends_on           = [azurerm_role_assignment.adf_storage]
}

# PostgreSqlV2 permite mantener la contraseña en Key Vault en lugar de
# incrustarla en Terraform/ADF.
resource "azurerm_data_factory_linked_custom_service" "postgres" {
  name            = "ls_postgresql"
  data_factory_id = azurerm_data_factory.this.id
  type            = "PostgreSqlV2"

  type_properties_json = jsonencode({
    server             = azurerm_postgresql_flexible_server.source.fqdn
    port               = 5432
    database           = azurerm_postgresql_flexible_server_database.source.name
    username           = var.postgres_admin_login
    authenticationType = "Basic"
    sslMode            = 3
    password = {
      type = "AzureKeyVaultSecret"
      store = {
        referenceName = azurerm_data_factory_linked_service_key_vault.this.name
        type          = "LinkedServiceReference"
      }
      secretName = azurerm_key_vault_secret.postgres_password.name
    }
  })
}

# PostgreSQL V2 se administra mediante AzAPI porque el recurso custom de
# AzureRM no materializa authenticationType en ARM para este conector.
resource "azapi_resource" "postgres_v2" {
  type      = "Microsoft.DataFactory/factories/linkedservices@2018-06-01"
  parent_id = azurerm_data_factory.this.id
  name      = "ls_postgresql_v2"

  body = {
    properties = {
      type    = "AzurePostgreSql"
      version = "2.0"

      typeProperties = {
        server             = azurerm_postgresql_flexible_server.source.fqdn
        port               = 5432
        database           = azurerm_postgresql_flexible_server_database.source.name
        username           = var.postgres_admin_login
        authenticationType = "Basic"
        sslMode            = 5

        password = {
          type = "AzureKeyVaultSecret"

          store = {
            referenceName = azurerm_data_factory_linked_service_key_vault.this.name
            type          = "LinkedServiceReference"
          }

          secretName = azurerm_key_vault_secret.postgres_password.name
        }
      }
    }
  }

  schema_validation_enabled = false

  depends_on = [
    azurerm_data_factory_linked_service_key_vault.this
  ]
}

# Dataset heredado. Se mantiene temporalmente durante la migración para evitar
# eliminarlo mientras el pipeline de ADF todavía lo referencia en Azure.
resource "azurerm_data_factory_custom_dataset" "postgres_query" {
  name            = "ds_postgresql_query"
  data_factory_id = azurerm_data_factory.this.id
  type            = "PostgreSqlV2Table"

  linked_service {
    name = azapi_resource.postgres_v2.name
  }

  type_properties_json = jsonencode({
    table = "control_ingesta"
  })
}

# Dataset compatible con Azure Database for PostgreSQL connector 2.0.
# El pipeline se migrará primero a este recurso antes de eliminar el dataset
# heredado.
resource "azurerm_data_factory_custom_dataset" "postgres_query_v2" {
  name            = "ds_postgresql_query_v2"
  data_factory_id = azurerm_data_factory.this.id
  type            = "AzurePostgreSqlTable"

  linked_service {
    name = azapi_resource.postgres_v2.name
  }

  # Las actividades usan consultas SQL, por lo que la tabla funciona como
  # valor genérico del dataset.
  type_properties_json = jsonencode({
    table = "control_ingesta"
  })
}

resource "azurerm_data_factory_dataset_parquet" "bronze" {
  name                = "ds_bronze_parquet"
  data_factory_id     = azurerm_data_factory.this.id
  linked_service_name = azurerm_data_factory_linked_service_data_lake_storage_gen2.lake.name

  parameters = {
    tabla = ""
  }

  azure_blob_fs_location {
    file_system          = azurerm_storage_data_lake_gen2_filesystem.layers["bronze"].name
    path                 = "@concat(dataset().tabla, '/anio=', formatDateTime(utcNow(),'yyyy'), '/mes=', formatDateTime(utcNow(),'MM'), '/dia=', formatDateTime(utcNow(),'dd'))"
    dynamic_path_enabled = true
  }

  compression_codec = "snappy"
}

resource "azurerm_data_factory_linked_service_azure_databricks" "this" {
  name                = "ls_databricks"
  data_factory_id     = azurerm_data_factory.this.id
  adb_domain          = "https://${azurerm_databricks_workspace.this.workspace_url}"
  msi_workspace_id    = azurerm_databricks_workspace.this.id
  existing_cluster_id = databricks_cluster.etl.id

  depends_on = [
    azurerm_role_assignment.adf_databricks,
    databricks_service_principal.adf_mi
  ]
}

resource "azurerm_data_factory_pipeline" "notify" {
  name            = "pl_logitrack_notificar"
  data_factory_id = azurerm_data_factory.this.id
  description     = "Notificacion reutilizable por webhook almacenado en Key Vault"

  parameters = {
    notifications_enabled = "false"
    key_vault_uri         = ""
    message               = ""
    fail_after            = "false"
    failure_code          = "LOGITRACK_NOTIFICATION"
  }

  activities_json = jsonencode(
    jsondecode(
      file("${path.module}/../orchestration/adf/pipeline_notificar.json")
    )["properties"]["activities"]
  )

  depends_on = [
    azurerm_data_factory_linked_service_key_vault.this
  ]
}

resource "azurerm_data_factory_pipeline" "main" {
  name            = "pl_logitrack_end_to_end"
  data_factory_id = azurerm_data_factory.this.id
  description     = "Ingesta incremental y orquestacion Bronze-Silver-Gold"

  parameters = {
    environment           = var.environment
    storage_account_name  = azurerm_storage_account.lake.name
    catalog_name          = local.catalog_name
    use_unity_catalog     = tostring(var.enable_unity_catalog)
    carga_completa        = "false"
    force_volume_alert    = "false"
    key_vault_uri         = azurerm_key_vault.this.vault_uri
    notifications_enabled = tostring(var.enable_notifications)
  }

  activities_json = jsonencode(
    jsondecode(
      file("${path.module}/../orchestration/adf/pipeline_principal.json")
    )["properties"]["activities"]
  )

  # Durante esta etapa el pipeline pasa a depender del dataset nuevo.
  # El dataset heredado se eliminará únicamente después de comprobar que
  # Azure ya no tiene ninguna referencia hacia él.
  depends_on = [
    azurerm_data_factory_custom_dataset.postgres_query_v2,
    azurerm_data_factory_dataset_parquet.bronze,
    azurerm_data_factory_linked_service_azure_databricks.this,
    databricks_notebook.pipeline,
    azurerm_data_factory_pipeline.notify
  ]
}

# 07:00 UTC = 02:00 en Colombia (UTC-5). Se usa UTC para evitar ambigüedad de DST.
resource "azurerm_data_factory_trigger_schedule" "daily" {
  name            = "trg_diario_0200_bogota"
  data_factory_id = azurerm_data_factory.this.id
  pipeline_name   = azurerm_data_factory_pipeline.main.name
  activated       = var.enable_daily_trigger
  interval        = 1
  frequency       = "Day"
  time_zone       = "UTC"

  schedule {
    hours   = [7]
    minutes = [0]
  }

  pipeline_parameters = {
    environment           = var.environment
    storage_account_name  = azurerm_storage_account.lake.name
    catalog_name          = local.catalog_name
    use_unity_catalog     = tostring(var.enable_unity_catalog)
    carga_completa        = "false"
    force_volume_alert    = "false"
    key_vault_uri         = azurerm_key_vault.this.vault_uri
    notifications_enabled = tostring(var.enable_notifications)
  }
}

# Registra la Managed Identity de ADF dentro del workspace para que pueda
# adjuntarse al cluster.
data "azuread_service_principal" "adf_mi" {
  object_id  = azurerm_data_factory.this.identity[0].principal_id
  depends_on = [azurerm_data_factory.this]
}

resource "databricks_service_principal" "adf_mi" {
  application_id   = data.azuread_service_principal.adf_mi.client_id
  active           = true
  workspace_access = true
}

# Segmentación de compute: el pipeline usa el cluster ETL; Analyst no recibe
# permisos sobre él.
# Los administradores del workspace conservan CAN_MANAGE de forma implícita
# en Databricks.
resource "databricks_permissions" "etl_cluster" {
  cluster_id = databricks_cluster.etl.id

  access_control {
    service_principal_name = databricks_service_principal.adf_mi.application_id
    permission_level       = "CAN_ATTACH_TO"
  }
}
