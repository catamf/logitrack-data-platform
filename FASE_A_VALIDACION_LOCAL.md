# Validación local — LogiTrack Data Platform

## 1. Objetivo

Este documento registra las validaciones ejecutadas durante la fase de desarrollo local de LogiTrack antes del despliegue en Azure.

La fase local tuvo como objetivos:

- validar el entorno Python del proyecto;
- comprobar la generación reproducible de datos sintéticos;
- verificar los formatos CSV y Parquet;
- validar las anomalías sintéticas requeridas;
- desplegar PostgreSQL 16 mediante Docker;
- crear y validar el esquema relacional fuente;
- cargar los datos sintéticos en PostgreSQL;
- comprobar los tipos de datos;
- validar la estrategia de watermark;
- comprobar el mecanismo de actualización incremental mediante `ts_actualizacion`.

Las validaciones descritas a continuación corresponden a ejecuciones realizadas realmente durante el desarrollo.

---

## 2. Entorno Python y dependencias

### 2.1 Poetry

Se ejecutó:

```bash
poetry lock
```

Poetry detectó que el Python global del equipo era:

```text
Python 3.10.2
```

y que no cumplía el requisito definido por el proyecto:

```text
>=3.11,<3.14
```

Poetry seleccionó automáticamente:

```text
Python 3.12.6
```

y creó el entorno virtual local:

```text
.venv/
```

Resultado relevante:

```text
Creating virtualenv logitrack-data-platform in
C:\Users\ktmor\Documents\GitHub\logitrack-data-platform\.venv

Updating dependencies
Resolving dependencies...

Writing lock file
```

Posteriormente se ejecutó:

```bash
poetry install
```

Resultado:

```text
Installing dependencies from lock file

Package operations: 35 installs, 0 updates, 0 removals
```

Entre las dependencias instaladas se encuentran:

- pandas;
- NumPy;
- PyArrow;
- PyYAML;
- SQLAlchemy;
- psycopg;
- python-dotenv;
- pytest;
- azure-identity;
- azure-keyvault-secrets.

El archivo `poetry.lock` quedó generado y se versionará en Git para garantizar reproducibilidad.

El entorno `.venv/` está excluido mediante `.gitignore`.

---

## 3. Pruebas automatizadas

### 3.1 Primera validación

Inicialmente se ejecutó:

```bash
poetry run pytest
```

Resultado:

```text
9 passed
```

Durante las pruebas iniciales se detectó un warning asociado a una operación `timedelta` de NumPy.

Posteriormente, durante la ejecución real del generador, se identificaron dos casos no cubiertos por los tests existentes:

1. inconsistencia del schema Parquet entre bloques;
2. riesgo de sobrescritura del CSV durante escritura por bloques.

Se corrigieron ambos comportamientos y se añadieron pruebas de regresión.

### 3.2 Validación final

Después de las correcciones se ejecutó nuevamente:

```bash
poetry run pytest
```

Resultado final:

```text
...........                                                     [100%]
11 passed in 0.62s
```

Por tanto:

```text
Tests aprobados: 11/11
```

Entre los comportamientos validados se encuentran:

- reproducibilidad mediante seed fija;
- integridad referencial de los envíos;
- generación controlada de anomalías;
- estabilidad del schema Parquet entre bloques;
- escritura de múltiples bloques CSV sin sobrescritura;
- configuración general del proyecto.

---

## 4. Validación estructural del repositorio

Se ejecutó:

```bash
poetry run python scripts/validar_repo.py
```

Resultado:

```text
Estructura, PostgreSQL local, secretos y orquestacion base: OK
```

Esta validación comprueba aspectos estructurales y de configuración del repositorio.

No sustituye las pruebas de integración ejecutadas posteriormente contra PostgreSQL.

---

## 5. Docker y PostgreSQL local

### 5.1 Docker Engine

Docker Desktop y Docker Engine fueron iniciados y verificados mediante:

```bash
docker info
```

Se confirmó disponibilidad tanto del cliente como del servidor Docker.

Configuración observada:

```text
Server Version: 28.1.1
Operating System: Docker Desktop
OSType: linux
Architecture: x86_64
```

Docker utiliza WSL2 como backend Linux.

### 5.2 Creación del servicio PostgreSQL

Se ejecutó:

```bash
docker compose --env-file .env.local up -d
```

Resultado relevante:

```text
Network logitrack-local_default          Created
Volume "logitrack-local_postgres_data"   Created
Container logitrack-local-postgres-1     Started
```

La salud del servicio se comprobó mediante:

