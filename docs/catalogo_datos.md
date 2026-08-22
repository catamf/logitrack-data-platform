# Catálogo de datos — Silver y Gold

Este catálogo documenta cada campo materializado por el pipeline. Los tipos son los tipos lógicos usados por Spark/Delta; Bronze conserva el esquema PostgreSQL y agrega metadatos de ingesta.

## Etiquetado de columnas sensibles en origen

| Tabla origen | Campo | Etiqueta | Tratamiento desde Silver |
|---|---|---|---|
| OPE_CONDUCTORES | `nomb_cond` | PII_NOMBRE | SHA-256 y eliminación del texto en claro |
| OPE_CONDUCTORES | `apell_cond` | PII_NOMBRE | SHA-256 y eliminación del texto en claro |
| OPE_CONDUCTORES | `tip_doc` | PII_IDENTIFICADOR | se conserva solo en capa restringida Silver/Gold técnico; Analyst no accede a Silver |
| OPE_CONDUCTORES | `num_doc_hash` | PII_HASHED | ya viene hasheado desde fuente |
| CAL_DESTINATARIOS | `comentario_texto` | PII_TEXTO_LIBRE | SHA-256; no se conserva texto en claro |
| DIR_NOVEDADES | `desc_novedad` | PII_TEXTO_LIBRE | SHA-256; no se conserva texto en claro |
| DIR_NOVEDADES | `id_agente_registro` | IDENTIFICADOR_INTERNO | acceso restringido; no expuesto en los objetos Gold disponibles al Analista |
| TMS_ENVIOS | `vr_declarado` | SENSIBLE_NEGOCIO | acceso restringido; Gold expone solo donde es necesario para penalidad |

## Convenciones

- **Sí (hash):** el valor identificable no se conserva en claro desde Silver.
- **Potencial:** texto o dato operacional que podría ser sensible según el contenido/contexto.
- Los campos `_ingesta_ts`, `_sistema_fuente` y `_batch_id` llegan desde ADF; `ts_actualizacion` es el watermark técnico de PostgreSQL.

