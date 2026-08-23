# Fase D — Gobernanza, segregación de accesos y consumo analítico

**Proyecto:** LogiTrack Data Platform
**Entorno validado:** DEV
**Fecha de validación:** 2026-08-23
**Estado:** validación técnica y evidencias completadas.

---

## 1. Objetivo de la fase

El objetivo de la Fase D fue implementar y validar la capa de gobernanza y consumo analítico de la plataforma LogiTrack.

La fase debía demostrar una separación efectiva entre:

- las operaciones de ingeniería de datos;
- el procesamiento ETL;
- el acceso a Bronze y Silver;
- el consumo analítico de Gold;
- la administración de la plataforma.

El principio aplicado fue el de mínimo privilegio.

El rol Analyst debía poder consultar los datos publicados en Gold mediante Databricks SQL Warehouse, pero no debía recibir acceso a:

- Bronze;
- Silver;
- las External Locations de ingeniería;
- el cluster ETL;
- los notebooks utilizados por el pipeline;
- capacidad para crear clusters.

La Fase D también debía demostrar que esta segregación de permisos no interrumpía la ejecución del pipeline end-to-end administrado por Azure Data Factory.

---

## 2. Arquitectura validada

La arquitectura de consumo quedó organizada de la siguiente manera:

```text
Azure Database for PostgreSQL
            |
            v
Azure Data Factory
            |
            v
        Bronze
            |
            v
Databricks ETL notebooks
            |
            v
        Silver
            |
            v
         Gold
            |
            v
Databricks SQL Warehouse
            |
            v
 Analyst / BI / Dashboard
```

La separación de responsabilidades quedó definida de la siguiente forma:

| Rol / componente | Responsabilidad |
|---|---|
| Azure Data Factory | Orquestar la ingestión y ejecutar los notebooks ETL |
| Data Engineer / ETL | Procesar Bronze → Silver → Gold |
| Analyst | Consultar exclusivamente Gold mediante SQL Warehouse |
| Admin | Administrar workspace, permisos y recursos |
| Unity Catalog | Gobernar catálogos, schemas, credenciales y External Locations |

El Analyst no necesita acceso a los notebooks de transformación para realizar análisis.

Sus cruces, agregaciones y consultas se realizan mediante SQL sobre las tablas publicadas en Gold.

---

## 3. Unity Catalog

Se utilizó Unity Catalog como mecanismo de gobierno de las capas de datos.

El catálogo utilizado en DEV es:

```text
logitrack_dev
```

Dentro de este catálogo se encuentran los schemas:

```text
bronze
silver
gold
```

También se configuraron External Locations independientes para las capas del Data Lake:

```text
ext_logitrack_dev_bronze
ext_logitrack_dev_silver
ext_logitrack_dev_gold
```

Las ubicaciones utilizan la Storage Credential:

```text
cred_logitrack_dev
```

La autenticación Databricks → ADLS se realiza mediante Unity Catalog y la Managed Identity asociada al Azure Databricks Access Connector.

No se implementó una segunda ruta de autenticación OAuth hacia ADLS.

---

## 4. SQL Warehouse

Para el consumo analítico se habilitó un Databricks SQL Warehouse:

```text
sql-logitrack-dev
```

Configuración validada:

```text
Tipo: Serverless
Warehouse type: PRO
Tamaño: X-Small
Máximo de clusters: 1
Auto-stop: 10 minutos
```

El Warehouse se utiliza exclusivamente como capa de consulta para Gold.

### 4.1 Incidente durante el despliegue

Inicialmente se intentó crear un SQL Warehouse Classic X-Small.

Azure rechazó el aprovisionamiento debido a la cuota disponible de cómputo de la suscripción.

El error indicó que:

```text
Total Regional Cores current limit: 4
Additional required: 8
Minimum new limit: 8
```

El recurso Classic quedó tainted en Terraform.

Para evitar incrementar la cuota únicamente para la prueba técnica, se cambió el diseño a Databricks Serverless SQL Warehouse.

Terraform reemplazó el Warehouse fallido por el Warehouse Serverless y el nuevo recurso inició correctamente.

Esta decisión también evitó depender de capacidad VM clásica de la suscripción para el consumo SQL.

---

## 5. Identidad Analyst

Debido a que el entorno de la prueba dispone de una única cuenta humana, y esa cuenta tiene permisos administrativos, no se utilizó el usuario administrador para validar el rol Analyst.

