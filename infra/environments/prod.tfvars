environment       = "prod"
location          = "eastus"
# Ajusta el SKU después de validar disponibilidad/costo en tu suscripción.
postgres_sku      = "B_Standard_B2s"
postgres_storage_mb = 32768
alert_email       = "CAMBIAR_POR_TU_CORREO"
developer_public_ip = ""
databricks_min_workers = 1
databricks_max_workers = 2
analyst_user_name = "" # Completar con un usuario real para la evidencia de permisos.

enable_unity_catalog  = true
enable_sql_warehouse  = true
enable_daily_trigger   = true
enable_notifications  = false # Cambiar a true despues de guardar el webhook en Key Vault.