## `silver.ope_conductores`
Conductores conformados; nombres en claro se eliminan y se sustituyen por hash.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `cond_id` | string | OPE_CONDUCTORES.cond_id | No |
| `tip_doc` | string | OPE_CONDUCTORES.tip_doc | Sí |
| `num_doc_hash` | string | OPE_CONDUCTORES.num_doc_hash; ya viene hasheado | Sí (hash) |
| `fec_ingreso` | date | OPE_CONDUCTORES.fec_ingreso | No |
| `id_ciudad_base` | string | OPE_CONDUCTORES.id_ciudad_base | No |
| `tip_vehiculo` | string | OPE_CONDUCTORES.tip_vehiculo | No |
| `cod_zona_asignada` | string | OPE_CONDUCTORES.cod_zona_asignada | No |
| `activo` | boolean | OPE_CONDUCTORES.activo | No |
| `calific_promedio_acum` | double | OPE_CONDUCTORES; 0.0 si nulo | No |
| `calific_promedio_acum_nulo` | boolean | Indicador de imputación | No |
| `nomb_cond_hash` | string | SHA-256 de nomb_cond; nombre en claro se elimina | Sí (hash) |
| `apell_cond_hash` | string | SHA-256 de apell_cond; apellido en claro se elimina | Sí (hash) |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.cli_remitentes`
Maestro limpio de clientes remitentes.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_remitente` | string | CLI_REMITENTES.id_remitente | No |
| `razon_social` | string | CLI_REMITENTES.razon_social | No |
| `tipo_cliente` | string | CLI_REMITENTES.tipo_cliente | No |
| `ciudad_principal` | string | CLI_REMITENTES.ciudad_principal | No |
| `sla_entrega_horas` | int | CLI_REMITENTES.sla_entrega_horas | No |
| `penalidad_porc` | double | CLI_REMITENTES.penalidad_porc | No |
| `activo` | boolean | CLI_REMITENTES.activo | No |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.geo_zonas`
Zonas operativas tipadas y con nulo descriptivo controlado.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_zona` | string | GEO_ZONAS.id_zona | No |
| `nom_zona` | string | GEO_ZONAS.nom_zona | No |
| `id_ciudad` | string | GEO_ZONAS.id_ciudad | No |
| `barrio_referencia` | string | GEO_ZONAS; `SIN_DATO` si nulo | Potencial |
| `latitud_centroide` | double | GEO_ZONAS.latitud_centroide | Potencial |
| `longitud_centroide` | double | GEO_ZONAS.longitud_centroide | Potencial |
| `nivel_trafico_prom` | double | GEO_ZONAS.nivel_trafico_prom | No |
| `tip_zona` | string | GEO_ZONAS.tip_zona | No |
| `distancia_bodega_km` | double | GEO_ZONAS.distancia_bodega_km | No |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.tms_envios`
Envíos deduplicados, con FK validadas y anomalías de negocio rechazadas.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_envio` | string | TMS_ENVIOS.id_envio | No |
| `id_remitente` | string | TMS_ENVIOS.id_remitente; FK validada | No |
| `cond_id` | string | TMS_ENVIOS.cond_id; FK validada | No |
| `id_zona_destino` | string | TMS_ENVIOS.id_zona_destino; FK validada | No |
| `tip_paquete` | string | TMS_ENVIOS.tip_paquete | No |
| `peso_kg` | double | TMS_ENVIOS.peso_kg; se rechaza <=0 | No |
| `fec_recepcion` | date | TMS_ENVIOS.fec_recepcion | No |
| `hra_recepcion` | string/time | TMS_ENVIOS.hra_recepcion | No |
| `fec_entrega_programada` | date | TMS_ENVIOS.fec_entrega_programada | No |
| `fec_intento1` | date | TMS_ENVIOS.fec_intento1 | No |
| `hra_intento1` | string/time | TMS_ENVIOS.hra_intento1 | No |
| `resultado_intento1` | string | TMS_ENVIOS.resultado_intento1 | No |
| `fec_intento2` | date | TMS_ENVIOS.fec_intento2 | No |
| `hra_intento2` | string/time | TMS_ENVIOS.hra_intento2 | No |
| `resultado_intento2` | string | TMS_ENVIOS.resultado_intento2 | No |
| `fec_entrega_real` | date | TMS_ENVIOS.fec_entrega_real; se rechaza si anterior a recepción | No |
| `estado_final` | string | TMS_ENVIOS.estado_final | No |
| `motivo_fallo_cod` | string | TMS_ENVIOS.motivo_fallo_cod | No |
| `vr_declarado` | double | TMS_ENVIOS; 0.0 si nulo | Potencial |
| `vr_declarado_nulo` | boolean | Indicador de imputación de vr_declarado | No |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.gps_rutas`
Rutas tipadas con conductor validado.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_ruta` | string | GPS_RUTAS.id_ruta | No |
| `cond_id` | string | GPS_RUTAS.cond_id; FK validada | No |
| `fec_ruta` | date | GPS_RUTAS.fec_ruta | No |
| `hra_inicio` | string/time | GPS_RUTAS.hra_inicio | No |
| `hra_fin` | string/time | GPS_RUTAS.hra_fin | No |
| `km_recorridos` | double | GPS_RUTAS.km_recorridos | No |
| `num_paradas_plan` | int | GPS_RUTAS.num_paradas_plan | No |
| `num_paradas_real` | int | GPS_RUTAS.num_paradas_real | No |
| `desviacion_ruta_km` | double | GPS_RUTAS.desviacion_ruta_km | No |
| `consumo_combustible` | double | GPS_RUTAS; 0.0 si nulo | No |
| `consumo_combustible_nulo` | boolean | Indicador de imputación | No |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.cal_destinatarios`
Calificaciones conformadas; el comentario libre no se conserva en claro.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_calificacion` | string | CAL_DESTINATARIOS.id_calificacion | No |
| `id_envio` | string | CAL_DESTINATARIOS.id_envio; FK validada | No |
| `fec_calificacion` | date | CAL_DESTINATARIOS.fec_calificacion | No |
| `puntaje_1_5` | int | CAL_DESTINATARIOS.puntaje_1_5 | No |
| `canal_calificacion` | string | CAL_DESTINATARIOS.canal_calificacion | No |
| `comentario_hash` | string | SHA-256 de comentario_texto | Sí (hash) |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.dir_novedades`
Novedades conformadas; la descripción libre no se conserva en claro.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_novedad` | string | DIR_NOVEDADES.id_novedad | No |
| `id_envio` | string | DIR_NOVEDADES.id_envio; FK validada | No |
| `fec_novedad` | date | DIR_NOVEDADES.fec_novedad | No |
| `tip_novedad` | string | DIR_NOVEDADES.tip_novedad | No |
| `id_agente_registro` | string | DIR_NOVEDADES.id_agente_registro | Potencial |
| `requiere_accion` | boolean | DIR_NOVEDADES.requiere_accion | No |
| `desc_novedad_hash` | string | SHA-256 de desc_novedad | Sí (hash) |
| `_ingesta_ts` | timestamp | ADF: marca de tiempo de ingesta | No |
| `_sistema_fuente` | string | ADF: literal `postgresql` | No |
| `_batch_id` | string | ADF: identificador de ejecución | No |
| `ts_actualizacion` | timestamp | PostgreSQL: timestamp técnico para incrementalidad | No |