En su lugar se creó un Databricks-managed service principal:

```text
analyst-logitrack-dev
```

La configuración Terraform incluye:

```hcl
workspace_access      = false
databricks_sql_access = true
allow_cluster_create  = false
```

Por tanto, el principal:

- tiene acceso a Databricks SQL;
- Terraform configura `workspace_access = false`;
- la comprobación SCIM de entitlements directos mostró únicamente `databricks-sql-access`;
- el acceso detectado inicialmente sobre `/Shared` provenía de la ACL heredada del grupo de sistema `users`, no de un grant directo configurado para Analyst;
- no puede crear clusters;
- no recibe permisos sobre el cluster ETL;
- no recibe grants sobre Bronze;
- no recibe grants sobre Silver.

Esta identidad técnica se utilizó para realizar las pruebas de autorización reales de la fase.

En un entorno empresarial, el mismo modelo de permisos podría aplicarse a usuarios humanos o grupos de analistas.

---

## 6. Permisos de Analyst

El rol Analyst recibió únicamente los permisos necesarios para consumo Gold.

### 6.1 Catálogo

Sobre:

```text
logitrack_dev
```

se otorgó:

```text
USE_CATALOG
```

### 6.2 Gold

Sobre:

```text
logitrack_dev.gold
```

se otorgó:

```text
USE_SCHEMA
SELECT
```

### 6.3 SQL Warehouse

Sobre:

```text
sql-logitrack-dev
```

se otorgó:

```text
CAN_USE
```

### 6.4 Permisos no otorgados

Analyst no recibió:

```text
Bronze:
  ningún grant

Silver:
  ningún grant

External Locations:
  ningún acceso directo

Cluster ETL:
  ningún permiso

Notebooks ETL:
  ningún permiso

Cluster creation:
  no permitido
```

---

## 7. Autenticación real como Analyst

Para evitar validar permisos utilizando accidentalmente la cuenta administrativa, se realizó una autenticación OAuth Machine-to-Machine utilizando el service principal Analyst.

Durante la primera prueba se utilizó accidentalmente el Secret ID en lugar del valor real del secreto, lo que produjo:

```text
invalid_client
```

Posteriormente se generó/utilizó correctamente el secreto OAuth y se realizó la autenticación mediante el flujo M2M.

La autenticación devolvió:

```text
OAuth OK
Tipo de token: Bearer
Expira en: 3600 segundos
```

El token se mantuvo únicamente como variable temporal de PowerShell.

No se guardó ningún token ni OAuth secret dentro del repositorio.

La identidad efectiva también se comprobó mediante SQL:

```sql
SELECT session_user() AS identidad;
```

La consulta confirmó que la sesión correspondía al service principal Analyst y no al usuario administrador.

---

## 8. Validación positiva de Gold

Como Analyst se ejecutó:

```sql
SHOW TABLES IN logitrack_dev.gold;
```

La consulta finalizó correctamente y permitió descubrir las tablas publicadas en Gold.

Entre las tablas disponibles se observaron:

```text
agg_desempeno_zona
agg_sla_remitente
agg_tipo_paquete
dim_conductores
dim_remitentes
dim_zonas
fact_alertas_zona
fact_desempeno_conductor
fact_envios
fact_rutas
fact_trazabilidad_envio
kpi_logistica_diaria
resultados_calidad
resumen_ejecuciones
```

También se ejecutó una consulta real:

```sql
SELECT *
FROM logitrack_dev.gold.kpi_logistica_diaria
LIMIT 5;
```

La consulta finalizó en estado:

```text
SUCCEEDED
```

y devolvió cinco registros reales.

Esto demuestra que Analyst puede utilizar Gold mediante SQL Warehouse.

A partir de Gold el analista puede realizar:

- JOIN entre hechos y dimensiones;
- filtros;
- agregaciones;
- GROUP BY;
- CTE;
- funciones de ventana;
- análisis por zona, remitente, conductor o tipo de paquete;
- consultas para dashboards y herramientas BI.

---

## 9. Validación negativa de Silver

Como Analyst se intentó consultar:

```sql
SELECT *
FROM logitrack_dev.silver.reporte_calidad
LIMIT 1;
```

Databricks rechazó la consulta con:

```text
[INSUFFICIENT_PERMISSIONS]
User does not have USE SCHEMA on Schema 'logitrack_dev.silver'.
SQLSTATE: 42501
```

