# Databricks notebook source
# MAGIC %run ./00_common

from pyspark.sql import functions as F, Window



def main():
    cond = read_delta(silver_path("ope_conductores"))
    rem = read_delta(silver_path("cli_remitentes"))
    zon = read_delta(silver_path("geo_zonas"))
    env = read_delta(silver_path("tms_envios"))
    rutas = read_delta(silver_path("gps_rutas"))
    cal = read_delta(silver_path("cal_destinatarios"))
    nov = read_delta(silver_path("dir_novedades"))

    # --- Dimensiones ---
    dim_conductores = (cond
        .withColumn("antiguedad_anios", F.round(F.months_between(F.current_date(), F.to_date("fec_ingreso")) / 12, 2))
        .withColumn("tip_vehiculo", F.when(F.lower("tip_vehiculo").contains("moto"), "Moto")
            .when(F.lower("tip_vehiculo").contains("bici"), "Bicicleta")
            .when(F.lower("tip_vehiculo").contains("van"), "Van")
            .otherwise("Camion"))
        .select("cond_id", "nomb_cond_hash", "apell_cond_hash", "num_doc_hash", "fec_ingreso",
                "antiguedad_anios", "id_ciudad_base", "tip_vehiculo", "cod_zona_asignada",
                "activo", "calific_promedio_acum"))
    write_delta(dim_conductores, gold_path("dim_conductores"), "gold", "dim_conductores")

    dim_remitentes = (rem
        .withColumn("segmento_industria", F.when(F.lower("tipo_cliente").contains("ecommerce"), "Ecommerce")
            .when(F.lower("tipo_cliente").contains("farm"), "Farmaceutico")
            .when(F.lower("tipo_cliente").contains("retail"), "Retail")
            .when(F.lower("tipo_cliente").contains("telecom"), "Telecomunicaciones")
            .otherwise("Otro"))
        .withColumn("sla_entrega_horas", F.col("sla_entrega_horas").cast("double")))
    write_delta(dim_remitentes, gold_path("dim_remitentes"), "gold", "dim_remitentes")

    city_map = F.create_map(*sum([[F.lit(k), F.lit(v)] for k, v in {
        "BOG":"Bogota","MED":"Medellin","CAL":"Cali","BAQ":"Barranquilla","BGA":"Bucaramanga",
        "PEI":"Pereira","MZL":"Manizales","CTG":"Cartagena","SMR":"Santa Marta","CUC":"Cucuta"}.items()], []))
    dim_zonas = (zon
        .withColumn("indice_dificultad_operativa",
            F.round(1 + 4 * (0.6 * ((F.col("nivel_trafico_prom") - 1) / 4) +
                                0.4 * (F.least(F.col("distancia_bodega_km"), F.lit(40.0)) / 40.0)), 0).cast("int"))
        .withColumn("municipio", city_map[F.col("id_ciudad")]))
    write_delta(dim_zonas, gold_path("dim_zonas"), "gold", "dim_zonas")

    # --- Fact de envíos ---
    # Supuesto documentado: fec_entrega_programada no trae hora; se interpreta como fin del día (23:59:59).
    recepcion_ts = F.to_timestamp(F.concat_ws(" ", F.col("e.fec_recepcion"), F.col("e.hra_recepcion")))
    int1_ts = F.to_timestamp(F.concat_ws(" ", F.col("e.fec_intento1"), F.col("e.hra_intento1")))
    int2_ts = F.to_timestamp(F.concat_ws(" ", F.col("e.fec_intento2"), F.col("e.hra_intento2")))
    entrega_ts = F.when(F.col("e.resultado_intento2") == "Entregado", int2_ts) \
                  .when(F.col("e.resultado_intento1") == "Entregado", int1_ts) \
                  .otherwise(F.to_timestamp(F.col("e.fec_entrega_real")))
    programada_ts = F.to_timestamp(F.concat_ws(" ", F.col("e.fec_entrega_programada"), F.lit("23:59:59")))

    motivo_map = F.create_map(
        F.lit("DEST_AUSENTE"), F.lit("Destinatario ausente"),
        F.lit("DIR_INCORRECTA"), F.lit("Direccion incorrecta"),
        F.lit("ZONA_DIFICIL"), F.lit("Zona de dificil acceso"),
        F.lit("RECHAZADO"), F.lit("Paquete rechazado"),
        F.lit("OTRO"), F.lit("Otro"),
    )

    fact_envios = (env.alias("e")
        .join(rem.select("id_remitente", "sla_entrega_horas", "penalidad_porc").alias("r"), "id_remitente", "left")
        .withColumn("recepcion_ts", recepcion_ts)
        .withColumn("entrega_real_ts", entrega_ts)
        .withColumn("entrega_programada_ts", programada_ts)
        .withColumn("tiempo_entrega_real_horas",
            F.when(F.col("entrega_real_ts").isNotNull(),
                   (F.col("entrega_real_ts").cast("long") - F.col("recepcion_ts").cast("long")) / 3600.0))
        .withColumn("cumplimiento_sla",
            (F.col("estado_final") == "Entregado") & (F.col("tiempo_entrega_real_horas") <= F.col("sla_entrega_horas")))
        .withColumn("motivo_fallo_desc", motivo_map[F.col("motivo_fallo_cod")])
        .withColumn("numero_intentos", F.when(F.col("fec_intento2").isNotNull(), 2).otherwise(1))
        .withColumn("retraso_horas",
            F.when(F.col("entrega_real_ts").isNotNull(),
                   (F.col("entrega_real_ts").cast("long") - F.col("entrega_programada_ts").cast("long")) / 3600.0))
        .withColumn("clasificacion_retraso",
            F.when(F.col("estado_final") != "Entregado", "No entregado")
             .when(F.col("retraso_horas") <= 0, "A tiempo")
             .when(F.col("retraso_horas") <= 4, "Retraso leve")
             .when(F.col("retraso_horas") <= 24, "Retraso moderado")
             .otherwise("Retraso critico"))
        .withColumn("penalidad_estimada",
            F.when(~F.col("cumplimiento_sla"), F.col("vr_declarado") * F.col("penalidad_porc")).otherwise(F.lit(0.0)))
        .withColumn("anio_recepcion", F.year("fec_recepcion"))
        .withColumn("mes_recepcion", F.month("fec_recepcion")))
    write_delta(fact_envios, gold_path("fact_envios"), "gold", "fact_envios", ["anio_recepcion", "mes_recepcion"])

    # --- Fact rutas ---
    start_ts = F.to_timestamp(F.concat_ws(" ", F.col("fec_ruta"), F.col("hra_inicio")))
    end_ts = F.to_timestamp(F.concat_ws(" ", F.col("fec_ruta"), F.col("hra_fin")))
    fact_rutas = (rutas
        .withColumn("horas_trabajadas", F.greatest((end_ts.cast("long") - start_ts.cast("long")) / 3600.0, F.lit(0.1)))
        .withColumn("eficiencia_ruta", F.when(F.col("num_paradas_plan") > 0, F.col("num_paradas_real") / F.col("num_paradas_plan")))
        .withColumn("velocidad_promedio_kmh", F.col("km_recorridos") / F.col("horas_trabajadas"))
        .withColumn("desviacion_porc", F.when(F.col("km_recorridos") > 0, F.col("desviacion_ruta_km") / F.col("km_recorridos") * 100))
        .withColumn("anio_ruta", F.year("fec_ruta"))
        .withColumn("mes_ruta", F.month("fec_ruta")))
    write_delta(fact_rutas, gold_path("fact_rutas"), "gold", "fact_rutas", ["anio_ruta", "mes_ruta"])

    # --- Desempeño conductor ---
    env_day = (fact_envios
        .withColumn("fecha", F.to_date("fec_recepcion"))
        .groupBy("cond_id", "fecha")
        .agg(F.avg(F.when(F.col("estado_final") == "Entregado", 1.0).otherwise(0.0)).alias("tasa_exito"),
             F.avg("numero_intentos").alias("intentos_promedio"),
             F.first("id_zona_destino").alias("zona_referencia"),
             F.sum("penalidad_estimada").alias("penalidad_estimada_total")))
    route_day = (fact_rutas.groupBy("cond_id", F.col("fec_ruta").alias("fecha"))
        .agg(F.avg("desviacion_porc").alias("desviacion_promedio_porc"),
             F.avg("velocidad_promedio_kmh").alias("velocidad_promedio_kmh")))
    rating_day = (cal.join(fact_envios.select("id_envio", "cond_id", "fec_recepcion"), "id_envio", "inner")
        .groupBy("cond_id", F.to_date("fec_recepcion").alias("fecha"))
        .agg(F.avg("puntaje_1_5").alias("calificacion_promedio")))
    perf = (env_day.join(route_day, ["cond_id", "fecha"], "left")
            .join(rating_day, ["cond_id", "fecha"], "left")
            .join(dim_zonas.select(F.col("id_zona").alias("zona_referencia"), "indice_dificultad_operativa"), "zona_referencia", "left")
            .fillna({"desviacion_promedio_porc": 100.0, "velocidad_promedio_kmh": 0.0, "calificacion_promedio": 0.0,
                     "indice_dificultad_operativa": 3}))
    perf = (perf
        .withColumn("adherencia_ruta_normalizada", F.greatest(F.lit(0.0), F.lit(1.0) - F.least(F.col("desviacion_promedio_porc") / 100.0, F.lit(1.0))))
        .withColumn("velocidad_estandar_zona", F.when(F.col("indice_dificultad_operativa") >= 4, 18.0).when(F.col("indice_dificultad_operativa") == 3, 24.0).otherwise(30.0))
        .withColumn("velocidad_vs_estandar_zona", F.least(F.col("velocidad_promedio_kmh") / F.col("velocidad_estandar_zona"), F.lit(1.0)))
        .withColumn("inversa_intentos_promedio", F.least(F.lit(1.0) / F.greatest(F.col("intentos_promedio"), F.lit(1.0)), F.lit(1.0)))
        .withColumn("calificacion_destinatario_normalizada", F.least(F.col("calificacion_promedio") / 5.0, F.lit(1.0)))
        .withColumn("score_desempeno", F.round(
            F.col("tasa_exito") * 0.35 +
            F.col("adherencia_ruta_normalizada") * 0.20 +
            F.col("velocidad_vs_estandar_zona") * 0.20 +
            F.col("inversa_intentos_promedio") * 0.15 +
            F.col("calificacion_destinatario_normalizada") * 0.10, 2))
        .withColumn("anio", F.year("fecha"))
        .withColumn("mes", F.month("fecha")))
    write_delta(perf, gold_path("fact_desempeno_conductor"), "gold", "fact_desempeno_conductor", ["anio", "mes"])

    # --- Trazabilidad completa por envío ---
    reception_events = env.select("id_envio", F.to_timestamp(F.concat_ws(" ", "fec_recepcion", "hra_recepcion")).alias("evento_ts"), F.lit("Recepcion").alias("evento"))
    int1_events = env.filter(F.col("fec_intento1").isNotNull()).select("id_envio", F.to_timestamp(F.concat_ws(" ", "fec_intento1", "hra_intento1")).alias("evento_ts"), F.lit("Intento 1").alias("evento"))
    int2_events = env.filter(F.col("fec_intento2").isNotNull()).select("id_envio", F.to_timestamp(F.concat_ws(" ", "fec_intento2", "hra_intento2")).alias("evento_ts"), F.lit("Intento 2").alias("evento"))
    delivery_events = fact_envios.filter(F.col("entrega_real_ts").isNotNull()).select("id_envio", F.col("entrega_real_ts").alias("evento_ts"), F.lit("Entrega").alias("evento"))
    nov_events = (nov.join(env.select("id_envio", "fec_recepcion"), "id_envio", "inner")
        .filter(F.to_date("fec_novedad") >= F.to_date("fec_recepcion"))
        .select("id_envio", F.to_timestamp("fec_novedad").alias("evento_ts"),
                F.concat(F.lit("Novedad: "), F.col("tip_novedad")).alias("evento")))
    events = reception_events.unionByName(int1_events).unionByName(int2_events).unionByName(delivery_events).unionByName(nov_events)
    w_event = Window.partitionBy("id_envio").orderBy("evento_ts", "evento")
    traza = (events
        .withColumn("orden_evento", F.row_number().over(w_event))
        .withColumn("evento_anterior_ts", F.lag("evento_ts").over(w_event))
        .withColumn("horas_desde_evento_anterior", (F.col("evento_ts").cast("long") - F.col("evento_anterior_ts").cast("long")) / 3600.0)
        .withColumn("anio_evento", F.year("evento_ts"))
        .withColumn("mes_evento", F.month("evento_ts")))
    write_delta(traza, gold_path("fact_trazabilidad_envio"), "gold", "fact_trazabilidad_envio", ["anio_evento", "mes_evento"])

    # --- Alertas de zona: mismo día de semana, 4 observaciones previas ---
    zone_daily = (fact_envios
        .withColumn("fecha", F.to_date("fec_recepcion"))
        .groupBy("id_zona_destino", "fecha")
        .agg(F.avg(F.when(F.col("estado_final") != "Entregado", 1.0).otherwise(0.0)).alias("tasa_fallo_actual"))
        .withColumn("dia_semana", F.dayofweek("fecha")))
    w_zone = Window.partitionBy("id_zona_destino", "dia_semana").orderBy("fecha").rowsBetween(-4, -1)
    alertas = (zone_daily
        .withColumn("promedio_historico_4", F.avg("tasa_fallo_actual").over(w_zone))
        .withColumn("porcentaje_desviacion", F.when(F.col("promedio_historico_4") > 0,
            (F.col("tasa_fallo_actual") - F.col("promedio_historico_4")) / F.col("promedio_historico_4") * 100))
        .filter(F.col("promedio_historico_4").isNotNull() & (F.col("tasa_fallo_actual") > F.col("promedio_historico_4") * 1.25))
        .withColumn("anio", F.year("fecha"))
        .withColumn("mes", F.month("fecha")))
    write_delta(alertas, gold_path("fact_alertas_zona"), "gold", "fact_alertas_zona", ["anio", "mes"])

    # --- Tres agregaciones y KPI ejecutivo ---
    agg_zona = (fact_envios.groupBy(F.to_date("fec_recepcion").alias("fecha"), "id_zona_destino")
        .agg(F.count("*").alias("envios"), F.avg(F.col("cumplimiento_sla").cast("double")).alias("tasa_cumplimiento_sla"),
             F.avg(F.when(F.col("estado_final") == "Entregado", 1.0).otherwise(0.0)).alias("tasa_exito"),
             F.sum("penalidad_estimada").alias("penalidad_estimada")))
    write_delta(agg_zona, gold_path("agg_desempeno_zona"), "gold", "agg_desempeno_zona")

    agg_rem = (fact_envios.groupBy(F.to_date("fec_recepcion").alias("fecha"), "id_remitente")
        .agg(F.count("*").alias("envios"),
             F.avg(F.col("cumplimiento_sla").cast("double")).alias("tasa_cumplimiento_sla"),
             F.avg(F.when(F.col("estado_final") == "Entregado", 1.0).otherwise(0.0)).alias("tasa_exito"),
             F.sum("penalidad_estimada").alias("penalidad_estimada")))
    write_delta(agg_rem, gold_path("agg_sla_remitente"), "gold", "agg_sla_remitente")

    agg_pkg = (fact_envios.groupBy(F.to_date("fec_recepcion").alias("fecha"), "tip_paquete")
        .agg(F.count("*").alias("envios"), F.avg(F.when(F.col("estado_final") == "Entregado", 1.0).otherwise(0.0)).alias("tasa_exito"),
             F.avg("tiempo_entrega_real_horas").alias("tiempo_promedio_horas"),
             F.sum("penalidad_estimada").alias("penalidad_estimada")))
    write_delta(agg_pkg, gold_path("agg_tipo_paquete"), "gold", "agg_tipo_paquete")

    kpi = (fact_envios.groupBy(F.to_date("fec_recepcion").alias("fecha"))
        .agg(F.count("*").alias("total_envios"),
             F.sum(F.when(F.col("estado_final") == "Entregado", 1).otherwise(0)).alias("envios_entregados"),
             F.avg(F.when(F.col("estado_final") == "Entregado", 1.0).otherwise(0.0)).alias("tasa_exito"),
             F.avg(F.col("cumplimiento_sla").cast("double")).alias("tasa_cumplimiento_sla"),
             F.avg("tiempo_entrega_real_horas").alias("tiempo_promedio_entrega_horas"),
             F.sum("penalidad_estimada").alias("penalidad_estimada_total")))
    write_delta(kpi, gold_path("kpi_logistica_diaria"), "gold", "kpi_logistica_diaria")

    payload = {"batch_id": BATCH_ID, "status": "GOLD_OK", "facts": 5, "dimensions": 3, "aggregates": 3, "kpi": 1}
    print_json(payload)
    return payload


resultado = run_notebook("Procesar_Gold", main)
dbutils.notebook.exit(__import__("json").dumps(resultado, ensure_ascii=False))
