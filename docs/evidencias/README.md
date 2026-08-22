# Checklist de evidencias

No se incluyen capturas ficticias. Toma evidencia de tu propia ejecución. PostgreSQL local es una validación de desarrollo y no sustituye las evidencias cloud; las capturas obligatorias de la fuente deben provenir de Azure Database for PostgreSQL.

- [ ] `terraform apply` exitoso o portal con los recursos desplegados.
- [ ] Lista de recursos, región y propósito.
- [ ] `SELECT COUNT(*)` para las siete tablas fuente.
- [ ] Archivos Bronze en ADLS, con partición `anio/mes/dia`.
- [ ] Tabla/consulta del log de ingesta con conteo, tamaño y duración.
- [ ] Reporte de calidad Silver.
- [ ] Registro en `errores_pipeline`.
- [ ] Tablas Delta Silver.
- [ ] Dimensiones/facts Gold.
- [ ] Tres agregaciones Gold y tabla KPI ejecutivo.
- [ ] Cinco pruebas de calidad con PASS/FAIL.
- [ ] Pipeline ADF completo con Bronze → Silver → Gold en verde.
- [ ] Historial de al menos dos ejecuciones.
- [ ] Ejecución fallida controlada y alerta recibida.
- [ ] Resumen de ejecución exitosa.
- [ ] Evidencia de anomalía de volumen >30%.
- [ ] Roles Data Engineer / Analyst / Admin implementados.
- [ ] Analyst sin permiso sobre el cluster ETL y con `CAN_USE` sobre SQL Warehouse.
- [ ] Admin con control sobre cluster ETL y SQL Warehouse.
- [ ] Consulta del Analista a Gold exitosa.
- [ ] Consulta de `gold.kpi_logistica_diaria` mediante SQL Warehouse (evidencia de consumo analítico).
- [ ] Consulta del Analista a Bronze/Silver rechazada.