Resultado esperado:

```text
Analyst → Silver: DENEGADO
```

La prueba confirma que disponer de acceso a Gold no concede acceso implícito a Silver.

---

## 10. Validación negativa de Bronze

Inicialmente se intentó consultar una tabla Bronze por nombre.

Esta prueba no se consideró concluyente porque Bronze está almacenado principalmente como archivos Parquet en ADLS y el objeto consultado no tenía necesariamente que estar registrado como tabla de Unity Catalog.

También se realizaron pruebas exploratorias mediante `SHOW TABLES` y comandos de schema, pero no se utilizaron como evidencia principal.

La prueba definitiva se realizó intentando acceder directamente a la External Location de Bronze:

```sql
LIST 'abfss://bronze@stlogidevmn79c.dfs.core.windows.net/' LIMIT 1;
```

Databricks rechazó la operación con:

```text
PERMISSION_DENIED:
User does not have READ FILES on External Location
'ext_logitrack_dev_bronze'.

SQLSTATE: 42501
```

Resultado esperado:

```text
Analyst → Bronze: DENEGADO
```

Esto demuestra que Analyst tampoco puede eludir el modelo de schemas accediendo directamente a los archivos de Bronze.

---

## 11. Segregación del cluster ETL

El cluster ETL utilizado por Azure Data Factory es:

```text
etl-logitrack-dev
```

La ACL efectiva del cluster fue consultada utilizando la identidad administrativa.

Se observó:

```text
ADF service principal → CAN_ATTACH_TO
Usuario administrador → CAN_MANAGE
Grupo admins          → CAN_MANAGE
```

El service principal Analyst no aparece en la ACL efectiva.

Analyst tampoco recibió:

```text
CAN_ATTACH_TO
CAN_RESTART
CAN_MANAGE
```

Por tanto:

```text
ADF / Data Engineer → cluster ETL
Analyst             → SQL Warehouse
```

Esta separación evita utilizar el mismo compute para procesamiento y consumo analítico.

---

## 12. Hallazgo: exposición de notebooks bajo /Shared

Durante la validación de permisos se descubrió un problema adicional.

Los notebooks ETL estaban desplegados inicialmente bajo:

```text
/Shared/logitrack/dev
```

Al autenticarse como Analyst fue posible:

1. listar los seis notebooks;
2. exportar el contenido del notebook `00_common`.

Por tanto, aunque Analyst no tenía acceso al cluster ETL ni a Bronze/Silver, todavía podía leer el código de ingeniería.

Esta situación no cumplía con el aislamiento buscado para el rol Analyst.

---

## 13. Investigación del acceso a /Shared

Inicialmente se modificó el service principal Analyst para utilizar:

```hcl
workspace_access = false
```

La modificación se aplicó correctamente.

Sin embargo, después de obtener un nuevo OAuth token, Analyst todavía podía leer los notebooks almacenados en `/Shared`.

Se verificaron entonces los entitlements del service principal mediante SCIM.

El resultado mostró únicamente:

```text
databricks-sql-access
```

y no mostró grupos adicionales asignados directamente al principal.

Por tanto, la exposición no se debía a un entitlement directo de Workspace Access.

Posteriormente se inspeccionó la ACL de `/Shared`.

El resultado fue:

```text
Ruta: /Shared

GROUP: users  → CAN_MANAGE | heredado=False
GROUP: admins → CAN_MANAGE | heredado=True
```

Para:

```text
/Shared/logitrack/dev
```

se encontró:

```text
GROUP: users → CAN_MANAGE | heredado=True
```

heredado desde `/Shared`.

Esta fue identificada como la causa real del acceso de Analyst a los notebooks.

---

## 14. Corrección del aislamiento de notebooks

No se modificó globalmente la ACL de `/Shared`, ya que ese cambio habría afectado a otros usuarios u objetos del workspace.

En su lugar se creó un directorio específico para ingeniería:

```text
/Engineering/logitrack/dev
```

Terraform gestiona actualmente este directorio mediante:

```hcl
resource "databricks_directory" "etl_notebooks"
```

Los seis notebooks fueron reubicados a:

```text
/Engineering/logitrack/dev/00_common
/Engineering/logitrack/dev/00_auditar_bronze
/Engineering/logitrack/dev/01_procesar_silver
/Engineering/logitrack/dev/02_procesar_gold
/Engineering/logitrack/dev/03_calidad_gold
/Engineering/logitrack/dev/04_resumen_ejecucion
```