```bash
docker compose --env-file .env.local ps
```

Resultado:

```text
NAME                         IMAGE                STATUS
logitrack-local-postgres-1   postgres:16-alpine   Up (...) (healthy)
```

Puerto publicado:

```text
0.0.0.0:5432->5432/tcp
```

Por tanto, PostgreSQL quedó disponible localmente mediante:

```text
host: localhost
port: 5432
```

---

## 6. Protección de secretos

La configuración local se encuentra en:

```text
.env.local
```

El archivo está excluido del control de versiones.

Se verificó mediante:

```bash
git check-ignore -v .env.local
```

Resultado:

```text
.gitignore:20:.env.*    .env.local
```

El repositorio contiene únicamente:

```text
.env.local.example
```

como plantilla sin credenciales reales.

También se verificó que el entorno virtual esté ignorado:

```bash
git check-ignore -v .venv/
```

Resultado:

```text
.gitignore:31:.venv/    .venv/
```

Los datasets generados tampoco se versionan.

Validación:

```bash
git check-ignore -v data-generation/output/dev/manifest.json
```

Resultado:

```text
.gitignore:36:/data-generation/output/
```

---

## 7. Generación de datos sintéticos DEV

Se ejecutó:

```bash
poetry run python data-generation/generar_datos.py --profile dev
```

La ejecución finalizó correctamente.

Manifest generado:

```json
{
  "profile": "dev",
  "seed": 42,
  "fecha_inicio": "2025-08-01",
  "fecha_fin": "2026-08-21",
  "formatos": [
    "csv",
    "parquet"
  ],
  "volumen_base": {
    "OPE_CONDUCTORES": 120,
    "CLI_REMITENTES": 60,
    "GEO_ZONAS": 80,
    "TMS_ENVIOS": 10000,
    "GPS_RUTAS": 3000,
    "CAL_DESTINATARIOS": 2500,
    "DIR_NOVEDADES": 1500
  },
  "filas_tms_envios_incluyendo_duplicados": 10005,
  "anomalias": {
    "duplicados_envios": 0.0005,
    "peso_negativo": 0.0005,
    "fecha_entrega_invalida": 0.0005
  },
  "porcentaje_nulos_objetivo": 0.05
}
```

La generación cubre el periodo:

```text
2025-08-01 → 2026-08-21
```

por lo que contiene más de doce meses de histórico.

---

## 8. Archivos generados

Se verificó el contenido de:

```text
data-generation/output/dev/
```

Se generaron los siete datasets en CSV y Parquet, además de `manifest.json`.

Los tamaños observados confirmaron la diferencia esperada entre almacenamiento CSV y Parquet.

Ejemplo:

```text
TMS_ENVIOS.csv       ~1.5 MB
TMS_ENVIOS.parquet   ~279 KB
```

Parquet utiliza almacenamiento columnar y compresión, por lo que el tamaño es significativamente menor.

---

## 9. Conteos de los datasets

Resultado de la validación de conteos CSV:

```text
CAL_DESTINATARIOS: 2,500 filas
CLI_REMITENTES: 60 filas
DIR_NOVEDADES: 1,500 filas
GEO_ZONAS: 80 filas
GPS_RUTAS: 3,000 filas
OPE_CONDUCTORES: 120 filas
TMS_ENVIOS: 10,005 filas
```

El volumen configurado para `TMS_ENVIOS` es de 10.000 filas base y se añaden deliberadamente 5 duplicados.

Resultado físico:

```text
10.005 filas
```

---

## 10. Equivalencia CSV vs. Parquet

Se compararon los conteos de ambos formatos.

Resultado:

```text
CAL_DESTINATARIOS: CSV=2,500 | Parquet=2,500
CLI_REMITENTES: CSV=60 | Parquet=60
DIR_NOVEDADES: CSV=1,500 | Parquet=1,500
GEO_ZONAS: CSV=80 | Parquet=80
GPS_RUTAS: CSV=3,000 | Parquet=3,000
OPE_CONDUCTORES: CSV=120 | Parquet=120
TMS_ENVIOS: CSV=10,005 | Parquet=10,005
```

Conclusión: los conteos CSV y Parquet coinciden para las siete fuentes.

---

## 11. Anomalías sintéticas antes de PostgreSQL

Las anomalías de `TMS_ENVIOS` fueron verificadas directamente sobre el archivo Parquet.

Resultado:

```text
Duplicados id_envio: 5
Pesos <= 0: 5
Fechas entrega < recepcion: 5
```

