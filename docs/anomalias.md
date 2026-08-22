# Anomalías intencionales

| Patrón | Tabla | Generación | Tratamiento |
|---|---|---|---|
| Duplicado exacto | TMS_ENVIOS | Se anexan copias exactas de una fracción pequeña | Silver conserva una fila por `id_envio` y registra el rechazo |
| Peso negativo | TMS_ENVIOS | Una fracción muy pequeña recibe `peso_kg < 0` | Registro a `errores_pipeline`; no pasa a Silver confiable |
| Fecha imposible | TMS_ENVIOS | `fec_entrega_real < fec_recepcion` | Registro a errores; no pasa a Silver |

Los nulos (~5%) se introducen únicamente en campos no críticos. Las FK generadas permanecen válidas en la fuente base.