Se creó una ACL específica para el directorio:

```text
ADF service principal → CAN_RUN
admins                → CAN_MANAGE heredado
Analyst               → sin permiso
```

También se actualizaron las cinco actividades Databricks de:

```text
orchestration/adf/pipeline_principal.json
```

para sustituir:

```text
/Shared/logitrack/@{pipeline().parameters.environment}/...
```

por:

```text
/Engineering/logitrack/@{pipeline().parameters.environment}/...
```

---

## 15. Aplicación del hardening

El Terraform plan del cambio mostró:

```text
Plan: 8 to add, 1 to change, 6 to destroy.
```

Los seis recursos destruidos correspondían exclusivamente a las copias antiguas de los notebooks almacenadas bajo `/Shared`.

Terraform:

1. eliminó los seis notebooks de `/Shared`;
2. creó `/Engineering/logitrack/dev`;
3. creó la ACL de la carpeta;
4. recreó los seis notebooks en `/Engineering`;
5. actualizó el pipeline de Azure Data Factory.

El resultado fue:

```text
Apply complete!
Resources: 8 added, 1 changed, 6 destroyed.
```

No se modificaron como parte de esta operación:

- el SQL Warehouse;
- los grants de Gold;
- los schemas Bronze/Silver/Gold;
- las External Locations;
- el cluster ETL;
- PostgreSQL;
- ADLS.

---

## 16. Validación del aislamiento después del hardening

Después de la migración se obtuvo un nuevo token Analyst y se intentó exportar:

```text
/Engineering/logitrack/dev/00_common
```

Databricks devolvió:

```text
RESOURCE_DOES_NOT_EXIST
Path (/Engineering/logitrack/dev/00_common) doesn't exist.
```

Esta respuesta por sí sola no se tomó como prueba definitiva, ya que podía ser consecuencia de ocultamiento del recurso por autorización.

Se utilizó entonces la identidad administrativa para consultar exactamente la misma ruta.

El resultado confirmó:

```text
Path: /Engineering/logitrack/dev/00_common
Tipo: NOTEBOOK
```

Por tanto, el notebook existe realmente.

La ACL del directorio mostró:

```text
ADF service principal → CAN_RUN | heredado=False
admins                → CAN_MANAGE | heredado=True
```

No aparece:

```text
GROUP: users
```

y tampoco aparece:

```text
analyst-logitrack-dev
```

La combinación de ambas pruebas demuestra que:

```text
Admin   → puede resolver y administrar el notebook
ADF     → puede ejecutar los notebooks
Analyst → no puede leer/exportar el notebook
```

---

## 17. Validación funcional de ADF después del hardening

Después de mover los notebooks se ejecutó nuevamente el pipeline completo:

```text
pl_logitrack_end_to_end
```

Run ID:

```text
d636a27f-9f2f-11f1-8ad2-f4c52f12ecd6
```

El pipeline terminó en:

```text
Succeeded
```

Las cinco actividades Databricks también terminaron correctamente:

| Actividad | Tipo | Estado |
|---|---|---|
| Auditar_Bronze | DatabricksNotebook | Succeeded |
| Procesar_Silver | DatabricksNotebook | Succeeded |
| Procesar_Gold | DatabricksNotebook | Succeeded |
| Calidad_Gold | DatabricksNotebook | Succeeded |
| Resumen_Ejecucion | DatabricksNotebook | Succeeded |

También finalizaron correctamente las actividades de ingestión, watermarks, logs de ingesta y el pipeline de resumen.

Esto demuestra que retirar los notebooks de `/Shared` no rompió la integración ADF → Databricks.

---

## 18. Idempotencia de Terraform

Una vez completado el despliegue y las pruebas funcionales se ejecutó nuevamente:

```powershell
terraform -chdir=infra plan `
  -var-file="environments/dev.tfvars" `
  -var-file="environments/dev.local.tfvars" `
  -no-color
```

Terraform refrescó, entre otros:

```text
/Engineering/logitrack/dev

