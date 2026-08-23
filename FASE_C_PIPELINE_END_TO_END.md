# Fase C - Pipeline end-to-end

## 1. Objetivo

Esta fase registra la validación funcional del pipeline end-to-end de LogiTrack en Azure.

El objetivo fue comprobar que la plataforma puede ejecutar de forma integrada:

```text
Azure Database for PostgreSQL
        ↓
Azure Data Factory
        ↓
Bronze en ADLS Gen2
        ↓
Databricks
        ↓
Silver Delta
        ↓
Gold Delta
        ↓
Controles de calidad
        ↓
Resumen de ejecución
```

Las evidencias descritas en este documento corresponden a ejecuciones reales realizadas durante el desarrollo.

---

## 2. Pipeline validado

Pipeline principal:

```text
pl_logitrack_end_to_end
```

Data Factory:

```text
adf-logitrack-dev-mn79c
```

El flujo ejecutado incluye:

1. lectura incremental desde Azure Database for PostgreSQL;
2. escritura de Bronze en ADLS Gen2;
3. auditoría de Bronze;
4. transformación a Silver;
5. tratamiento de calidad y anomalías;
6. transformación a Gold;
7. ejecución de controles de calidad Gold;
8. generación del resumen final de ejecución.

---

## 3. Incidencia 1 - parsing de `%run` en Databricks

La primera ejecución funcional de ADF alcanzó correctamente las actividades PostgreSQL, pero falló al iniciar el notebook `00_auditar_bronze`.

Run de ADF:

```text
34794ce2-9eda-11f1-95dd-f4c52f12ecd6
```

La causa fue el uso de:

```python
# MAGIC %run ./00_common
```

sin un separador de celda Databricks posterior.

Se corrigieron los notebooks:

```text
00_auditar_bronze.py
01_procesar_silver.py
02_procesar_gold.py
03_calidad_gold.py
04_resumen_ejecucion.py
```

añadiendo:

```python
# COMMAND ----------
```

después del `%run`.

La corrección se desplegó mediante Terraform.

---

## 4. Incidencia 2 - acceso Databricks a Bronze

La siguiente ejecución avanzó más allá del error de parsing.

Run de ADF:

```text
dcbcfa8b-9edd-11f1-9bca-f4c52f12ecd6
```

`Auditar_Bronze` falló al intentar leer ADLS con:

```text
Invalid configuration value detected for fs.azure.account.key
```

No se implementó un fallback mediante account key ni OAuth con client secret.

La solución adoptada mantuvo la arquitectura objetivo:

```text
Databricks Access Connector
        +
Managed Identity
        +
Storage Credential
        +
External Locations
        +
Unity Catalog
```

Después de habilitar Unity Catalog y validar el acceso al almacenamiento, `Auditar_Bronze` pudo leer correctamente Bronze.

---

## 5. Incidencia 3 - combinación de fecha y hora en Gold

En la ejecución:

```text
f47886be-9ee4-11f1-a666-f4c52f12ecd6
```

se validaron correctamente:

```text
Auditar_Bronze  -> Succeeded
Procesar_Silver -> Succeeded
```

pero `Procesar_Gold` falló.

El error observado fue:

```text
[CAST_INVALID_INPUT]
The value '2025-11-16 1970-01-01 16:16:00'
of type STRING cannot be cast to TIMESTAMP
```

La causa fue que algunas columnas `hra_*` llegaban a Gold representadas como timestamp con fecha auxiliar `1970-01-01`.

Se corrigió `02_procesar_gold.py` mediante una función que:

1. extrae únicamente `HH:mm:ss`;
2. normaliza la fecha a `yyyy-MM-dd`;
3. combina ambas partes;
4. genera el timestamp final con formato explícito.

La sintaxis Python fue validada antes del despliegue.

Terraform mostró únicamente:

```text
Plan: 0 to add, 1 to change, 0 to destroy.
```

para:

```text
databricks_notebook.pipeline["02_procesar_gold"]
```

La aplicación terminó correctamente.

---

## 6. Primera ejecución end-to-end exitosa

Después de corregir Gold se ejecutó:

```text
9d74929b-9ee9-11f1-b7f5-f4c52f12ecd6
```

Resultado general:

```text
Pipeline: Succeeded
```

Etapas Databricks:

```text
Auditar_Bronze       Succeeded
Procesar_Silver      Succeeded
Procesar_Gold        Succeeded
Calidad_Gold         Succeeded
Resumen_Ejecucion    Succeeded
```

