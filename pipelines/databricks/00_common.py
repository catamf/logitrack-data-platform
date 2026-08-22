# Databricks notebook source
"""Funciones comunes del pipeline LogiTrack."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Callable, TypeVar

from py4j.protocol import Py4JJavaError
from pyspark.sql import DataFrame, functions as F

T = TypeVar("T")


def widget(nombre: str, default: str) -> str:
    """Obtiene un parametro de ADF; crea un valor por defecto para ejecucion manual."""
    try:
        dbutils.widgets.get(nombre)
    except (Py4JJavaError, ValueError, KeyError):
        dbutils.widgets.text(nombre, default)
    value = dbutils.widgets.get(nombre)
    return value if value != "" else default


ENVIRONMENT = widget("environment", "dev")
STORAGE_ACCOUNT = widget("storage_account_name", "CAMBIAR_STORAGE")
CATALOG_NAME = widget("catalog_name", f"logitrack_{ENVIRONMENT}")
USE_UNITY_CATALOG = widget("use_unity_catalog", "true").lower() == "true"
BATCH_ID = widget("batch_id", f"manual-{int(time.time())}")
PIPELINE_START_UTC = widget("pipeline_start_utc", "")


def layer_path(layer: str, table: str | None = None) -> str:
    base = f"abfss://{layer}@{STORAGE_ACCOUNT}.dfs.core.windows.net"
    return f"{base}/{table}" if table else base


def bronze_path(table: str) -> str:
    return layer_path("bronze", table)


def silver_path(table: str) -> str:
    return layer_path("silver", table)


def gold_path(table: str) -> str:
    return layer_path("gold", table)


def table_name(layer: str, table: str) -> str:
    return f"{CATALOG_NAME}.{layer}.{table}"


def path_exists(path: str) -> bool:
    try:
        dbutils.fs.ls(path)
        return True
    except (Py4JJavaError, FileNotFoundError):
        return False


def _is_transient(exc: Exception) -> bool:
    """Distingue errores transitorios para evitar reintentar fallos de logica o esquema."""
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    message = str(exc).lower()
    transient_markers = (
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
        "socket",
        "network",
        "throttl",
        "too many requests",
        "status code: 429",
        "status code: 500",
        "status code: 502",
        "status code: 503",
        "status code: 504",
    )
    return any(marker in message for marker in transient_markers)


def retry_exponential(fn: Callable[[], T], attempts: int = 4, base_seconds: int = 5) -> T:
    """Reintenta solo errores transitorios con esperas 5, 10 y 20 segundos."""
    if attempts < 1:
        raise ValueError("attempts debe ser al menos 1")

    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if not _is_transient(exc) or attempt == attempts - 1:
                raise
            time.sleep(base_seconds * (2 ** attempt))

    raise RuntimeError("Estado inalcanzable en retry_exponential")  # pragma: no cover


def read_parquet(path: str) -> DataFrame:
    return retry_exponential(
        lambda: spark.read.option("recursiveFileLookup", "true").parquet(path)
    )


def read_delta(path: str) -> DataFrame:
    return retry_exponential(lambda: spark.read.format("delta").load(path))


def write_delta(
    df: DataFrame,
    path: str,
    layer: str,
    table: str,
    partition_by: list[str] | None = None,
) -> None:
    """Escribe de forma deterministica y registra la tabla en Unity Catalog."""

    def _write() -> None:
        writer = (
            df.write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
        )
        if partition_by:
            writer = writer.partitionBy(*partition_by)
        writer.save(path)

    retry_exponential(_write)
    if USE_UNITY_CATALOG:
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {table_name(layer, table)} "
            f"USING DELTA LOCATION '{path}'"
        )
        spark.sql(f"REFRESH TABLE {table_name(layer, table)}")


def append_delta(df: DataFrame, path: str, layer: str, table: str) -> None:
    def _append() -> None:
        (
            df.write.format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .save(path)
        )

    retry_exponential(_append)
    if USE_UNITY_CATALOG:
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {table_name(layer, table)} "
            f"USING DELTA LOCATION '{path}'"
        )


def log_operational_error(task_name: str, exc: Exception) -> None:
    """Registra una excepcion operacional sin ocultar la excepcion original."""
    payload = {
        "tipo": type(exc).__name__,
        "mensaje": str(exc)[:4000],
        "tarea": task_name,
    }
    row = spark.createDataFrame(
        [(
            BATCH_ID,
            task_name,
            "EXCEPCION_OPERACIONAL",
            json.dumps(payload, ensure_ascii=False),
            utc_now_iso(),
        )],
        "batch_id string, tarea string, regla string, payload_json string, fecha_error string",
    ).select(
        F.expr("uuid()").alias("error_id"),
        "batch_id",
        F.lit("_pipeline").alias("tabla"),
        F.col("tarea").alias("clave_registro"),
        "regla",
        "payload_json",
        F.to_timestamp("fecha_error").alias("fecha_error"),
    )

    try:
        append_delta(row, silver_path("errores_pipeline"), "silver", "errores_pipeline")
    except Exception as logging_exc:
        # El registro de error no debe ocultar el fallo original si el storage tambien esta caido.
        print_json({
            "status": "ERROR_LOGGING_FAILED",
            "task": task_name,
            "original_error": str(exc),
            "logging_error": str(logging_exc),
        })


def run_notebook(task_name: str, fn: Callable[[], T]) -> T:
    """Ejecuta la logica de un notebook y registra excepciones operacionales."""
    try:
        return fn()
    except Exception as exc:
        log_operational_error(task_name, exc)
        raise


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