## `silver.errores_pipeline`
Quarantine/auditoría de registros rechazados. No persiste payload PII en claro.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `error_id` | string | UUID generado en Silver | No |
| `batch_id` | string | Lote ADF | No |
| `tabla` | string | Tabla que originó el error | No |
| `clave_registro` | string | Clave técnica del registro | Potencial |
| `regla` | string | Regla incumplida | No |
| `payload_json` | string | JSON limitado a la clave técnica | Potencial |
| `fecha_error` | timestamp | Timestamp de detección | No |

## `silver.reporte_calidad`
Métricas de calidad por tabla y lote.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `batch_id` | string | Lote ADF | No |
| `tabla` | string | Tabla Silver | No |
| `registros_origen` | long | COUNT de Bronze | No |
| `registros_conformes` | long | COUNT después de limpieza | No |
| `registros_rechazados` | long | Diferencia origen-conformes | No |
| `porcentaje_conforme` | double | conformes/origen*100 | No |
| `metricas_nulos_json` | string | Porcentaje de nulos por columna | No |
| `generado_en` | timestamp | Timestamp de reporte | No |

## `silver.auditoria_ingesta`
Auditoría por ejecución de la ingesta a Bronze, basada en el log de Copy Activity generado por ADF.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `batch_id` | string | Lote ADF | No |
| `tabla` | string | Tabla Bronze | No |
| `registros` | long | Registros copiados por ADF en el lote | No |
| `bytes` | long | Bytes escritos por ADF en el lote | No |
| `duracion_segundos` | double | Duración reportada por la Copy Activity | No |
| `auditado_en` | timestamp | Timestamp de auditoría | No |

## `silver.alertas_volumen`
Alertas cuando el volumen se desvía >30% del promedio de hasta siete ejecuciones previas.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `tabla` | string | Auditoría Bronze | No |
| `batch_id` | string | Lote ADF | No |
| `registros` | long | Volumen observado | No |
| `bytes` | long | Bytes escritos en la ejecución | No |
| `duracion_segundos` | double | Duración de ingesta de la tabla en la ejecución | No |
| `auditado_en` | timestamp | Timestamp de auditoría | No |
| `promedio_7` | double | Promedio de siete ejecuciones previas | No |
| `desviacion_porc` | double | Desviación absoluta porcentual | No |
| `es_alerta` | boolean | True si supera 30% | No |
| `tipo_alerta` | string | ANOMALIA_VOLUMEN o PRUEBA_CONTROLADA | No |

## `gold.dim_conductores`
Dimensión de conductor para análisis.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `cond_id` | string | silver.ope_conductores.cond_id | No |
| `nomb_cond_hash` | string | Silver, hash de nombre | Sí (hash) |
| `apell_cond_hash` | string | Silver, hash de apellido | Sí (hash) |
| `num_doc_hash` | string | Silver, documento hasheado | Sí (hash) |
| `fec_ingreso` | date | Silver | No |
| `antiguedad_anios` | double | months_between(fecha actual,fec_ingreso)/12 | No |
| `id_ciudad_base` | string | Silver | No |
| `tip_vehiculo` | string | Catálogo Moto/Bicicleta/Van/Camion | No |
| `cod_zona_asignada` | string | Silver | No |
| `activo` | boolean | Silver | No |
| `calific_promedio_acum` | double | Silver | No |

