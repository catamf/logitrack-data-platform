resource "azurerm_databricks_workspace" "this" {
  name                = "dbw-${local.prefix}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = var.databricks_sku
  tags                = local.tags
}

data "databricks_spark_version" "lts" {
  long_term_support = true
  depends_on        = [azurerm_databricks_workspace.this]
}

data "databricks_node_type" "smallest" {
  local_disk = true
  depends_on = [azurerm_databricks_workspace.this]
}

data "databricks_current_user" "me" {
  depends_on = [azurerm_databricks_workspace.this]
}

resource "databricks_cluster" "etl" {
  cluster_name            = "etl-${local.prefix}"
  spark_version           = data.databricks_spark_version.lts.id
  node_type_id            = data.databricks_node_type.smallest.id
  autotermination_minutes = 15
  data_security_mode      = "USER_ISOLATION"

  autoscale {
    min_workers = var.databricks_min_workers
    max_workers = var.databricks_max_workers
  }

  custom_tags = {
    Environment = var.environment
    Project     = var.project
  }
}

locals {
  notebook_sources = {
    "00_common"            = "00_common.py"
    "00_auditar_bronze"    = "00_auditar_bronze.py"
    "01_procesar_silver"   = "01_procesar_silver.py"
    "02_procesar_gold"     = "02_procesar_gold.py"
    "03_calidad_gold"      = "03_calidad_gold.py"
    "04_resumen_ejecucion" = "04_resumen_ejecucion.py"
  }
}

resource "databricks_notebook" "pipeline" {
  for_each = local.notebook_sources
  source   = "${path.module}/../pipelines/databricks/${each.value}"
  path     = "/Shared/logitrack/${var.environment}/${each.key}"
}

# Principal opcional para demostrar el rol Analista con una sesión real.
# Los usuarios agregados al workspace pueden recibir privilegios de Unity Catalog;
# a diferencia de los grupos workspace-local, que no son válidos para GRANT en Unity Catalog.
resource "databricks_user" "analyst" {
  count                 = var.analyst_user_name == "" ? 0 : 1
  user_name             = var.analyst_user_name
  display_name          = "Analista LogiTrack ${var.environment}"
  workspace_access      = true
  databricks_sql_access = true
}

# Unity Catalog es condicional porque un laboratorio/suscripción puede requerir primero
# que un metastore esté asignado al workspace.
resource "databricks_storage_credential" "lake" {
  count = var.enable_unity_catalog ? 1 : 0
  name  = "cred_${local.catalog_name}"

  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.uc.id
  }

  comment    = "Credencial administrada por Terraform para ADLS LogiTrack"
  depends_on = [azurerm_role_assignment.uc_storage]
}

resource "databricks_external_location" "layers" {
  for_each = var.enable_unity_catalog ? toset(["bronze", "silver", "gold"]) : toset([])
  name     = "ext_${local.catalog_name}_${each.value}"
  url      = "abfss://${each.value}@${azurerm_storage_account.lake.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.lake[0].name
  comment  = "Capa ${each.value} de LogiTrack"
  depends_on = [azurerm_storage_data_lake_gen2_filesystem.layers]
}

resource "databricks_catalog" "logitrack" {
  count   = var.enable_unity_catalog ? 1 : 0
  name    = local.catalog_name
  comment = "Catalogo LogiTrack ${var.environment}"
}

resource "databricks_schema" "layers" {
  for_each     = var.enable_unity_catalog ? toset(["bronze", "silver", "gold"]) : toset([])
  catalog_name = databricks_catalog.logitrack[0].name
  name         = each.value
  comment      = "Capa ${each.value}"
  storage_root = "abfss://${each.value}@${azurerm_storage_account.lake.name}.dfs.core.windows.net/managed/"
  depends_on   = [databricks_external_location.layers]
}

# Tres roles lógicos:
# - Data Engineer técnico: Managed Identity de ADF, lectura/escritura en todas las capas.
# - Analyst: usuario opcional, solo SELECT en Gold.
# - Admin: usuario que ejecuta Terraform, control completo sobre los objetos de datos.
resource "databricks_grants" "catalog" {
  count   = var.enable_unity_catalog ? 1 : 0
  catalog = databricks_catalog.logitrack[0].name

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["USE_CATALOG"]
  }

  dynamic "grant" {
    for_each = var.analyst_user_name == "" ? [] : [1]
    content {
      principal  = databricks_user.analyst[0].user_name
      privileges = ["USE_CATALOG"]
    }
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }
}

resource "databricks_grants" "bronze" {
  count  = var.enable_unity_catalog ? 1 : 0
  schema = "${databricks_catalog.logitrack[0].name}.bronze"

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE"]
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }

  depends_on = [databricks_schema.layers]
}

resource "databricks_grants" "silver" {
  count  = var.enable_unity_catalog ? 1 : 0
  schema = "${databricks_catalog.logitrack[0].name}.silver"

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE"]
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }

  depends_on = [databricks_schema.layers]
}

resource "databricks_grants" "gold" {
  count  = var.enable_unity_catalog ? 1 : 0
  schema = "${databricks_catalog.logitrack[0].name}.gold"

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE"]
  }

  dynamic "grant" {
    for_each = var.analyst_user_name == "" ? [] : [1]
    content {
      principal  = databricks_user.analyst[0].user_name
      privileges = ["USE_SCHEMA", "SELECT"]
    }
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }

  depends_on = [databricks_schema.layers]
}

resource "databricks_sql_endpoint" "gold" {
  count            = var.enable_sql_warehouse ? 1 : 0
  name             = "sql-${local.prefix}"
  cluster_size     = "X-Small"
  max_num_clusters = 1
  auto_stop_mins   = 10
}

# Segmentación de consumo: Analyst usa el SQL Warehouse, pero no el cluster ETL.
# ADF no necesita este compute porque su función es orquestar el pipeline, no consumir Gold.
resource "databricks_permissions" "sql_warehouse" {
  count           = var.enable_sql_warehouse ? 1 : 0
  sql_endpoint_id = databricks_sql_endpoint.gold[0].id

  dynamic "access_control" {
    for_each = var.analyst_user_name == "" ? [] : [1]
    content {
      user_name        = databricks_user.analyst[0].user_name
      permission_level = "CAN_USE"
    }
  }
}

# El motor de Databricks necesita acceso a los paths externos para registrar y escribir tablas Delta.
resource "databricks_grants" "external_locations" {
  for_each          = var.enable_unity_catalog ? databricks_external_location.layers : {}
  external_location = each.value.id

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE"]
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }
}
