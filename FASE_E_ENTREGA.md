# Fase E - Cierre y entrega

**Proyecto:** LogiTrack Data Platform
**Entorno principal validado:** DEV
**Estado:** en progreso

---

## 1. Objetivo

Cerrar los requisitos obligatorios pendientes de la prueba tecnica, consolidar las evidencias finales y preparar el repositorio para la entrega.

No se incorporaran nuevas tecnologias ni ampliaciones de arquitectura salvo que sean necesarias para cumplir un requisito explicito.

---

## 2. Verificacion del generador de datos

### Cobertura temporal

Configuracion verificada:

- fecha_inicio: 2025-08-01
- fecha_fin: 2026-08-21
- rango superior a 365 dias

**Estado:** CUMPLIDO Y EJECUTADO. Ver evidencia E.1.

### Formatos de salida

Configurados:

- CSV
- Parquet

**Estado:** CUMPLIDO Y VERIFICADO. Ver evidencia E.2.

### Calidad de datos sinteticos

Configurados:

- 5 % de nulos controlados
- envios duplicados
- pesos negativos
- fechas de entrega invalidas

**Estado:** CUMPLIDO EN CODIGO.

### Volumen minimo LogiTrack

| Tabla | Registros |
|---|---:|
| OPE_CONDUCTORES | 500 |
| CLI_REMITENTES | 200 |
| GEO_ZONAS | 300 |
| TMS_ENVIOS | 2.000.000 |
| GPS_RUTAS | 100.000 |
| CAL_DESTINATARIOS | 300.000 |
| DIR_NOVEDADES | 150.000 |

Los valores configurados coinciden con los minimos solicitados en la prueba tecnica.

**Estado:** CUMPLIDO Y EJECUTADO. Ver evidencia E.1.

---

## 3. Requisitos obligatorios de cierre

- Ejecutar el perfil prod y registrar los conteos reales.
- Obtener evidencia de la ejecucion con volumen completo.
- Obtener evidencia de notificacion de exito.
- Obtener evidencia de fallo controlado y su notificacion.
- Obtener evidencia de anomalia de volumen superior al 30 %.
- Dejar evidencia de la programacion diaria requerida.
- Verificar requisitos finales de calidad, errores y auditoria.
- Completar README y CHANGELOG.
- Ejecutar validaciones finales.
- Crear y compartir el repositorio remoto.

---

## 4. Evidencias

Esta seccion se actualizara unicamente con pruebas realmente ejecutadas durante el cierre.

### E.1 Generacion completa de datos

Fecha: 2026-08-23
Resultado: EXIT CODE 0
Duracion: 00:00:47.0536323
Periodo: 2025-08-01 a 2026-08-21
Formatos: CSV y Parquet
Volumen: 500 conductores; 200 remitentes; 300 zonas; 2.000.000 envios base; 100.000 rutas; 300.000 calificaciones; 150.000 novedades; 2.001.000 envios incluyendo duplicados intencionales.
Evidencia: docs/evidencias/fase_e/01_generacion_prod.txt
Estado: CUMPLIDO Y EJECUTADO.


### E.2 Archivos generados

Se verificaron las siete tablas del perfil prod en formatos CSV y Parquet, junto con manifest.json. Los archivos fueron generados localmente en data-generation/output/prod.
Evidencia: docs/evidencias/fase_e/02_archivos_prod.txt
Estado: CUMPLIDO Y VERIFICADO.


### E.3 Carga completa en Azure PostgreSQL DEV

Fecha: 2026-08-23
Destino: Azure Database for PostgreSQL DEV - base logitrack
Resultado: EXIT CODE 0
Duracion: 00:01:25.2966319
Conteos: OPE_CONDUCTORES=500; CLI_REMITENTES=200; GEO_ZONAS=300; TMS_ENVIOS=2.001.000; GPS_RUTAS=100.000; CAL_DESTINATARIOS=300.000; DIR_NOVEDADES=150.000.
La contrasena fue obtenida desde Azure Key Vault y no fue expuesta en la ejecucion.
Evidencia: docs/evidencias/fase_e/03_carga_postgresql_prod.txt
Estado: CUMPLIDO Y VERIFICADO.


### E.4 Programacion automatica diaria

