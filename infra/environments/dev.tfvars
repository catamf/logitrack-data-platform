environment = "dev"
location    = "eastus"

postgres_sku        = "B_Standard_B1ms"
postgres_storage_mb = 32768

# El valor real se proporciona mediante dev.local.tfvars,
# que no se versiona.
alert_email = "CAMBIAR_POR_TU_CORREO"

# Se mantiene vacío hasta la carga de datos a Azure PostgreSQL.
# La IP real se proporciona mediante dev.local.tfvars.
developer_public_ip = ""

databricks_min_workers = 1
databricks_max_workers = 2

# Se completa únicamente durante la evidencia final de permisos.
analyst_user_name = ""

# La primera creación del workspace se realiza sin objetos de
# Unity Catalog. Se habilita después de comprobar/asignar metastore.
enable_unity_catalog = true

# Se habilita únicamente durante la evidencia de consumo Gold.
enable_sql_warehouse = false

# El trigger existe pero no se activa durante el desarrollo inicial.
enable_daily_trigger = false

# Las notificaciones por webhook se habilitan después de configurar
# el secreto correspondiente en Key Vault.
enable_notifications = false

postgres_location       = "centralus"
databricks_single_node  = true