Estas anomalías son deliberadas y deben conservarse en la fuente y en Bronze para posteriormente ser detectadas o tratadas por Silver.

---

## 12. Incidencia 1 — Schema Parquet entre bloques

Durante la primera ejecución completa del generador se produjo:

```text
ValueError: Table schema does not match schema used to create file
```

La diferencia estaba asociada a `motivo_fallo_cod`.

En el archivo Parquet inicial la columna había sido inferida como `string`, pero el bloque de duplicados contenía únicamente valores nulos y PyArrow la infería como `null`.

Se corrigió `EscritorPorBloques` para:

1. determinar el schema durante la primera escritura;
2. almacenar dicho schema;
3. reutilizarlo para todos los bloques siguientes.

También se añadió un test específico para evitar regresiones.

---

## 13. Incidencia 2 — Escritura CSV por bloques

Durante la revisión del writer se identificó que `self.primero` no cambiaba a `False` después de escribir el primer bloque.

Esto podía provocar que ejecuciones con múltiples chunks utilizaran nuevamente `mode="w"` y sobrescribieran el contenido anterior.

Se corrigió el comportamiento para utilizar:

```text
primer bloque  -> write
resto          -> append
```

y se añadió una prueba automatizada específica.

---

## 14. Creación y carga de PostgreSQL

El loader fue validado sintácticamente mediante:

```bash
poetry run python -m py_compile data-generation/cargar_postgresql.py
```

Resultado: sin errores.

Posteriormente se intentó una primera carga mediante `pandas.to_sql()`.

Se produjo:

```text
psycopg.errors.DatatypeMismatch:
column "fec_ingreso" is of type date
but expression is of type character varying
```

La causa fue que `pandas.read_csv()` interpretaba las fechas del CSV como texto y `to_sql()` enviaba los valores a PostgreSQL como `VARCHAR`, mientras que el esquema relacional correctamente definía `fec_ingreso DATE`.

No se modificó el esquema para convertir fechas a texto.

En su lugar se reemplazó la estrategia de carga por PostgreSQL `COPY`.

De esta manera PostgreSQL aplica los tipos definidos en `00_schema.sql`.

Esta solución también es más adecuada para el volumen final previsto de millones de registros.

---

## 15. Carga final PostgreSQL

Después de implementar `COPY`, se ejecutó:

```bash
poetry run python data-generation/cargar_postgresql.py \
  --profile dev \
  --truncate \
  --env-file .env.local
```

Resultado:

```text
OPE_CONDUCTORES: 120 filas cargadas
CLI_REMITENTES: 60 filas cargadas
GEO_ZONAS: 80 filas cargadas
TMS_ENVIOS: 10,005 filas cargadas
GPS_RUTAS: 3,000 filas cargadas
CAL_DESTINATARIOS: 2,500 filas cargadas
DIR_NOVEDADES: 1,500 filas cargadas
```

Conteos finales reportados por PostgreSQL:

```text
OPE_CONDUCTORES: 120
CLI_REMITENTES: 60
GEO_ZONAS: 80
TMS_ENVIOS: 10,005
GPS_RUTAS: 3,000
CAL_DESTINATARIOS: 2,500
DIR_NOVEDADES: 1,500
```

---

## 16. Tablas PostgreSQL creadas

Se ingresó directamente a PostgreSQL y se ejecutó:

```sql
\dt
```

Resultado:

```text
cal_destinatarios
cli_remitentes
control_ingesta
dir_novedades
geo_zonas
gps_rutas
log_ingesta_adf
ope_conductores
tms_envios
```

Total:

```text
9 tablas
```

De ellas:

```text
7 = tablas fuente
2 = tablas técnicas de ingesta
```

---

## 17. Validación del schema SQL

Se inspeccionó:

```sql
\d ope_conductores
```

Se verificaron, entre otros:

```text
fec_ingreso           DATE
activo                BOOLEAN
calific_promedio_acum NUMERIC(4,2)
ts_actualizacion      TIMESTAMP WITH TIME ZONE
```

También se verificó `PRIMARY KEY: cond_id` y el trigger `trg_ts_actualizacion`.

Posteriormente se inspeccionó:

```sql
\d tms_envios
```

Tipos relevantes:

```text
peso_kg                NUMERIC(12,2)
fec_recepcion          DATE
hra_recepcion          TIME
fec_entrega_programada DATE
fec_intento1           DATE
hra_intento1           TIME
fec_intento2           DATE
hra_intento2           TIME
fec_entrega_real       DATE
vr_declarado           NUMERIC(18,2)
ts_actualizacion       TIMESTAMP WITH TIME ZONE
```

