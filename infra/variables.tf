variable "project" {
  description = "Nombre corto del proyecto."
  type        = string
  default     = "logitrack"
}

variable "environment" {
  description = "Ambiente de despliegue: dev o prod."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment debe ser dev o prod."
  }
}

variable "location" {
  description = "Región Azure."
  type        = string
  default     = "eastus"
}

variable "postgres_sku" {
  description = "SKU de Azure Database for PostgreSQL Flexible Server."
  type        = string
}

variable "postgres_storage_mb" {
  description = "Almacenamiento de PostgreSQL en MB."
  type        = number
  default     = 32768
}

variable "postgres_admin_login" {
  description = "Usuario administrador de PostgreSQL. No es una contraseña."
  type        = string
  default     = "logitrack_admin"
}

variable "postgres_database" {
  description = "Base de datos fuente."
  type        = string
  default     = "logitrack"
}

variable "developer_public_ip" {
  description = "IP pública del equipo del candidato para carga/consulta. Vacío evita crear la regla."
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Correo para Action Group."
  type        = string
}

variable "enable_notifications" {
  description = "Habilita el webhook de resumen diario y alerta de volumen una vez creado el secreto notification-webhook-url en Key Vault."
  type        = bool
  default     = false
}

variable "enable_daily_trigger" {
  description = "Activa el trigger diario de ADF. En dev puede mantenerse apagado para controlar costos; en prod queda activo."
  type        = bool
  default     = false
}

variable "databricks_sku" {
  description = "Premium permite capacidades de gobierno requeridas."
  type        = string
  default     = "premium"
}

variable "databricks_min_workers" {
  description = "Workers mínimos del cluster de ejecución."
  type        = number
  default     = 1
}

variable "databricks_max_workers" {
  description = "Workers máximos del cluster de ejecución."
  type        = number
  default     = 2
}


variable "analyst_user_name" {
  description = "Usuario real de Azure Databricks para demostrar el rol Analista. Vacío omite su alta hasta la evidencia final."
  type        = string
  default     = ""
}

variable "enable_unity_catalog" {
  description = "Crea objetos Unity Catalog si el workspace tiene metastore disponible."
  type        = bool
  default     = true
}

variable "enable_sql_warehouse" {
  description = "Crea SQL Warehouse para validar consumo de Gold."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Etiquetas adicionales."
  type        = map(string)
  default     = {}
}

variable "postgres_location" {
  description = "Region especifica para PostgreSQL. Vacio usa la region general del ambiente."
  type        = string
  default     = ""
}

variable "databricks_single_node" {
  description = "Usa Databricks con un unico nodo para ambientes con cuota limitada."
  type        = bool
  default     = false
}