/Engineering/logitrack/dev/00_common
/Engineering/logitrack/dev/00_auditar_bronze
/Engineering/logitrack/dev/01_procesar_silver
/Engineering/logitrack/dev/02_procesar_gold
/Engineering/logitrack/dev/03_calidad_gold
/Engineering/logitrack/dev/04_resumen_ejecucion
```

El resultado final fue:

```text
No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your
configuration and found no differences, so no changes are needed.
```

Esto confirma que el estado real de DEV y la configuración declarativa de Terraform quedaron sincronizados.

---

## 19. Matriz final de autorización validada

| Acción | ADF service principal | Analyst | Admin |
|---|---:|---:|---:|
| Ejecutar notebooks ETL | Sí (`CAN_RUN`) | No | Sí |
| Attach al cluster ETL | Sí (`CAN_ATTACH_TO`) | No | Sí |
| Consultar Gold por SQL Warehouse | No requerido | Sí (`SELECT`) | Sí |
| Consultar Silver | No es el rol de consumo | No | Sí |
| Acceder directamente a Bronze | Según procesamiento ETL | No | Sí |
| Utilizar SQL Warehouse | No requerido | Sí (`CAN_USE`) | Sí |
| Crear clusters | No validado como capacidad del SP | No | Sí |
| Administrar permisos | No | No | Sí |

---

## 20. Criterios de aceptación de Fase D

| Criterio | Resultado |
|---|---|
| Unity Catalog configurado | PASS |
| Bronze/Silver/Gold gobernados | PASS |
| External Locations configuradas | PASS |
| SQL Warehouse disponible | PASS |
| SQL Warehouse Serverless validado | PASS |
| Analyst tiene CAN_USE en SQL Warehouse | PASS |
| Analyst puede consultar Gold | PASS |
| Analyst no puede consultar Silver | PASS |
| Analyst no puede acceder directamente a Bronze | PASS |
| Analyst no tiene acceso al cluster ETL | PASS |
| Analyst no puede leer notebooks ETL | PASS |
| ADF conserva acceso a notebooks ETL | PASS |
| ADF conserva CAN_ATTACH_TO al cluster ETL | PASS |
| Pipeline funciona después del hardening | PASS |
| Terraform finaliza en No changes | PASS |

---

## 21. Incidentes y correcciones

| Incidente | Diagnóstico | Corrección | Resultado |
|---|---|---|---|
| SQL Warehouse Classic no inicia | Cuota regional insuficiente | Cambio a Serverless SQL Warehouse | Resuelto |
| OAuth devuelve `invalid_client` | Se utilizó Secret ID en lugar del secret value | Generación/uso correcto del OAuth secret | Resuelto |
| PowerShell Basic Auth devuelve 401 | Forma de autenticación no funcionó como se esperaba | Uso de `curl.exe --user` para OAuth M2M | Resuelto |
| Primera prueba Bronze no concluyente | El objeto consultado no era necesariamente tabla UC | Prueba directa contra External Location | Denegación demostrada |
| Analyst puede leer notebooks | Notebooks estaban bajo `/Shared` | Investigación de ACL | Causa identificada |
| `workspace_access=false` no resuelve notebooks | Permiso provenía de ACL de `/Shared`, no del entitlement directo | Reubicación fuera de `/Shared` | Resuelto |
| `/Shared` entrega `users → CAN_MANAGE` | Permiso heredado por `/Shared/logitrack/dev` | Crear `/Engineering/logitrack/dev` con ACL específica | Resuelto |
| Riesgo de romper ADF al mover notebooks | ADF contenía cinco rutas hardcodeadas | Actualización conjunta Terraform + pipeline JSON | Pipeline E2E Succeeded |

---

## 22. Decisiones de diseño

### 22.1 Gold como contrato analítico

El rol Analyst consume exclusivamente Gold.

Gold funciona como contrato de datos para consumo analítico.

Si un dato requerido por negocio no está disponible en Gold, la solución esperada no es ampliar el acceso del Analyst a Silver.

El flujo esperado es:

```text
Necesidad analítica
       |
       v
Data Engineer incorpora/modela el dato
       |
       v
Gold
       |
       v
Analyst consume mediante SQL
```

Esto mantiene el desacoplamiento entre transformación técnica y consumo.

### 22.2 SQL Warehouse separado del ETL compute

El procesamiento y el consumo utilizan recursos diferentes:

```text
ADF / Data Engineer
        |
        v
   ETL cluster

Analyst
        |
        v
 SQL Warehouse
