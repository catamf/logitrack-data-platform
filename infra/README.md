# Infraestructura Terraform

## Qué crea

- Resource Group
- ADLS Gen2 + `bronze`, `silver`, `gold`
- Azure Database for PostgreSQL Flexible Server
- Azure Data Factory
- Azure Databricks
- Azure Key Vault
- Log Analytics Workspace
- Action Group y alertas de ADF
- Access Connector para Unity Catalog
- Unity Catalog y SQL Warehouse de forma configurable; el Warehouse consulta Gold, sin crear una capa física de consumo


## Antes de Terraform: cerrar la prueba local

Antes del primer `terraform apply`, valida `profile dev` contra PostgreSQL local con `compose.yaml`. Terraform **no administra** ese contenedor: Docker se usa solo para desarrollo. Cuando la fuente local esté estable, Azure Database for PostgreSQL se crea con Terraform y se carga con el mismo generador/esquema/loader.

## State remoto

El módulo `infra/bootstrap/` crea el Storage Account del backend. Para evitar dejar incluso el state del bootstrap en el equipo:

1. `terraform -chdir=infra/bootstrap init -backend=false`
2. `terraform -chdir=infra/bootstrap apply`
3. Copia `infra/bootstrap/backend.hcl.example` a `infra/bootstrap/backend.hcl` y reemplaza el nombre del Storage Account con el output.
4. Ejecuta `terraform -chdir=infra/bootstrap init -migrate-state -backend-config=backend.hcl`.
5. Crea `infra/backend/backend-dev.hcl` y `backend-prod.hcl` a partir de los ejemplos, usando el mismo Storage Account pero keys distintas.

Nunca confirmes un `terraform.tfstate` ni los archivos `backend*.hcl` reales en Git. El Storage Account del backend debe conservarse mientras existan los demás states.

## DEV vs PROD

El código `.tf` es común. Cambian `environments/dev.tfvars` y `prod.tfvars`. Cada ambiente usa una key de backend diferente.

## Antes del primer apply

Edita al menos:

- `alert_email` con tu correo real;
- `developer_public_ip` si vas a cargar PostgreSQL desde tu computador;
- El service principal técnico de Analyst se crea automáticamente al habilitar `enable_sql_warehouse`.
- `enable_notifications`: en la configuracion DEV de entrega se mantiene `true` porque el webhook de evaluacion ya fue guardado de forma segura en Key Vault; la URL no se almacena en Terraform ni en Git.
- `enable_daily_trigger`: en la configuracion DEV de entrega se mantiene `true` para demostrar la ejecucion automatica diaria requerida a las 02:00 hora de Bogota.
- `enable_sql_warehouse`: en la configuracion DEV de entrega se mantiene `true` para demostrar el consumo gobernado de Gold mediante SQL Warehouse Serverless X-Small.

## Nota de costos

`dev.tfvars` de entrega mantiene `enable_sql_warehouse=true`, `enable_daily_trigger=true` y `enable_notifications=true`. El cluster ETL usa un solo worker en DEV y tiene auto-termination. El entorno DEV puede destruirse con Terraform despues de la evaluacion para evitar costos innecesarios.

La segmentación de compute es simple: Data Engineer técnico/ADF usa el cluster ETL; Analyst usa SQL Warehouse; Admin puede gestionar ambos. No se crea un cluster por persona.

Unity Catalog requiere que el workspace tenga un metastore habilitado. Si tu suscripción/laboratorio no lo tiene disponible al primer despliegue, usa temporalmente `enable_unity_catalog=false`, termina la ruta crítica y vuelve a habilitarlo para la evidencia de gobierno.

## Secreto del webhook

Terraform no recibe la URL del webhook para evitar que aparezca en el state. Tras crear Key Vault, ejecuta `poetry run python scripts/configurar_webhook.py`, que usa `az login`, solicita la URL de forma oculta y la guarda directamente como `notification-webhook-url`.
