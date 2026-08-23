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
  is_pinned               = true

  is_single_node = var.databricks_single_node ? true : null
  kind           = var.databricks_single_node ? "CLASSIC_PREVIEW" : null

  data_security_mode = var.databricks_single_node ? "DATA_SECURITY_MODE_STANDARD" : "USER_ISOLATION"

  dynamic "autoscale" {
    for_each = var.databricks_single_node ? [] : [1]

    content {
      min_workers = var.databricks_min_workers
      max_workers = var.databricks_max_workers
    }
  }

  custom_tags = {
    Environment = var.environment
    Project     = var.project
  }

  # Databricks agrega estas propiedades automáticamente
  # cuando is_single_node = true.
  lifecycle {
    ignore_changes = [
      spark_conf["spark.databricks.cluster.profile"],
      spark_conf["spark.master"],
      custom_tags["ResourceClass"]
    ]
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

# Directorio restringido para los notebooks de ingenieria/ETL.
# Se evita /Shared porque esa carpeta concede permisos amplios al grupo users.
resource "databricks_directory" "etl_notebooks" {
  path = "/Engineering/logitrack/${var.environment}"
}

# ADF puede ejecutar los notebooks del pipeline, pero no se concede acceso
# al rol Analyst. Los administradores conservan CAN_MANAGE por defecto.
resource "databricks_permissions" "etl_notebooks" {
  directory_id = databricks_directory.etl_notebooks.object_id

  access_control {
    service_principal_name = databricks_service_principal.adf_mi.application_id
    permission_level       = "CAN_RUN"
  }
}

resource "databricks_notebook" "pipeline" {
  for_each = local.notebook_sources
  source   = "${path.module}/../pipelines/databricks/${each.value}"
  path     = "${databricks_directory.etl_notebooks.path}/${each.key}"

  depends_on = [
    databricks_permissions.etl_notebooks
  ]
}

# Principal técnico que representa el rol Analyst de consumo.
# Se crea únicamente cuando se habilita el SQL Warehouse.
#
# El Analyst:
# - puede acceder al workspace y a Databricks SQL;
# - recibe USE_CATALOG sobre el catálogo LogiTrack;
# - recibe USE_SCHEMA + SELECT únicamente sobre Gold;
# - recibe CAN_USE sobre el SQL Warehouse;
# - no recibe permisos sobre Bronze;
# - no recibe permisos sobre Silver;
# - no recibe permisos sobre el cluster ETL.
resource "databricks_service_principal" "analyst" {
  count                 = var.enable_sql_warehouse ? 1 : 0
  display_name          = "analyst-${local.prefix}"
  active                = true
  workspace_access      = false
  databricks_sql_access = true
  allow_cluster_create  = false
}

# Unity Catalog es condicional porque un laboratorio/suscripción puede requerir
# primero que un metastore esté asignado al workspace.
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
  for_each        = var.enable_unity_catalog ? toset(["bronze", "silver", "gold"]) : toset([])
  name            = "ext_${local.catalog_name}_${each.value}"
  url             = "abfss://${each.value}@${azurerm_storage_account.lake.name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.lake[0].name
  comment         = "Capa ${each.value} de LogiTrack"
  depends_on      = [azurerm_storage_data_lake_gen2_filesystem.layers]
}

resource "databricks_catalog" "logitrack" {
  count   = var.enable_unity_catalog ? 1 : 0
  name    = local.catalog_name
  comment = "Catalogo LogiTrack ${var.environment}"

  # El metastore asignado al workspace no tiene una ubicación administrada
  # propia. El catálogo usa un subpath exclusivo dentro de Gold.
  # Los schemas mantienen ubicaciones separadas por capa.
  storage_root = "abfss://gold@${azurerm_storage_account.lake.name}.dfs.core.windows.net/_unity_catalog/"

  depends_on = [databricks_external_location.layers]
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
#
# Data Engineer técnico / ADF:
# - lectura y escritura sobre Bronze, Silver y Gold;
# - ejecuta el pipeline sobre el cluster ETL.
#
# Analyst:
# - acceso de consulta únicamente a Gold;
# - consumo mediante SQL Warehouse;
# - sin acceso a Bronze, Silver ni al cluster ETL.
#
# Admin:
# - usuario que ejecuta Terraform;
# - control completo sobre los objetos gobernados.
resource "databricks_grants" "catalog" {
  count   = var.enable_unity_catalog ? 1 : 0
  catalog = databricks_catalog.logitrack[0].name

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["USE_CATALOG"]
  }

  dynamic "grant" {
    for_each = var.enable_sql_warehouse ? [1] : []

    content {
      principal  = databricks_service_principal.analyst[0].application_id
      privileges = ["USE_CATALOG"]
    }
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }
}

# Bronze es una capa técnica de ingeniería.
# Analyst no recibe ningún grant sobre este schema.
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

# Silver es una capa técnica de transformación y calidad.
# Analyst no recibe ningún grant sobre este schema.
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

# Gold es la única capa expuesta al rol Analyst.
resource "databricks_grants" "gold" {
  count  = var.enable_unity_catalog ? 1 : 0
  schema = "${databricks_catalog.logitrack[0].name}.gold"

  grant {
    principal  = databricks_service_principal.adf_mi.application_id
    privileges = ["USE_SCHEMA", "SELECT", "MODIFY", "CREATE_TABLE"]
  }

  dynamic "grant" {
    for_each = var.enable_sql_warehouse ? [1] : []

    content {
      principal  = databricks_service_principal.analyst[0].application_id
      privileges = ["USE_SCHEMA", "SELECT"]
    }
  }

  grant {
    principal  = data.databricks_current_user.me.user_name
    privileges = ["ALL_PRIVILEGES"]
  }

  depends_on = [databricks_schema.layers]
}

# Motor de consulta destinado al consumo analítico de Gold.
# Se mantiene pequeño y con auto-stop para limitar el costo del ambiente DEV.
resource "databricks_sql_endpoint" "gold" {
  count                     = var.enable_sql_warehouse ? 1 : 0
  name                      = "sql-${local.prefix}"
  cluster_size              = "X-Small"
  max_num_clusters          = 1
  auto_stop_mins            = 10
  enable_serverless_compute = true
  warehouse_type            = "PRO"
}

# Segmentación de compute:
# - ADF / Data Engineer usa el cluster ETL.
# - Analyst usa exclusivamente el SQL Warehouse.
resource "databricks_permissions" "sql_warehouse" {
  count           = var.enable_sql_warehouse ? 1 : 0
  sql_endpoint_id = databricks_sql_endpoint.gold[0].id

  access_control {
    service_principal_name = databricks_service_principal.analyst[0].application_id
    permission_level       = "CAN_USE"
  }
}

# El motor de Databricks necesita acceso a los paths externos para registrar
# y escribir las tablas Delta.
#
# Analyst no recibe permisos directos sobre las External Locations porque
# consume las tablas gobernadas de Gold mediante Unity Catalog y SQL Warehouse.
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
