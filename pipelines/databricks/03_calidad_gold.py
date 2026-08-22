# Databricks notebook source
# MAGIC %run ./00_common

from pyspark.sql import functions as F



def main():
    fact = read_delta(gold_path("fact_envios"))
    dim_cond = read_delta(gold_path("dim_conductores"))

    checks = []

    def add_check(regla: str, fallos: int, detalle: str):
        checks.append((BATCH_ID, regla, "PASS" if fallos == 0 else "FAIL", int(fallos), detalle, utc_now_iso()))

    add_check("DQ01_ID_ENVIO_NO_NULO", fact.filter(F.col("id_envio").isNull()).count(), "id_envio debe existir")
    add_check("DQ02_ID_ENVIO_UNICO", fact.groupBy("id_envio").count().filter("count > 1").count(), "id_envio no debe duplicarse")
    add_check("DQ03_CONDUCTOR_EXISTE", fact.join(dim_cond.select("cond_id"), "cond_id", "left_anti").count(), "cond_id debe existir en dim_conductores")
    add_check("DQ04_PESO_POSITIVO", fact.filter(F.col("peso_kg").isNotNull() & (F.col("peso_kg") <= 0)).count(), "peso_kg > 0")
    add_check("DQ05_FECHA_COHERENTE", fact.filter(F.col("fec_entrega_real").isNotNull() & (F.to_date("fec_entrega_real") < F.to_date("fec_recepcion"))).count(), "entrega >= recepcion")

    result = spark.createDataFrame(checks, "batch_id string, regla string, estado string, fallos long, detalle string, ejecutado_en string") \
                  .withColumn("ejecutado_en", F.to_timestamp("ejecutado_en"))
    append_delta(result, gold_path("resultados_calidad"), "gold", "resultados_calidad")
    display(result)

    failed = result.filter("estado = 'FAIL'").count()
    if failed:
        raise RuntimeError(f"CALIDAD_GOLD_FAIL: {failed} reglas fallaron")
    payload = {"batch_id": BATCH_ID, "status": "QUALITY_OK", "checks": len(checks)}
    print_json(payload)
    return payload


resultado = run_notebook("Calidad_Gold", main)
dbutils.notebook.exit(__import__("json").dumps(resultado, ensure_ascii=False))
