# Linaje de campos Gold

## `fact_envios.tiempo_entrega_real_horas`

- **Origen:** `TMS_ENVIOS.fec_recepcion`, `hra_recepcion`, `fec_entrega_real`.
- **Transformación:** se construye el timestamp de recepción y se calcula la diferencia contra la entrega real en horas.
- **Propósito:** medir duración real del envío y apoyar SLA.

## `fact_envios.clasificacion_retraso`

- **Origen:** `TMS_ENVIOS.fec_entrega_real`, `fec_entrega_programada`, `estado_final`.
- **Transformación:** diferencia en horas; `<=0 A tiempo`, `>0–4 Retraso leve`, `>4–24 Retraso moderado`, `>24 Retraso crítico`; no entregados reciben `No entregado`.
- **Propósito:** priorizar incumplimientos y análisis operacional.

## `fact_desempeno_conductor.score_desempeno`

- **Origen:** `TMS_ENVIOS`, `GPS_RUTAS`, `CAL_DESTINATARIOS`.
- **Transformación:** normaliza a 0–1 y pondera tasa de éxito 35%, adherencia 20%, velocidad vs estándar de zona 20%, inversa de intentos 15% y calificación 10%.
- **Propósito:** soportar bonos basados en desempeño multidimensional.

## `fact_alertas_zona.porcentaje_desviacion`

- **Origen:** `fact_envios`.
- **Transformación:** compara la tasa de fallo actual con el promedio de las cuatro semanas previas del mismo día de semana.
- **Propósito:** detectar deterioro inusual de una zona.

## Supuestos de modelado

- `fec_entrega_programada` no contiene hora. Para calcular retraso se interpreta el compromiso como las `23:59:59` del día programado.
- La fuente no contiene una velocidad estándar explícita por zona. Para `velocidad_vs_estandar_zona` se deriva un estándar operativo según el `indice_dificultad_operativa`: 18 km/h para dificultad alta, 24 km/h para media y 30 km/h para baja.
- `DIR_NOVEDADES.fec_novedad` contiene fecha sin hora; en la trazabilidad se representa al inicio del día y solo se incluyen novedades con fecha igual o posterior a la recepción.