Se verifico el trigger ADF trg_diario_0200_bogota en estado Started, con frecuencia diaria a las 07:00 UTC, equivalente a las 02:00 hora de Bogota (UTC-5).
Evidencia: docs/evidencias/fase_e/04_trigger_0200.txt
Estado: CUMPLIDO Y VERIFICADO.


### E.5 Notificacion de fallo controlado

Fecha: 2026-08-23
Run ID: 3d04632d-9f4e-11f1-8332-f4c52f12ecd6
Resultado esperado: Failed
Se ejecuto un fallo controlado despues del envio de la notificacion. El mensaje fue recibido correctamente por el canal webhook.
Evidencias: docs/evidencias/fase_e/07_fallo_controlado.txt y docs/evidencias/fase_e/07_fallo_controlado_webhook.png
Estado: CUMPLIDO Y VERIFICADO.


### E.6 Alerta por anomalia de volumen superior al 30 %

Fecha: 2026-08-23
Run ID: 0b22931b-9f4f-11f1-bf89-f4c52f12ecd6
Resultado esperado: Failed por detencion controlada posterior a la alerta.
Se activo de forma controlada la validacion de anomalia de volumen mediante force_volume_alert. El canal recibio LOGITRACK - ANOMALIA DE VOLUMEN con VOLUME_ALERT, cal_destinatarios=100.0% y umbral=30%.
Evidencias: docs/evidencias/fase_e/08_anomalia_volumen.txt y docs/evidencias/fase_e/08_anomalia_volumen_webhook.png
Estado: CUMPLIDO Y VERIFICADO.


### E.7 Entrega del resumen de una ejecucion exitosa

Fecha: 2026-08-23
Batch de origen exitoso: d636a27f-9f2f-11f1-8ad2-f4c52f12ecd6
Run de validacion del canal: 9f66db15-9f52-11f1-b1ea-f4c52f12ecd6
Resultado del envio: Succeeded
Resumen generado por la ejecucion E2E exitosa: silver=17250; gold=54519; rechazados=15; alertas_calidad=0; duracion_segundos=848.621.
El resumen historico real fue reenviado mediante pl_logitrack_notificar para validar su recepcion en el canal configurado. No se afirma que la notificacion estuviera habilitada durante la corrida historica original.
Evidencias: docs/evidencias/fase_e/09_resumen_fuente_exitoso.txt, docs/evidencias/fase_e/09_resumen_notificado.txt y docs/evidencias/fase_e/09_resumen_exitoso_webhook.png
Estado: CUMPLIDO Y VERIFICADO.


### E.8 Calidad automatica e idempotencia

Se verificaron cinco controles automaticos en Gold: DQ01_ID_ENVIO_NO_NULO, DQ02_ID_ENVIO_UNICO, DQ03_CONDUCTOR_EXISTE, DQ04_PESO_POSITIVO y DQ05_FECHA_COHERENTE. Los cinco controles finalizaron en PASS, con checks=5 y status=QUALITY_OK. Los resultados se almacenan en gold.resultados_calidad.

La idempotencia se implementa mediante watermark en Bronze, deduplicacion en Silver y sobrescritura deterministica de Silver y Gold. Los historiales de auditoria y calidad se identifican por batch_id.

Evidencia principal: docs/evidencias/fase_c/07_gold_calidad.png
Estado: CUMPLIDO Y VERIFICADO.


### E.9 Auditoria de acceso analitico

Se verifico el Historial de SQL de Databricks para la identidad analyst-logitrack-dev. El historial registra usuario, sentencia ejecutada, fecha/hora, resultado y SQL Warehouse utilizado. Se observan consultas exitosas sobre Gold mediante sql-logitrack-dev y rechazos de acceso sobre Silver y Bronze, coherentes con el modelo de minimo privilegio validado en Fase D.

Evidencia: docs/evidencias/fase_d/15_query_history_analyst.png
Estado: CUMPLIDO Y VERIFICADO.


### E.10 Convergencia final de Terraform

Se aplico la configuracion final de entrega con notificaciones y trigger diario habilitados. El apply final realizo 0 altas, 2 cambios in-place y 0 destrucciones. Un terraform plan posterior confirmo: No changes. Your infrastructure matches the configuration.

Evidencias: docs/evidencias/fase_e/10_terraform_apply_final.txt y docs/evidencias/fase_e/11_terraform_no_changes.txt
Estado: CUMPLIDO Y VERIFICADO.
