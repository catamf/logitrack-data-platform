# Databricks notebook source
# MAGIC %run ./00_common

from datetime import datetime, timezone
from pyspark.sql import functions as F


def main() -> str:
    summary_rows = []
    layers = {
        "silver": [
            "ope_conductores", "cli_remitentes", "geo_zonas", "tms_envios",
            "gps_rutas", "cal_destinatarios", "dir_novedades",
        ],
        "gold": [
            "dim_conductores", "dim_remitentes", "dim_zonas", "fact_envios",
            "fact_rutas", "fact_desempeno_conductor", "fact_trazabilidad_envio",
            "fact_alertas_zona",
        ],
    }

    for layer, tables in layers.items():
        for table in tables:
            path = silver_path(table) if layer == "silver" else gold_path(table)
            summary_rows.append((layer, table, read_delta(path).count()))

    rejected = (
        read_delta(silver_path("errores_pipeline"))
        .filter(F.col("batch_id") == BATCH_ID)
        .count()
    )
    quality = read_delta(gold_path("resultados_calidad")).filter(
        F.col("batch_id") == BATCH_ID
    )
    quality_failures = quality.filter("estado = 'FAIL'").count()

    now_utc = datetime.now(timezone.utc)
    duracion_total_segundos = None
    if PIPELINE_START_UTC:
        try:
            inicio = datetime.fromisoformat(PIPELINE_START_UTC.replace("Z", "+00:00"))
            duracion_total_segundos = round((now_utc - inicio).total_seconds(), 3)
        except ValueError:
            duracion_total_segundos = None

    totals = {
        layer: sum(n for row_layer, _, n in summary_rows if row_layer == layer)
        for layer in layers
    }
    payload = {
        "batch_id": BATCH_ID,
        "status": "SUCCESS",
        "registros_por_capa": totals,
        "registros_por_tabla": {f"{l}.{t}": n for l, t, n in summary_rows},
        "registros_rechazados": rejected,
        "alertas_calidad": quality_failures,
        "duracion_total_segundos": duracion_total_segundos,
        "finalizado_en": utc_now_iso(),
    }

    row = spark.createDataFrame(
        [(
            BATCH_ID,
            __import__("json").dumps(payload, ensure_ascii=False),
            totals["silver"],
            totals["gold"],
            rejected,
            quality_failures,
            duracion_total_segundos,
            utc_now_iso(),
        )],
        "batch_id string, resumen_json string, registros_silver long, registros_gold long, "
        "registros_rechazados long, alertas_calidad long, duracion_total_segundos double, "
        "finalizado_en string",
    ).withColumn("finalizado_en", F.to_timestamp("finalizado_en"))
    append_delta(row, gold_path("resumen_ejecuciones"), "gold", "resumen_ejecuciones")

    print_json(payload)
    return (
        f"RESUMEN_DIARIO | batch_id={BATCH_ID} | "
        f"silver={totals['silver']} | gold={totals['gold']} | "
        f"rechazados={rejected} | alertas_calidad={quality_failures} | "
        f"duracion_segundos={duracion_total_segundos}"
    )


resultado = run_notebook("Resumen_Ejecucion", main)
print(resultado)
dbutils.notebook.exit(resultado)