## `gold.dim_remitentes`
Dimensión de clientes remitentes y SLA.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_remitente` | string | silver.cli_remitentes | No |
| `razon_social` | string | Silver | No |
| `tipo_cliente` | string | Silver | No |
| `ciudad_principal` | string | Silver | No |
| `sla_entrega_horas` | double | Silver, convertido a numérico | No |
| `penalidad_porc` | double | Silver | No |
| `activo` | boolean | Silver | No |
| `segmento_industria` | string | Ecommerce/Farmaceutico/Retail/Telecomunicaciones/Otro | No |
| `ts_actualizacion` | timestamp | Silver/origen técnico | No |
| `_ingesta_ts` | timestamp | Silver/ADF | No |
| `_sistema_fuente` | string | Silver/ADF | No |
| `_batch_id` | string | Silver/ADF | No |

## `gold.dim_zonas`
Dimensión geográfica y dificultad operativa.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_zona` | string | silver.geo_zonas | No |
| `nom_zona` | string | Silver | No |
| `id_ciudad` | string | Silver | No |
| `barrio_referencia` | string | Silver | Potencial |
| `latitud_centroide` | double | Silver | Potencial |
| `longitud_centroide` | double | Silver | Potencial |
| `nivel_trafico_prom` | double | Silver | No |
| `tip_zona` | string | Silver | No |
| `distancia_bodega_km` | double | Silver | No |
| `indice_dificultad_operativa` | int | 60% tráfico normalizado + 40% distancia, escala 1-5 | No |
| `municipio` | string | Mapeo id_ciudad a nombre de ciudad | No |
| `ts_actualizacion` | timestamp | Silver/origen técnico | No |
| `_ingesta_ts` | timestamp | Silver/ADF | No |
| `_sistema_fuente` | string | Silver/ADF | No |
| `_batch_id` | string | Silver/ADF | No |

## `gold.fact_envios`
Hecho central de envíos con SLA, intentos, retraso y penalidad.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_envio` | string | silver.tms_envios | No |
| `id_remitente` | string | Silver | No |
| `cond_id` | string | Silver | No |
| `id_zona_destino` | string | Silver | No |
| `tip_paquete` | string | Silver | No |
| `peso_kg` | double | Silver | No |
| `fec_recepcion` | date | Silver | No |
| `hra_recepcion` | string/time | Silver | No |
| `fec_entrega_programada` | date | Silver | No |
| `fec_intento1` | date | Silver | No |
| `hra_intento1` | string/time | Silver | No |
| `resultado_intento1` | string | Silver | No |
| `fec_intento2` | date | Silver | No |
| `hra_intento2` | string/time | Silver | No |
| `resultado_intento2` | string | Silver | No |
| `fec_entrega_real` | date | Silver | No |
| `estado_final` | string | Silver | No |
| `motivo_fallo_cod` | string | Silver | No |
| `vr_declarado` | double | Silver | Potencial |
| `vr_declarado_nulo` | boolean | Silver | No |
| `ts_actualizacion` | timestamp | Silver/origen técnico | No |
| `_ingesta_ts` | timestamp | Silver/ADF | No |
| `_sistema_fuente` | string | Silver/ADF | No |
| `_batch_id` | string | Silver/ADF | No |
| `sla_entrega_horas` | double | dim_remitentes / silver.cli_remitentes | No |
| `penalidad_porc` | double | silver.cli_remitentes | No |
| `recepcion_ts` | timestamp | fec_recepcion + hra_recepcion | No |
| `entrega_real_ts` | timestamp | timestamp del intento exitoso; fallback a fec_entrega_real | No |
| `entrega_programada_ts` | timestamp | fec_entrega_programada + 23:59:59 (supuesto) | No |
| `tiempo_entrega_real_horas` | double | entrega_real_ts - recepcion_ts | No |
| `cumplimiento_sla` | boolean | Entregado y tiempo_real <= SLA | No |
| `motivo_fallo_desc` | string | Mapeo legible de motivo_fallo_cod | No |
| `numero_intentos` | int | 1 o 2 según segundo intento | No |
| `retraso_horas` | double | entrega_real_ts - entrega_programada_ts | No |
| `clasificacion_retraso` | string | A tiempo / leve / moderado / crítico / No entregado | No |
| `penalidad_estimada` | double | vr_declarado * penalidad_porc si incumple SLA | Potencial |
| `anio_recepcion` | int | year(fec_recepcion); partición física | No |
| `mes_recepcion` | int | month(fec_recepcion); partición física | No |

## `gold.fact_rutas`
Hecho de eficiencia de rutas.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_ruta` | string | silver.gps_rutas | No |
| `cond_id` | string | Silver | No |
| `fec_ruta` | date | Silver | No |
| `hra_inicio` | string/time | Silver | No |
| `hra_fin` | string/time | Silver | No |
| `km_recorridos` | double | Silver | No |
| `num_paradas_plan` | int | Silver | No |
| `num_paradas_real` | int | Silver | No |
| `desviacion_ruta_km` | double | Silver | No |
| `consumo_combustible` | double | Silver | No |
| `consumo_combustible_nulo` | boolean | Silver | No |
| `ts_actualizacion` | timestamp | Silver/origen técnico | No |
| `_ingesta_ts` | timestamp | Silver/ADF | No |
| `_sistema_fuente` | string | Silver/ADF | No |
| `_batch_id` | string | Silver/ADF | No |
| `horas_trabajadas` | double | hra_fin - hra_inicio | No |
| `eficiencia_ruta` | double | num_paradas_real / num_paradas_plan | No |
| `velocidad_promedio_kmh` | double | km_recorridos / horas_trabajadas | No |
| `desviacion_porc` | double | desviacion_ruta_km/km_recorridos*100 | No |
| `anio_ruta` | int | year(fec_ruta); partición física | No |
| `mes_ruta` | int | month(fec_ruta); partición física | No |