Ventana observada:

```text
Inicio: 2026-08-23T11:56:04.485797+00:00
Fin:    2026-08-23T12:08:54.885797+00:00
```

---

## 7. Bronze

`Auditar_Bronze` devolvió:

```text
BRONZE_OK | batch_id=9d74929b-9ee9-11f1-b7f5-f4c52f12ecd6 | tablas=7
```

Las siete tablas fuente observadas en Bronze fueron:

```text
cal_destinatarios
cli_remitentes
dir_novedades
geo_zonas
gps_rutas
ope_conductores
tms_envios
```

Además existe el directorio técnico `_control`.

Evidencias visuales:

```text
docs/evidencias/fase_c/03a_bronze_estructura.png
docs/evidencias/fase_c/03b_bronze_tms_envios_particion.png
```

---

## 8. Silver y reporte de calidad

`Procesar_Silver` devolvió:

```json
{
  "batch_id": "9d74929b-9ee9-11f1-b7f5-f4c52f12ecd6",
  "errores": 20,
  "status": "SILVER_OK"
}
```

`errores=20` corresponde a hallazgos de calidad registrados en:

```text
logitrack_dev.silver.errores_pipeline
```

No corresponde directamente al número de filas efectivamente rechazadas.

Se consultó:

```text
logitrack_dev.silver.reporte_calidad
```

Resultado:

| tabla | registros_origen | registros_conformes | registros_rechazados | porcentaje_conforme |
|---|---:|---:|---:|---:|
| cal_destinatarios | 2500 | 2500 | 0 | 100.0 |
| cli_remitentes | 60 | 60 | 0 | 100.0 |
| dir_novedades | 1500 | 1500 | 0 | 100.0 |
| geo_zonas | 80 | 80 | 0 | 100.0 |
| gps_rutas | 3000 | 3000 | 0 | 100.0 |
| ope_conductores | 120 | 120 | 0 | 100.0 |
| tms_envios | 10005 | 9990 | 15 | 99.8501 |

Total de filas efectivamente rechazadas:

```text
15
```

Evidencia visual:

```text
docs/evidencias/fase_c/04_silver_reporte_calidad.png
```

---

## 9. Hallazgos en `errores_pipeline`

Para el batch exitoso se observaron 20 hallazgos, todos asociados a `tms_envios`.

Distribución validada:

```text
DUPLICADO_CLAVE                     10
FECHA_ENTREGA_ANTERIOR_RECEPCION     5
PESO_NO_POSITIVO                     5
---------------------------------------
TOTAL                               20
```

Los 10 hallazgos de duplicidad corresponden a cinco claves duplicadas, porque cada una aparece dos veces en el registro de errores.

Por tanto:

```text
20 hallazgos de calidad
!=
15 filas efectivamente rechazadas
```

Evidencia visual:

```text
docs/evidencias/fase_c/05_silver_errores_pipeline.png
```

---

## 10. Objetos Gold

`Procesar_Gold` devolvió:

```text
GOLD_OK
dimensions = 3
facts = 5
aggregates = 3
kpi = 1
```

En `logitrack_dev.gold` se observaron 14 tablas: 12 objetos analíticos y 2 tablas técnicas.

### Dimensiones

```text
dim_conductores
dim_remitentes
dim_zonas
```

### Facts

```text
fact_alertas_zona
fact_desempeno_conductor
fact_envios
fact_rutas
fact_trazabilidad_envio
```

### Agregaciones

```text
agg_desempeno_zona
agg_sla_remitente
agg_tipo_paquete
```

### KPI

```text
kpi_logistica_diaria
```

### Tablas técnicas

```text
resultados_calidad
resumen_ejecuciones
```

Evidencia visual:

```text
docs/evidencias/fase_c/06_gold_objetos.png
```

---

## 11. Cinco controles de calidad Gold

Se consultó:

```text
logitrack_dev.gold.resultados_calidad
```

para el batch exitoso.

| Regla | Estado | Fallos |
|---|---|---:|
| `DQ01_ID_ENVIO_NO_NULO` | PASS | 0 |
| `DQ02_ID_ENVIO_UNICO` | PASS | 0 |
| `DQ03_CONDUCTOR_EXISTE` | PASS | 0 |
| `DQ04_PESO_POSITIVO` | PASS | 0 |
| `DQ05_FECHA_COHERENTE` | PASS | 0 |

La actividad `Calidad_Gold` devolvió:

```json
{
  "batch_id": "9d74929b-9ee9-11f1-b7f5-f4c52f12ecd6",
  "checks": 5,
  "status": "QUALITY_OK"
}
```

Evidencia visual:

```text
docs/evidencias/fase_c/07_gold_calidad.png
```

---

## 12. Incidencia semántica en `registros_rechazados`

La primera ejecución end-to-end exitosa generó:

```text
silver=17250
gold=54519
rechazados=20
alertas_calidad=0
```

Se comprobó que `04_resumen_ejecucion.py` calculaba `registros_rechazados` contando las filas de `silver.errores_pipeline`.

Ese cálculo era semánticamente incorrecto porque `errores_pipeline` contiene hallazgos de calidad.

Silver ya almacenaba el valor correcto en:

```text
silver.reporte_calidad.registros_rechazados
```

Para `tms_envios`:

```text
10005 - 9990 = 15
```

---

## 13. Corrección del resumen

Se modificó `04_resumen_ejecucion.py` para sumar `registros_rechazados` desde `silver.reporte_calidad` para el batch actual.

La sintaxis Python fue validada.

Terraform mostró únicamente:

```text
databricks_notebook.pipeline["04_resumen_ejecucion"]
Plan: 0 to add, 1 to change, 0 to destroy.
```

La modificación fue aplicada correctamente.

Después del despliegue, Terraform devolvió:

```text
No changes. Your infrastructure matches the configuration.
```

---

## 14. Segunda ejecución end-to-end exitosa

Para validar la corrección se generó:

```text
45463ed4-9f0e-11f1-a1b7-f4c52f12ecd6
```

Resultado:

```text
Pipeline: Succeeded
```

`Resumen_Ejecucion` devolvió:

```text
RESUMEN_DIARIO |
batch_id=45463ed4-9f0e-11f1-a1b7-f4c52f12ecd6 |
silver=17250 |
gold=54519 |
rechazados=15 |
alertas_calidad=0 |
duracion_segundos=511.93
```

La tabla `logitrack_dev.gold.resumen_ejecuciones` permite observar el antes y el después:

| Ejecución | Silver | Gold | Rechazados | Alertas calidad |
|---|---:|---:|---:|---:|
| `9d74929b-...` | 17250 | 54519 | 20 | 0 |
| `45463ed4-...` | 17250 | 54519 | 15 | 0 |

La corrección no cambió los volúmenes procesados; corrigió únicamente la semántica de la métrica.

Evidencia visual:

```text
docs/evidencias/fase_c/08_resumen_ejecucion_corregido.png
```

---

## 15. Resultado técnico de `Procesar_Gold`

Para el segundo batch se recuperó el activity run de `Procesar_Gold`.

Resultado:

```text
activityName : Procesar_Gold
status       : Succeeded
batch_id     : 45463ed4-9f0e-11f1-a1b7-f4c52f12ecd6
gold_status  : GOLD_OK
dimensions   : 3
facts        : 5
aggregates   : 3
kpi          : 1
```

Evidencia visual:

```text
docs/evidencias/fase_c/10_gold_run_output.png
```

---

## 16. Resultado de la fase

La Fase C demostró funcionalmente el flujo:

```text
PostgreSQL
→ ADF
→ Bronze
→ Silver
→ Gold
→ calidad
→ resumen
```

Se validó:

- ingesta de siete tablas fuente;
- Bronze disponible en ADLS Gen2;
- transformación Silver;
- detección y persistencia de anomalías;
- 20 hallazgos de calidad y 15 filas efectivamente rechazadas;
- materialización de 12 objetos analíticos Gold;
- cinco controles de calidad Gold en `PASS`;
- cero alertas de calidad;
- dos ejecuciones end-to-end exitosas;
- corrección y revalidación de `registros_rechazados`;
- resultado técnico `GOLD_OK`.

---

## 17. Pendientes después de la Fase C

La fase de pipeline queda funcionalmente validada.

Permanecen para fases posteriores:

1. habilitar y validar SQL Warehouse;
2. configurar y validar permisos finales de Analyst y Admin;
3. demostrar que Analyst puede consultar Gold;
4. demostrar que Analyst no puede consultar Bronze/Silver;
5. validar consumo de `gold.kpi_logistica_diaria` mediante SQL Warehouse;
6. completar las evidencias operativas y de fallo controlado requeridas para la entrega;
7. retirar recursos legacy PostgreSQL/ADF únicamente después de comprobar referencias exactas.

Los puntos anteriores no se consideran completados dentro de la Fase C.
