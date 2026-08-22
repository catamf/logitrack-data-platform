# Calidad de datos

## Silver

Por ejecución se calcula:

- porcentaje de nulos por columna;
- número de registros rechazados;
- porcentaje de registros conformes;
- duplicados detectados;
- FK inexistentes;
- registros con fechas/pesos inválidos.

## Cinco validaciones automatizadas en Gold

1. `fact_envios.id_envio` no nulo.
2. `fact_envios.id_envio` único.
3. `fact_envios.cond_id` existe en `dim_conductores`.
4. `fact_envios.peso_kg > 0` cuando no es nulo.
5. Si existe `fec_entrega_real`, no puede ser anterior a `fec_recepcion`.

Los resultados se escriben en `gold.resultados_calidad` con lote, regla, estado y detalle.

## Estrategia de nulos

| Campo / tipo | Estrategia | Motivo |
|---|---|---|
| claves y campos obligatorios | rechazo a `silver.errores_pipeline` | no se puede garantizar integridad |
| `calific_promedio_acum` | `0.0` + indicador `_nulo` | conserva fila y deja trazabilidad de imputación |
| `barrio_referencia` | `SIN_DATO` | atributo descriptivo no crítico |
| `vr_declarado` | `0.0` + indicador `_nulo` | permite agregación sin perder que faltaba el dato |
| `consumo_combustible` | `0.0` + indicador `_nulo` | no bloquea la ruta y conserva indicador de ausencia |
| campos naturalmente opcionales de intentos/entrega | se mantienen nulos | el nulo tiene significado de negocio |
| texto libre de calificación/novedad | hash o nulo | evita persistir texto potencialmente sensible en claro desde Silver |

`errores_pipeline.payload_json` conserva únicamente la clave técnica del registro rechazado, no el payload completo, para no reintroducir PII cruda en Silver.