`id_envio` dispone de índice, pero deliberadamente no es una PRIMARY KEY.

Esto permite conservar duplicados de fuente para que la deduplicación se produzca posteriormente en Silver.

---

## 18. Validación de anomalías en PostgreSQL

### IDs duplicados

```sql
SELECT COUNT(*) AS ids_duplicados
FROM (
    SELECT id_envio
    FROM tms_envios
    GROUP BY id_envio
    HAVING COUNT(*) > 1
) d;
```

Resultado:

```text
5
```

### Pesos inválidos

```sql
SELECT COUNT(*) AS pesos_invalidos
FROM tms_envios
WHERE peso_kg <= 0;
```

Resultado:

```text
5
```

### Fechas inválidas

```sql
SELECT COUNT(*) AS fechas_invalidas
FROM tms_envios
WHERE fec_entrega_real < fec_recepcion;
```

Resultado:

```text
5
```

Las anomalías sobrevivieron correctamente la carga desde el generador hasta PostgreSQL.

---

## 19. Validación del watermark inicial

Se ejecutó:

```sql
SELECT
    tabla,
    watermark_utc
FROM control_ingesta
ORDER BY tabla;
```

Resultado:

```text
cal_destinatarios | 1900-01-01 00:00:00+00
cli_remitentes    | 1900-01-01 00:00:00+00
dir_novedades     | 1900-01-01 00:00:00+00
geo_zonas         | 1900-01-01 00:00:00+00
gps_rutas         | 1900-01-01 00:00:00+00
ope_conductores   | 1900-01-01 00:00:00+00
tms_envios        | 1900-01-01 00:00:00+00
```

Las siete fuentes tienen por tanto un watermark inicial equivalente a “ningún dato ingerido todavía”.

---

## 20. Validación de consulta incremental

Se ejecutó:

```sql
SELECT COUNT(*) AS filas_incrementales
FROM tms_envios
WHERE ts_actualizacion > (
    SELECT watermark_utc
    FROM control_ingesta
    WHERE LOWER(tabla) = LOWER('TMS_ENVIOS')
);
```

Resultado:

```text
10005
```

Esto confirma el comportamiento esperado para la primera ejecución:

```text
watermark = 1900-01-01
        ↓
todos los registros son posteriores
        ↓
primera carga = 10.005 registros
```

Una vez que ADF actualice el watermark, las ejecuciones siguientes deberán recuperar únicamente registros nuevos o modificados.

---

## 21. Validación del trigger `ts_actualizacion`

Se consultó inicialmente el primer conductor.

Resultado:

```text
cond_id:          CON00001
activo:           true
ts_actualizacion: 2026-08-22 18:15:47.069996+00
```

Posteriormente se ejecutó:

```sql
UPDATE ope_conductores
SET activo = activo
WHERE cond_id = (
    SELECT cond_id
    FROM ope_conductores
    ORDER BY cond_id
    LIMIT 1
)
RETURNING
    cond_id,
    activo,
    ts_actualizacion;
```

Resultado:

```text
cond_id:          CON00001
activo:           true
ts_actualizacion: 2026-08-22 18:19:29.040534+00
```

El valor funcional de `activo` se mantuvo sin cambios, pero el trigger actualizó correctamente `ts_actualizacion`.

Esto valida el mecanismo necesario para detectar modificaciones durante una ingesta incremental.

---

## 22. Estado final de la fase local

| Validación | Estado |
|---|---|
| Poetry | ✅ |
| Python aislado mediante `.venv` | ✅ |
| `poetry.lock` | ✅ |
| Dependencias instaladas | ✅ |
| Tests | ✅ 11/11 |
| Validador del repositorio | ✅ |
| Docker Engine | ✅ |
| Docker Compose | ✅ |
| PostgreSQL 16 | ✅ |
| PostgreSQL healthcheck | ✅ healthy |
| Generación reproducible con seed 42 | ✅ |
| Histórico > 12 meses | ✅ |
| CSV | ✅ |
| Parquet | ✅ |
| Conteos CSV = Parquet | ✅ |
| 7 fuentes sintéticas | ✅ |
| 5 duplicados | ✅ |
| 5 pesos inválidos | ✅ |
| 5 fechas inválidas | ✅ |
| PostgreSQL `COPY` | ✅ |
| 7 tablas fuente cargadas | ✅ |
| Tipos SQL | ✅ |
| Watermarks iniciales | ✅ |
| Consulta incremental inicial | ✅ |
| Trigger `ts_actualizacion` | ✅ |
| Protección de secretos mediante `.gitignore` | ✅ |
| Azure CLI | Pendiente |
| Terraform | Pendiente |
| Infraestructura Azure DEV | Pendiente |
| Azure PostgreSQL | Pendiente |
| ADF → Bronze | Pendiente |
| Databricks Silver | Pendiente |
| Databricks Gold | Pendiente |
| Unity Catalog | Pendiente |
| Monitoring y alertas | Pendiente |
| Ejecución `prod` con volumen completo | Pendiente |

