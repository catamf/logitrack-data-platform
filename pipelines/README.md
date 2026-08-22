# Pipelines Databricks

- `00_common.py`: parámetros, rutas, lectura/escritura y retry exponencial.
- `00_auditar_bronze.py`: conteos y anomalía de volumen.
- `01_procesar_silver.py`: deduplicación, FK, PII, nulos, errores y reporte de calidad.
- `02_procesar_gold.py`: dimensiones, facts, trazabilidad, score, alertas de zona, agregaciones y KPI.
- `03_calidad_gold.py`: cinco controles automatizados.
- `04_resumen_ejecucion.py`: resumen por capa para evidencia operacional.

Silver y Gold se escriben en Delta. La escritura de tablas de negocio es determinística (`overwrite`) sobre el conjunto acumulado de Bronze, por lo que repetir el mismo input produce el mismo resultado. Los historiales de auditoría se anexan por `batch_id`.