```

De esta forma el rol analítico no necesita permisos sobre el cluster de procesamiento.

### 22.3 No modificar globalmente /Shared

Aunque retirar `users → CAN_MANAGE` de `/Shared` habría podido eliminar la exposición, se descartó porque es una configuración global del workspace.

La solución seleccionada fue aislar los notebooks propios de LogiTrack en un directorio restringido.

---

## 23. Seguridad

Durante las pruebas:

- los tokens OAuth se mantuvieron únicamente en variables temporales de PowerShell;
- no se almacenaron tokens en Terraform;
- no se almacenaron OAuth secrets en Git;
- los archivos locales destinados a contener secretos están configurados para ser ignorados por Git; la comprobación final del contenido a incluir en el commit se realizará como parte del cierre de la fase;
- no se implementó una segunda credencial de acceso a ADLS;
- se mantuvo el principio de mínimo privilegio.

El OAuth secret temporal utilizado para las pruebas debe revocarse una vez finalizadas todas las validaciones que requieran autenticación como Analyst.

---

## 24. Evidencias

Las evidencias técnicas y visuales de la fase se almacenan bajo:

```text
docs/evidencias/fase_d/
```

La secuencia de evidencias validada es:

| ID | Archivo | Validación |
|---|---|---|
| D.1 | `01_unity_catalog.png` | Catálogo `logitrack_dev` y schemas gobernados |
| D.2 | `02_external_locations.png` | External Locations Bronze/Silver/Gold |
| D.3 | `03_sql_warehouse.png` | SQL Warehouse Serverless |
| D.4 | `04_sql_warehouse_permissions.png` | Analyst dispone de `CAN_USE` |
| D.5 | `05_analyst_service_principal.png` | Identidad técnica Analyst |
| D.6 | `06_analyst_gold_success.png` | Gold consultado correctamente como Analyst |
| D.7 | `07_analyst_silver_denied.png` | Silver denegado con `INSUFFICIENT_PERMISSIONS` |
| D.8 | `08_analyst_bronze_denied.png` | Bronze denegado por ausencia de `READ FILES` |
| D.9 | `09_etl_cluster_permissions.png` | ADF `CAN_ATTACH_TO`; Analyst ausente de la ACL |
| D.10 | `10_shared_acl_root_cause.png` | Causa raíz: `users → CAN_MANAGE` en `/Shared` |
| D.11 | `11_engineering_acl.png` | ACL restringida de `/Engineering/logitrack/dev` |
| D.12 | `12_analyst_notebook_denied.png` | Notebook existente para Admin e inaccesible para Analyst |
| D.13 | `13_adf_pipeline_post_hardening.png` | Pipeline E2E posterior al hardening en `Succeeded` |
| D.13-TXT | `13_adf_pipeline_post_hardening.txt` | Evidencia textual reproducible del mismo Run ID |
| D.14 | `14_terraform_no_changes.png` | Terraform final en `No changes` |

Las capturas no contienen OAuth secrets, Bearer tokens ni contraseñas.

---

## 25. Trabajo pendiente antes del commit de la fase

La implementación, la validación técnica y la captura de evidencias principales de la Fase D están completadas.

Antes de realizar el commit de cierre quedan únicamente tareas de entrega:

1. incorporar/revisar las evidencias D.1–D.14 en el documento Word general del proyecto;
2. revocar el OAuth secret temporal utilizado para las pruebas cuando ya no sea necesario;
3. revisar el `git diff` completo de la Fase D;
4. ejecutar las validaciones finales del repositorio;
5. comprobar que no existan secretos ni archivos generados incluidos accidentalmente;
6. realizar el commit de cierre de Fase D.

La Fase E se tratará de forma independiente y no se considera ejecutada dentro de este documento.

---

## 26. Resultado de la fase

La Fase D demuestra que la plataforma implementa una separación real entre ingeniería de datos y consumo analítico.

El resultado validado es:

```text
ADF / Data Engineer
    → ETL cluster
    → Bronze
    → Silver
    → Gold
    → notebooks ETL

Analyst
    → SQL Warehouse
    → Gold SELECT

Admin
    → administración completa
```

Las pruebas se realizaron utilizando identidades reales y no únicamente inspeccionando la configuración Terraform.

Se verificaron tanto operaciones permitidas como operaciones denegadas y finalmente se ejecutó nuevamente el pipeline completo para comprobar que el endurecimiento de permisos no afectó el procesamiento de datos.

La infraestructura terminó en un estado idempotente:

```text
No changes. Your infrastructure matches the configuration.
```