## `gold.fact_desempeno_conductor`
Desempeño diario multidimensional por conductor.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `cond_id` | string | fact_envios/fact_rutas/calificaciones | No |
| `fecha` | date | Fecha de recepción/ruta | No |
| `tasa_exito` | double | Promedio de flag Entregado | No |
| `intentos_promedio` | double | Promedio de numero_intentos | No |
| `zona_referencia` | string | Primera zona del conductor en el día | No |
| `penalidad_estimada_total` | double | Suma de penalidad estimada | Potencial |
| `desviacion_promedio_porc` | double | Promedio fact_rutas.desviacion_porc | No |
| `velocidad_promedio_kmh` | double | Promedio fact_rutas.velocidad_promedio_kmh | No |
| `calificacion_promedio` | double | Promedio CAL_DESTINATARIOS.puntaje_1_5 | No |
| `indice_dificultad_operativa` | int | dim_zonas | No |
| `adherencia_ruta_normalizada` | double | 1 - min(desviacion/100,1) | No |
| `velocidad_estandar_zona` | double | 18/24/30 km/h según dificultad (supuesto) | No |
| `velocidad_vs_estandar_zona` | double | min(velocidad/estándar,1) | No |
| `inversa_intentos_promedio` | double | min(1/intentos_promedio,1) | No |
| `calificacion_destinatario_normalizada` | double | min(calificacion/5,1) | No |
| `score_desempeno` | double | 0.35 éxito + 0.20 adherencia + 0.20 velocidad + 0.15 inversa intentos + 0.10 rating | No |
| `anio` | int | year(fecha); partición física | No |
| `mes` | int | month(fecha); partición física | No |

