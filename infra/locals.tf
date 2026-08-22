locals {
  prefix = "${var.project}-${var.environment}"
  tags = merge({
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "data-engineering-technical-test"
  }, var.tags)

  source_tables = [
    "ope_conductores",
    "cli_remitentes",
    "geo_zonas",
    "tms_envios",
    "gps_rutas",
    "cal_destinatarios",
    "dir_novedades"
  ]

  catalog_name = "logitrack_${var.environment}"
}
