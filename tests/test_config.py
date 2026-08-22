from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "data-generation" / "config.yaml").read_text(encoding="utf-8"))

MINIMOS = {
    "OPE_CONDUCTORES": 500,
    "CLI_REMITENTES": 200,
    "GEO_ZONAS": 300,
    "TMS_ENVIOS": 2_000_000,
    "GPS_RUTAS": 100_000,
    "CAL_DESTINATARIOS": 300_000,
    "DIR_NOVEDADES": 150_000,
}


def test_seed_fijo():
    assert isinstance(CFG["seed"], int)


def test_prod_cumple_volumenes_minimos():
    for tabla, minimo in MINIMOS.items():
        assert CFG["profiles"]["prod"][tabla] >= minimo


def test_dos_formatos():
    assert len(set(CFG["formatos"]) & {"csv", "json", "parquet"}) >= 2


def test_nulos_aproximadamente_cinco_por_ciento():
    assert 0.04 <= float(CFG["porcentaje_nulos"]) <= 0.06


def test_tres_patrones_anomalia():
    assert len(CFG["anomalias"]) >= 3



def test_postgresql_local_compose():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    postgres = compose["services"]["postgres"]
    assert postgres["image"].startswith("postgres:16")
    assert "healthcheck" in postgres