## `gold.fact_trazabilidad_envio`
Timeline ordenado de eventos por envío.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_envio` | string | TMS_ENVIOS/DIR_NOVEDADES | No |
| `evento_ts` | timestamp | Timestamp reconstruido del evento | No |
| `evento` | string | Recepcion / Intento 1 / Intento 2 / Entrega / Novedad | No |
| `orden_evento` | int | row_number por id_envio y evento_ts | No |
| `evento_anterior_ts` | timestamp | lag(evento_ts) | No |
| `horas_desde_evento_anterior` | double | evento_ts - evento_anterior_ts | No |
| `anio_evento` | int | year(evento_ts); partición física | No |
| `mes_evento` | int | month(evento_ts); partición física | No |

## `gold.fact_alertas_zona`
Alertas diarias de tasa de fallo por zona y día de semana.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `id_zona_destino` | string | fact_envios | No |
| `fecha` | date | fact_envios.fec_recepcion | No |
| `tasa_fallo_actual` | double | Promedio de estado_final != Entregado | No |
| `dia_semana` | int | dayofweek(fecha) | No |
| `promedio_historico_4` | double | Promedio de cuatro observaciones anteriores del mismo día de semana | No |
| `porcentaje_desviacion` | double | (actual-histórico)/histórico*100 | No |
| `anio` | int | year(fecha); partición física | No |
| `mes` | int | month(fecha); partición física | No |

## `gold.agg_desempeno_zona`
Agregación diaria por zona.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `fecha` | date | fact_envios.fec_recepcion | No |
| `id_zona_destino` | string | fact_envios | No |
| `envios` | long | COUNT(*) | No |
| `tasa_cumplimiento_sla` | double | AVG(cumplimiento_sla) | No |
| `tasa_exito` | double | AVG(estado_final=Entregado) | No |
| `penalidad_estimada` | double | SUM(penalidad_estimada) | Potencial |

## `gold.agg_sla_remitente`
Agregación diaria por cliente remitente.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `fecha` | date | fact_envios.fec_recepcion | No |
| `id_remitente` | string | fact_envios | No |
| `envios` | long | COUNT(*) | No |
| `tasa_cumplimiento_sla` | double | AVG(cumplimiento_sla) | No |
| `tasa_exito` | double | AVG(estado_final=Entregado) | No |
| `penalidad_estimada` | double | SUM(penalidad_estimada) | Potencial |

## `gold.agg_tipo_paquete`
Agregación diaria por tipo de paquete.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `fecha` | date | fact_envios.fec_recepcion | No |
| `tip_paquete` | string | fact_envios | No |
| `envios` | long | COUNT(*) | No |
| `tasa_exito` | double | AVG(estado_final=Entregado) | No |
| `tiempo_promedio_horas` | double | AVG(tiempo_entrega_real_horas) | No |
| `penalidad_estimada` | double | SUM(penalidad_estimada) | Potencial |

## `gold.kpi_logistica_diaria`
KPIs ejecutivos diarios listos para visualización.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `fecha` | date | fact_envios.fec_recepcion | No |
| `total_envios` | long | COUNT(*) | No |
| `envios_entregados` | long | SUM(estado_final=Entregado) | No |
| `tasa_exito` | double | AVG(flag Entregado) | No |
| `tasa_cumplimiento_sla` | double | AVG(cumplimiento_sla) | No |
| `tiempo_promedio_entrega_horas` | double | AVG(tiempo_entrega_real_horas) | No |
| `penalidad_estimada_total` | double | SUM(penalidad_estimada) | Potencial |

## `gold.resultados_calidad`
Resultado de las cinco pruebas automáticas de Gold.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `batch_id` | string | Lote ADF | No |
| `regla` | string | Identificador DQ | No |
| `estado` | string | PASS/FAIL | No |
| `fallos` | long | Cantidad de incumplimientos | No |
| `detalle` | string | Descripción de regla | No |
| `ejecutado_en` | timestamp | Timestamp de prueba | No |

## `gold.resumen_ejecuciones`
Resumen operacional por ejecución.
| Campo | Tipo | Origen / transformación | Sensible |
|---|---|---|---|
| `batch_id` | string | Lote ADF | No |
| `resumen_json` | string | Conteos por capa/tabla, estado y timestamps | No |
| `registros_silver` | long | Suma de registros de las tablas Silver | No |
| `registros_gold` | long | Suma de registros de las tablas Gold principales | No |
| `registros_rechazados` | long | COUNT de errores del batch | No |
| `alertas_calidad` | long | Cantidad de DQ FAIL | No |
| `duracion_total_segundos` | double | Finalización - TriggerTime de ADF | No |
| `finalizado_en` | timestamp | Timestamp UTC final | No |
