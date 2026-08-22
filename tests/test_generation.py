import importlib.util
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "data-generation" / "generar_datos.py"
spec = importlib.util.spec_from_file_location("generar_datos", MOD_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def contexto(seed=42):
    cfg = mod.cargar_config(ROOT / "data-generation" / "config.yaml")
    cfg = dict(cfg)
    cfg["seed"] = seed
    fechas, pesos = mod._fechas_contexto(cfg)
    return mod.Contexto(cfg, "dev", Path("/tmp/no_write"), np.random.default_rng(seed), fechas, pesos)


def test_generacion_reproducible_zonas():
    a = mod.generar_zonas(contexto(42), 20)
    b = mod.generar_zonas(contexto(42), 20)
    pd.testing.assert_frame_equal(a, b)


def test_integridad_referencial_envios():
    ctx = contexto(42)
    zonas = mod.generar_zonas(ctx, 30)
    conductores = mod.generar_conductores(ctx, 40, zonas)
    remitentes = mod.generar_remitentes(ctx, 20)
    envios = mod._envios_bloque(ctx, 0, 1000, conductores, remitentes, zonas)
    assert envios["cond_id"].isin(conductores["cond_id"]).all()
    assert envios["id_remitente"].isin(remitentes["id_remitente"]).all()
    assert envios["id_zona_destino"].isin(zonas["id_zona"]).all()


def test_anomalias_controladas_en_envios():
    ctx = contexto(42)
    zonas = mod.generar_zonas(ctx, 30)
    conductores = mod.generar_conductores(ctx, 40, zonas)
    remitentes = mod.generar_remitentes(ctx, 20)
    envios = mod._envios_bloque(ctx, 0, 5000, conductores, remitentes, zonas)
    assert (envios["peso_kg"] <= 0).sum() >= 1
    entrega = pd.to_datetime(envios["fec_entrega_real"], errors="coerce")
    recepcion = pd.to_datetime(envios["fec_recepcion"], errors="coerce")
    assert (entrega < recepcion).sum() >= 1


def test_escritor_parquet_mantiene_schema_entre_bloques(tmp_path):
    escritor = mod.EscritorPorBloques(
        "test_schema",
        tmp_path,
        ["parquet"],
    )

    primer_bloque = pd.DataFrame({
        "id": ["1", "2"],
        "motivo": ["DEST_AUSENTE", None],
    })

    segundo_bloque = pd.DataFrame({
        "id": ["3"],
        "motivo": [None],
    })

    try:
        escritor.escribir(primer_bloque)
        escritor.escribir(segundo_bloque)
    finally:
        escritor.cerrar()

    resultado = pd.read_parquet(
        tmp_path / "test_schema.parquet"
    )

    assert len(resultado) == 3
    assert list(resultado["id"]) == ["1", "2", "3"]


def test_escritor_csv_anexa_bloques_sin_sobrescribir(tmp_path):
    escritor = mod.EscritorPorBloques(
        "test_csv",
        tmp_path,
        ["csv"],
    )

    escritor.escribir(
        pd.DataFrame({
            "id": ["1", "2"],
        })
    )
    escritor.escribir(
        pd.DataFrame({
            "id": ["3"],
        })
    )

    resultado = pd.read_csv(
        tmp_path / "test_csv.csv",
        dtype={"id": str},
    )

    assert len(resultado) == 3
    assert list(resultado["id"]) == ["1", "2", "3"]