---

## 23. Flujo validado hasta este punto

```text
config.yaml
    |
    v
generar_datos.py
    |
    +----------------+
    |                |
    v                v
   CSV            Parquet
    |
    v
cargar_postgresql.py
    |
    | PostgreSQL COPY
    v
PostgreSQL 16
    |
    +-- 7 tablas fuente
    +-- anomalías controladas
    +-- tipos SQL
    +-- ts_actualizacion
    +-- trigger de actualización
    +-- control_ingesta
    +-- watermark
    |
    v
[ siguiente fase ]
Azure Database for PostgreSQL
    |
    v
Azure Data Factory
    |
    v
ADLS Gen2 Bronze
```

---

## 24. Alcance de esta evidencia

Esta fase demuestra que la fuente de datos y los componentes locales funcionan antes del despliegue cloud.

Todavía no constituye evidencia de:

- despliegue real de recursos mediante Terraform;
- conexión contra Azure Database for PostgreSQL;
- ejecución real de ADF;
- ingesta Bronze en ADLS Gen2;
- procesamiento Silver en Databricks;
- procesamiento Gold en Databricks;
- gobierno mediante Unity Catalog;
- permisos del rol Analyst;
- alertas mediante Azure Monitor / Action Group;
- ejecución programada a las 02:00;
- comportamiento de retries en Azure;
- procesamiento del volumen completo de producción.

Estas evidencias deberán añadirse conforme se ejecuten las siguientes fases.

---

## 25. Conclusión

La fase local quedó validada de extremo a extremo hasta la fuente PostgreSQL.

El resultado permite continuar con el despliegue Azure sobre una base previamente probada y reduce el riesgo de diagnosticar simultáneamente errores de generación, esquema, carga e infraestructura cloud.

Estado al cierre:

```text
Generación         ✅
CSV / Parquet      ✅
Anomalías          ✅
Tests              ✅
Docker             ✅
PostgreSQL         ✅
Schema             ✅
Carga              ✅
Watermark          ✅
Incrementalidad    ✅
Azure              siguiente fase
```

---

## 26. Validación de Git y pre-commit

Como cierre de la fase local, se inicializó el repositorio Git y se configuraron controles automáticos antes de commit.

El commit inicial de la plataforma quedó consolidado como:

```text
7de8ab8 Inicializar LogiTrack data platform
```

Después del commit se verificó:

```bash
git status
```

Resultado:

```text
On branch main
nothing to commit, working tree clean
```

### 26.1 Validación de hooks sobre todo el repositorio

Se ejecutó:

```bash
poetry run pre-commit run --all-files
```

Resultado real:

```text
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check yaml...............................................................Passed
check json...............................................................Passed
check toml...............................................................Passed
check for added large files..............................................Passed
Run pytest...............................................................Passed
Validate repository......................................................Passed
```

Todos los hooks configurados pasaron correctamente.

Esto valida automáticamente, antes de futuros commits:

- eliminación de whitespace al final de línea;
- normalización del final de archivo;
- sintaxis YAML;
- sintaxis JSON;
- sintaxis TOML;
- prevención de archivos excesivamente grandes;
- ejecución de la suite `pytest`;
- ejecución del validador propio `scripts/validar_repo.py`.

### 26.2 Estado de cierre de la fase local

Al cierre de esta fase se dispone de:

```text
Generación sintética        ✅
CSV y Parquet               ✅
Anomalías controladas       ✅
Poetry / entorno aislado    ✅
Tests                       ✅ 11/11
Docker                      ✅
PostgreSQL 16               ✅
Schema relacional           ✅
Carga mediante COPY         ✅
Watermark inicial           ✅
Incrementalidad             ✅
Trigger ts_actualizacion    ✅
Git                         ✅
pre-commit                  ✅
Working tree limpio         ✅
Azure                       siguiente fase
```

La fase local queda, por tanto, cerrada y versionada antes de iniciar el despliegue cloud.
