# Databricks notebook source
# MAGIC %run ./00_common

# COMMAND ----------

from pyspark.sql import Window, functions as F

FORCE_VOLUME_ALERT = widget("force_volume_alert", "false").lower() == "true"
TABLES = [
    "ope_conductores", "cli_remitentes", "geo_zonas", "tms_envios",
    "gps_rutas", "cal_destinatarios", "dir_novedades",
]


def main() -> str:
    # ADF registra una fila por tabla en PostgreSQL y copia ese control a Bronze.
    # La validacion usa el volumen de la ejecucion y no el acumulado fisico del lake.
    control = read_parquet(bronze_path("_control/log_ingesta"))
    current = (
        control.filter(F.col("batch_id") == BATCH_ID)
        .select(
            "batch_id",
            "tabla",
            F.col("registros_procesados").cast("long").alias("registros"),
            F.col("bytes_escritos").cast("long").alias("bytes"),
            F.col("duracion_segundos").cast("double").alias("duracion_segundos"),
            F.current_timestamp().alias("auditado_en"),
        )
    )

    if current.count() != len(TABLES):
        raise RuntimeError(
            f"AUDITORIA_BRONZE_INCOMPLETA: se esperaban {len(TABLES)} registros de control para {BATCH_ID}"
        )

    append_delta(current, silver_path("auditoria_ingesta"), "silver", "auditoria_ingesta")

    # Promedio de hasta las ultimas siete ejecuciones previas por tabla.
    hist = read_delta(silver_path("auditoria_ingesta"))
    prev = (
        hist.filter(F.col("batch_id") != BATCH_ID)
        .withColumn(
            "rn",
            F.row_number().over(
                Window.partitionBy("tabla").orderBy(F.col("auditado_en").desc())
            ),
        )
        .filter(F.col("rn") <= 7)
        .groupBy("tabla")
        .agg(F.avg("registros").alias("promedio_7"))
    )

    checks = (
        current.join(prev, "tabla", "left")
        .withColumn(
            "desviacion_porc",
            F.when(
                F.col("promedio_7") > 0,
                F.abs(F.col("registros") - F.col("promedio_7"))
                / F.col("promedio_7")
                * 100,
            ).otherwise(F.lit(0.0)),
        )
        .withColumn("es_alerta", F.col("desviacion_porc") > 30)
    )

    if FORCE_VOLUME_ALERT:
        alertas = (
            current.limit(1)
            .withColumn(
                "promedio_7",
                F.when(F.col("registros") > 0, F.col("registros") / 2.0).otherwise(F.lit(1.0)),
            )
            .withColumn("desviacion_porc", F.lit(100.0))
            .withColumn("es_alerta", F.lit(True))
            .withColumn("tipo_alerta", F.lit("PRUEBA_CONTROLADA"))
        )
    else:
        alertas = checks.filter("es_alerta").withColumn(
            "tipo_alerta", F.lit("ANOMALIA_VOLUMEN")
        )

    if alertas.limit(1).count() > 0:
        append_delta(alertas, silver_path("alertas_volumen"), "silver", "alertas_volumen")
        display(alertas)
        detalles = [
            f"{row['tabla']}:{round(float(row['desviacion_porc']), 2)}%"
            for row in alertas.select("tabla", "desviacion_porc").collect()
        ]
        return (
            f"VOLUME_ALERT | batch_id={BATCH_ID} | "
            f"tablas={','.join(detalles)} | umbral=30%"
        )

    display(current.orderBy("tabla"))
    return f"BRONZE_OK | batch_id={BATCH_ID} | tablas={len(TABLES)}"


resultado = run_notebook("Auditar_Bronze", main)
print(resultado)
dbutils.notebook.exit(resultado)
