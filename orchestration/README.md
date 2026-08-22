# Orquestación ADF como código

`adf/pipeline_principal.json` contiene el DAG principal y `adf/pipeline_notificar.json` concentra la lógica de notificación. Terraform despliega ambos con `azurerm_data_factory_pipeline.activities_json`.

## Flujo

```text
ForEach 7 tablas
  Lookup watermark inicial
  Lookup watermark final
  Copy PostgreSQL -> Bronze Parquet
  ├─ intento 1
  ├─ espera 30 s -> intento 2
  └─ espera 60 s -> intento 3
  Registrar log de ingesta
  Update watermark
        ↓
Auditar Bronze
        ↓
¿Anomalía de volumen >30%?
  ├─ sí: notificar + detener
  └─ no: continuar
        ↓
Procesar Silver
        ↓
Procesar Gold
        ↓
Calidad Gold
        ↓
Resumen ejecución
```

La interfaz de ADF se usa principalmente para ejecutar, observar y tomar evidencia; la definición del DAG vive en Git.

## Carga incremental

Cada tabla tiene un `watermark_utc` en PostgreSQL. ADF selecciona `ts_actualizacion > inicio AND ts_actualizacion <= fin`; el watermark solo avanza después de una copia y del registro de auditoría exitosos.

`log_ingesta_adf` conserva por tabla y lote: watermark inicial/final, registros copiados, bytes escritos y duración informada por Copy Activity.

Para una prueba manual de carga completa se puede pasar `carga_completa=true`.

## Reintentos

La `Copy` de Bronze implementa tres intentos explícitos con esperas 30 s y 60 s. Esto evita depender del intervalo fijo de la política nativa de ADF para el requisito de backoff exponencial. Las operaciones Spark usan `retry_exponential` con esperas 5 s, 10 s y 20 s y solo reintentan errores clasificados como transitorios.

## Notificaciones

`pl_logitrack_notificar` obtiene el webhook desde Key Vault una sola vez por mensaje y se reutiliza para:

- `FALLO`: pipeline, tarea, fecha y mensaje de error; después propaga el fallo para conservar el estado correcto del DAG.
- `ANOMALIA DE VOLUMEN`: detalle de la tabla y desviación; después propaga un `Fail` antes de Silver.
- `RESUMEN_DIARIO`: conteos Silver/Gold, rechazados, alertas de calidad y duración; no falla el DAG cuando el envío termina correctamente.

Azure Monitor + Action Group permanece como alerta secundaria del fallo general de ADF.

La URL no se versiona ni entra al state de Terraform: `scripts/configurar_webhook.py` la solicita de forma oculta y la guarda directamente como `notification-webhook-url` en Key Vault. Terraform solo controla el booleano `enable_notifications`.

## Qué no orquesta ADF

El pipeline termina después de Gold, sus controles de calidad y la notificación. `Consumo analítico` no es una transformación adicional: SQL Warehouse consulta las tablas Gold ya publicadas y gobernadas por Unity Catalog.
