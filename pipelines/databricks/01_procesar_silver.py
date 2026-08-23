# Databricks notebook source
# MAGIC %run ./00_common

# COMMAND ----------

from functools import reduce
from pyspark.sql import DataFrame, functions as F

TABLE_KEYS = {
    "ope_conductores": "cond_id",
    "cli_remitentes": "id_remitente",
    "geo_zonas": "id_zona",
    "tms_envios": "id_envio",
    "gps_rutas": "id_ruta",
    "cal_destinatarios": "id_calificacion",
    "dir_novedades": "id_novedad",
}
REQUIRED = {
    "ope_conductores": ["cond_id", "fec_ingreso", "cod_zona_asignada"],
    "cli_remitentes": ["id_remitente", "sla_entrega_horas"],
    "geo_zonas": ["id_zona", "id_ciudad"],
    "tms_envios": ["id_envio", "id_remitente", "cond_id", "id_zona_destino", "fec_recepcion"],
    "gps_rutas": ["id_ruta", "cond_id", "fec_ruta"],
    "cal_destinatarios": ["id_calificacion", "id_envio", "puntaje_1_5"],
    "dir_novedades": ["id_novedad", "id_envio", "fec_novedad"],
}

CASTS = {
    "ope_conductores": {"fec_ingreso": "date", "activo": "boolean", "calific_promedio_acum": "double", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
    "cli_remitentes": {"sla_entrega_horas": "int", "penalidad_porc": "double", "activo": "boolean", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
    "geo_zonas": {"latitud_centroide": "double", "longitud_centroide": "double", "nivel_trafico_prom": "double", "distancia_bodega_km": "double", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
    "tms_envios": {"peso_kg": "double", "fec_recepcion": "date", "fec_entrega_programada": "date", "fec_intento1": "date", "fec_intento2": "date", "fec_entrega_real": "date", "vr_declarado": "double", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
    "gps_rutas": {"fec_ruta": "date", "km_recorridos": "double", "num_paradas_plan": "int", "num_paradas_real": "int", "desviacion_ruta_km": "double", "consumo_combustible": "double", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
    "cal_destinatarios": {"fec_calificacion": "date", "puntaje_1_5": "int", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
    "dir_novedades": {"fec_novedad": "date", "requiere_accion": "boolean", "ts_actualizacion": "timestamp", "_ingesta_ts": "timestamp"},
}


def error_rows(df: DataFrame, table: str, key: str, rule: str, condition) -> DataFrame:
    return (df.filter(condition)
            .select(
                F.expr("uuid()").alias("error_id"),
                F.lit(BATCH_ID).alias("batch_id"),
                F.lit(table).alias("tabla"),
                F.col(key).cast("string").alias("clave_registro"),
                F.lit(rule).alias("regla"),
                F.to_json(F.struct(F.col(key).cast("string").alias("clave_registro"))).alias("payload_json"),
                F.current_timestamp().alias("fecha_error"),
            ))


def required_condition(columns: list[str]):
    cond = F.lit(False)
    for c in columns:
        cond = cond | F.col(c).isNull()
    return cond




def main():
    raw = {t: read_parquet(bronze_path(t)) for t in TABLE_KEYS}
    errors = []
    clean = {}
    report = []

    # 1) Reglas genéricas: nulos obligatorios y duplicados.
    for table, df in raw.items():
        key = TABLE_KEYS[table]
        null_cond = required_condition(REQUIRED[table])
        errors.append(error_rows(df, table, key, "CAMPOS_OBLIGATORIOS_NULOS", null_cond))

        dup_ids = df.groupBy(key).count().filter("count > 1").select(key)
        errors.append(error_rows(df.join(dup_ids, key, "inner"), table, key, "DUPLICADO_CLAVE", F.lit(True)))

        valid = df.filter(~null_cond).dropDuplicates([key])
        clean[table] = valid

    # 2) Tipado explícito para que Silver tenga un contrato estable aunque cambie el lector de Bronze.
    for table, casts in CASTS.items():
        df = clean[table]
        for column, spark_type in casts.items():
            if column in df.columns:
                df = df.withColumn(column, F.col(column).cast(spark_type))
        clean[table] = df

    # 3) Integridad referencial.
    refs = [
        ("ope_conductores", "cod_zona_asignada", "geo_zonas", "id_zona"),
        ("tms_envios", "cond_id", "ope_conductores", "cond_id"),
        ("tms_envios", "id_remitente", "cli_remitentes", "id_remitente"),
        ("tms_envios", "id_zona_destino", "geo_zonas", "id_zona"),
        ("gps_rutas", "cond_id", "ope_conductores", "cond_id"),
        ("cal_destinatarios", "id_envio", "tms_envios", "id_envio"),
        ("dir_novedades", "id_envio", "tms_envios", "id_envio"),
    ]
    for child, fk, parent, pk in refs:
        invalid_ids = clean[child].join(clean[parent].select(F.col(pk).alias(fk)), fk, "left_anti")
        errors.append(error_rows(invalid_ids, child, TABLE_KEYS[child], f"FK_INVALIDA_{fk}", F.lit(True)))
        clean[child] = clean[child].join(clean[parent].select(F.col(pk).alias(fk)), fk, "left_semi")

    # 4) Anomalías de negocio en TMS_ENVIOS.
    env = clean["tms_envios"]
    peso_bad = F.col("peso_kg").isNotNull() & (F.col("peso_kg") <= 0)
    fecha_bad = F.col("fec_entrega_real").isNotNull() & (F.to_date("fec_entrega_real") < F.to_date("fec_recepcion"))
    errors.append(error_rows(env, "tms_envios", "id_envio", "PESO_NO_POSITIVO", peso_bad))
    errors.append(error_rows(env, "tms_envios", "id_envio", "FECHA_ENTREGA_ANTERIOR_RECEPCION", fecha_bad))
    clean["tms_envios"] = env.filter(~peso_bad & ~fecha_bad)

    # 5) Nulos no críticos y PII desde Silver.
    clean["ope_conductores"] = (clean["ope_conductores"]
        .withColumn("nomb_cond_hash", F.sha2(F.coalesce(F.col("nomb_cond"), F.lit("")), 256))
        .withColumn("apell_cond_hash", F.sha2(F.coalesce(F.col("apell_cond"), F.lit("")), 256))
        .drop("nomb_cond", "apell_cond")
        .withColumn("calific_promedio_acum_nulo", F.col("calific_promedio_acum").isNull())
        .fillna({"calific_promedio_acum": 0.0}))

    clean["geo_zonas"] = clean["geo_zonas"].fillna({"barrio_referencia": "SIN_DATO"})
    clean["tms_envios"] = (clean["tms_envios"]
        .withColumn("vr_declarado_nulo", F.col("vr_declarado").isNull())
        .fillna({"vr_declarado": 0.0}))
    clean["gps_rutas"] = (clean["gps_rutas"]
        .withColumn("consumo_combustible_nulo", F.col("consumo_combustible").isNull())
        .fillna({"consumo_combustible": 0.0}))
    clean["cal_destinatarios"] = (clean["cal_destinatarios"]
        .withColumn("comentario_hash", F.when(F.col("comentario_texto").isNotNull(), F.sha2("comentario_texto", 256)))
        .drop("comentario_texto"))
    clean["dir_novedades"] = (clean["dir_novedades"]
        .withColumn("desc_novedad_hash", F.when(F.col("desc_novedad").isNotNull(), F.sha2("desc_novedad", 256)))
        .drop("desc_novedad"))

    # 6) Reporte de calidad y escritura Silver.
    for table, df in clean.items():
        total = raw[table].count()
        conformes = df.count()
        null_counts = df.agg(*[F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c) for c in df.columns]).first().asDict()
        null_metrics = {c: null_counts[c] / max(conformes, 1) for c in df.columns}
        report.append((BATCH_ID, table, total, conformes, total - conformes,
                       round(conformes / max(total, 1) * 100, 4),
                       __import__('json').dumps(null_metrics, sort_keys=True), utc_now_iso()))
        write_delta(df, silver_path(table), "silver", table)

    all_errors = reduce(lambda a, b: a.unionByName(b, allowMissingColumns=True), errors)
    # Se conserva el histórico de errores por ejecución.
    append_delta(all_errors, silver_path("errores_pipeline"), "silver", "errores_pipeline")

    report_df = spark.createDataFrame(report,
        "batch_id string, tabla string, registros_origen long, registros_conformes long, registros_rechazados long, porcentaje_conforme double, metricas_nulos_json string, generado_en string") \
        .withColumn("generado_en", F.to_timestamp("generado_en"))
    append_delta(report_df, silver_path("reporte_calidad"), "silver", "reporte_calidad")

    display(report_df)
    payload = {"batch_id": BATCH_ID, "errores": all_errors.count(), "status": "SILVER_OK"}
    print_json(payload)
    return payload


resultado = run_notebook("Procesar_Silver", main)
dbutils.notebook.exit(__import__("json").dumps(resultado, ensure_ascii=False))
