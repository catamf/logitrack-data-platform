"""Generador reproducible de datos sintéticos para el escenario LogiTrack.

Objetivos del diseño:
- respetar nombres y campos de las siete tablas fuente;
- producir distribuciones plausibles y al menos doce meses de histórico;
- mantener integridad referencial en los registros base;
- introducir nulos controlados y tres patrones de anomalía documentados;
- soportar volúmenes de producción sin cargar 2 millones de envíos en memoria.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from datetime import timedelta

import numpy as np
import pandas as pd
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    pa = None
    pq = None
import yaml

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"

NOMBRES = [
    "Andrea", "Carlos", "Diana", "Felipe", "Gabriela", "Jorge", "Laura",
    "Mateo", "Natalia", "Oscar", "Paula", "Ricardo", "Sandra", "Tomas",
    "Valentina", "Camilo", "Juliana", "Santiago", "Mariana", "Daniel",
]
APELLIDOS = [
    "Gomez", "Rodriguez", "Martinez", "Lopez", "Hernandez", "Garcia",
    "Ramirez", "Torres", "Diaz", "Moreno", "Rojas", "Castro", "Vargas",
    "Ortiz", "Silva", "Ruiz", "Mendoza", "Perez", "Sanchez", "Reyes",
]


@dataclass(frozen=True)
class Contexto:
    cfg: dict
    profile: str
    out_dir: Path
    rng: np.random.Generator
    fechas: pd.DatetimeIndex
    pesos_fecha: np.ndarray


def cargar_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _ids(prefijo: str, cantidad: int, ancho: int = 7) -> np.ndarray:
    return np.array([f"{prefijo}{i:0{ancho}d}" for i in range(1, cantidad + 1)], dtype=object)


def _fechas_contexto(cfg: dict) -> tuple[pd.DatetimeIndex, np.ndarray]:
    fechas = pd.date_range(cfg["fecha_inicio"], cfg["fecha_fin"], freq="D")
    if len(fechas) < 365:
        raise ValueError("El rango temporal debe cubrir al menos 365 dias.")
    # Noviembre/diciembre tienen picos fuertes; fines de semana bajan ligeramente.
    pesos = np.ones(len(fechas), dtype=float)
    meses = fechas.month.to_numpy()
    pesos[np.isin(meses, [11, 12])] *= 2.2
    pesos[fechas.dayofweek.to_numpy() >= 5] *= 0.75
    pesos /= pesos.sum()
    return fechas, pesos


def _muestra_fechas(ctx: Contexto, n: int) -> pd.DatetimeIndex:
    idx = ctx.rng.choice(len(ctx.fechas), size=n, replace=True, p=ctx.pesos_fecha)
    return ctx.fechas[idx]


def _aplicar_nulos(df: pd.DataFrame, columnas: Iterable[str], pct: float, rng: np.random.Generator) -> None:
    for columna in columnas:
        if columna not in df.columns or len(df) == 0:
            continue
        n = max(1, int(round(len(df) * pct)))
        indices = rng.choice(df.index.to_numpy(), size=min(n, len(df)), replace=False)
        df.loc[indices, columna] = pd.NA


def _escribir_tabla(df: pd.DataFrame, nombre: str, out_dir: Path, formatos: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if "csv" in formatos:
        df.to_csv(out_dir / f"{nombre}.csv", index=False)
    if "parquet" in formatos:
        if pa is None:
            raise RuntimeError("Parquet requiere pyarrow. Ejecuta: poetry install")
        df.to_parquet(out_dir / f"{nombre}.parquet", index=False, engine="pyarrow")


class EscritorPorBloques:
    def __init__(self, nombre: str, out_dir: Path, formatos: list[str]) -> None:
        self.nombre = nombre
        self.out_dir = out_dir
        self.formatos = formatos
        self.csv_path = out_dir / f"{nombre}.csv"
        self.parquet_path = out_dir / f"{nombre}.parquet"
        self.writer = None
        self.parquet_schema = None
        self.primero = True
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.csv_path.exists():
            self.csv_path.unlink()
        if self.parquet_path.exists():
            self.parquet_path.unlink()

    def escribir(self, df: pd.DataFrame) -> None:
        if "csv" in self.formatos:
            df.to_csv(
                self.csv_path,
                index=False,
                mode="w" if self.primero else "a",
                header=self.primero,
            )

        if "parquet" in self.formatos:
            if pa is None or pq is None:
                raise RuntimeError(
                    "Parquet requiere pyarrow. Ejecuta: poetry install"
                )

            if self.parquet_schema is None:
                table = pa.Table.from_pandas(
                    df,
                    preserve_index=False,
                )
                self.parquet_schema = table.schema
                self.writer = pq.ParquetWriter(
                    self.parquet_path,
                    self.parquet_schema,
                    compression="snappy",
                )
            else:
                table = pa.Table.from_pandas(
                    df,
                    schema=self.parquet_schema,
                    preserve_index=False,
                )

            self.writer.write_table(table)

        self.primero = False

    def cerrar(self) -> None:
        if self.writer is not None:
            self.writer.close()


def generar_zonas(ctx: Contexto, n: int) -> pd.DataFrame:
    ciudades = ctx.cfg["ciudades"]
    city_ids = np.array([c["id"] for c in ciudades], dtype=object)
    city_names = {c["id"]: c["nombre"] for c in ciudades}
    id_ciudad = ctx.rng.choice(city_ids, size=n)
    trafico = np.clip(ctx.rng.normal(3.1, 1.0, size=n), 1, 5).round(1)
    distancia = np.clip(ctx.rng.gamma(shape=2.0, scale=4.5, size=n), 0.5, 45).round(2)
    tip_zona = np.where(distancia > 20, "Periferica", np.where(trafico > 3.8, "Urbana_densa", "Urbana"))
    lat_base = {"BOG": 4.65, "MED": 6.24, "CAL": 3.45, "BAQ": 10.98, "BGA": 7.12,
                "PEI": 4.81, "MZL": 5.07, "CTG": 10.40, "SMR": 11.24, "CUC": 7.89}
    lon_base = {"BOG": -74.08, "MED": -75.58, "CAL": -76.53, "BAQ": -74.80, "BGA": -73.12,
                "PEI": -75.69, "MZL": -75.52, "CTG": -75.51, "SMR": -74.20, "CUC": -72.50}
    df = pd.DataFrame({
        "id_zona": _ids("ZON", n, 4),
        "nom_zona": [f"Zona {city_names[c]} {i+1:03d}" for i, c in enumerate(id_ciudad)],
        "id_ciudad": id_ciudad,
        "barrio_referencia": [f"Sector {i % 35 + 1}" for i in range(n)],
        "latitud_centroide": [round(lat_base[c] + ctx.rng.normal(0, 0.08), 6) for c in id_ciudad],
        "longitud_centroide": [round(lon_base[c] + ctx.rng.normal(0, 0.08), 6) for c in id_ciudad],
        "nivel_trafico_prom": trafico,
        "tip_zona": tip_zona,
        "distancia_bodega_km": distancia,
    })
    _aplicar_nulos(df, ["barrio_referencia"], ctx.cfg["porcentaje_nulos"], ctx.rng)
    return df


def generar_conductores(ctx: Contexto, n: int, zonas: pd.DataFrame) -> pd.DataFrame:
    fechas_ingreso = pd.to_datetime(ctx.rng.choice(pd.date_range("2016-01-01", ctx.cfg["fecha_fin"], freq="D"), size=n))
    nombres = ctx.rng.choice(NOMBRES, size=n)
    apellidos = ctx.rng.choice(APELLIDOS, size=n)
    documentos = [str(10_000_000 + i) for i in range(n)]
    vehiculos = ctx.rng.choice(["Moto", "Bicicleta", "Van", "Camion"], size=n, p=[0.50, 0.12, 0.28, 0.10])
    zone_ids = ctx.rng.choice(zonas["id_zona"].to_numpy(), size=n)
    zone_city = zonas.set_index("id_zona")["id_ciudad"].to_dict()
    df = pd.DataFrame({
        "cond_id": _ids("CON", n, 5),
        "nomb_cond": nombres,
        "apell_cond": apellidos,
        "tip_doc": ctx.rng.choice(["CC", "CE"], size=n, p=[0.96, 0.04]),
        "num_doc_hash": [_sha(x) for x in documentos],
        "fec_ingreso": fechas_ingreso.date,
        "id_ciudad_base": [zone_city[z] for z in zone_ids],
        "tip_vehiculo": vehiculos,
        "cod_zona_asignada": zone_ids,
        "activo": ctx.rng.choice([True, False], size=n, p=[0.94, 0.06]),
        "calific_promedio_acum": np.clip(ctx.rng.normal(4.35, 0.45, size=n), 1, 5).round(2),
    })
    _aplicar_nulos(df, ["calific_promedio_acum"], ctx.cfg["porcentaje_nulos"], ctx.rng)
    return df


def generar_remitentes(ctx: Contexto, n: int) -> pd.DataFrame:
    tipos = ["Ecommerce", "Farmaceutico", "Retail", "Telecomunicaciones", "Otro"]
    city_names = [c["nombre"] for c in ctx.cfg["ciudades"]]
    tipo_cliente = ctx.rng.choice(tipos, size=n, p=[0.35, 0.14, 0.26, 0.15, 0.10])
    sla = np.where(np.isin(tipo_cliente, ["Farmaceutico", "Telecomunicaciones"]),
                   ctx.rng.choice([8, 12, 24], size=n, p=[0.25, 0.35, 0.40]),
                   ctx.rng.choice([12, 24, 36, 48], size=n, p=[0.10, 0.52, 0.23, 0.15]))
    return pd.DataFrame({
        "id_remitente": _ids("REM", n, 4),
        "razon_social": [f"Cliente Logistico {i+1:04d} SAS" for i in range(n)],
        "tipo_cliente": tipo_cliente,
        "ciudad_principal": ctx.rng.choice(city_names, size=n),
        "sla_entrega_horas": sla.astype(int),
        "penalidad_porc": ctx.rng.uniform(0.02, 0.08, size=n).round(4),
        "activo": ctx.rng.choice([True, False], size=n, p=[0.96, 0.04]),
    })


def _envios_bloque(ctx: Contexto, inicio: int, n: int, conductores: pd.DataFrame,
                   remitentes: pd.DataFrame, zonas: pd.DataFrame) -> pd.DataFrame:
    rng = ctx.rng
    ids_num = np.arange(inicio + 1, inicio + n + 1)
    fechas_rec = _muestra_fechas(ctx, n)
    horas = rng.integers(6, 21, size=n)
    minutos = rng.integers(0, 60, size=n)
    hra_recepcion = [f"{h:02d}:{m:02d}:00" for h, m in zip(horas, minutos)]

    cond_id = rng.choice(conductores["cond_id"].to_numpy(), size=n)
    remitente = rng.choice(remitentes["id_remitente"].to_numpy(), size=n)
    zona = rng.choice(zonas["id_zona"].to_numpy(), size=n)
    mapa_trafico = zonas.set_index("id_zona")["nivel_trafico_prom"].to_dict()
    mapa_dist = zonas.set_index("id_zona")["distancia_bodega_km"].to_dict()
    dificultad = np.array([(mapa_trafico[z] / 5) * 0.65 + min(mapa_dist[z] / 45, 1) * 0.35 for z in zona])

    p_fallo = np.clip(0.07 + dificultad * 0.11 + (horas >= 18) * 0.035, 0.06, 0.26)
    fallido = rng.random(n) < p_fallo
    segundo_intento = (~fallido) & (rng.random(n) < (0.08 + dificultad * 0.07))
    entregado = ~fallido

    programada = fechas_rec + pd.to_timedelta(np.where(horas < 10, 0, 1), unit="D")
    base_horas = np.clip(rng.normal(9 + dificultad * 7, 3.5, size=n), 1, 60)
    base_horas += segundo_intento * rng.uniform(6, 20, size=n)
    entrega_ts = pd.Series(pd.to_datetime(fechas_rec) + pd.to_timedelta(horas, unit="h") + pd.to_timedelta(minutos, unit="m") + pd.to_timedelta(base_horas, unit="h"))
    entrega_ts.loc[fallido] = pd.NaT

    intento1_ts = pd.to_datetime(fechas_rec) + pd.to_timedelta(np.minimum(horas + rng.integers(2, 10, size=n), 23), unit="h")
    intento2_ts = pd.Series(intento1_ts + pd.to_timedelta(rng.integers(4, 25, size=n), unit="h"))
    intento2_ts.loc[~segundo_intento & ~fallido] = pd.NaT
    intento2_ts.loc[fallido & (rng.random(n) > 0.62)] = pd.NaT

    causas = rng.choice(["DEST_AUSENTE", "DIR_INCORRECTA", "ZONA_DIFICIL", "RECHAZADO", "OTRO"],
                        size=n, p=[0.41, 0.27, 0.18, 0.09, 0.05])
    causas = np.where(fallido, causas, None)

    resultado1 = np.where(fallido | segundo_intento, "Fallido", "Entregado")
    resultado2 = np.where(segundo_intento, "Entregado", np.where(fallido, "Fallido", None))

    df = pd.DataFrame({
        "id_envio": [f"ENV{i:010d}" for i in ids_num],
        "id_remitente": remitente,
        "cond_id": cond_id,
        "id_zona_destino": zona,
        "tip_paquete": rng.choice(["Documento", "Pequeno", "Mediano", "Grande", "Fragil"], size=n,
                                   p=[0.08, 0.38, 0.31, 0.15, 0.08]),
        "peso_kg": np.clip(rng.lognormal(mean=1.0, sigma=0.8, size=n), 0.05, 80).round(2),
        "fec_recepcion": fechas_rec.date,
        "hra_recepcion": hra_recepcion,
        "fec_entrega_programada": programada.date,
        "fec_intento1": pd.to_datetime(intento1_ts).date,
        "hra_intento1": pd.to_datetime(intento1_ts).strftime("%H:%M:%S"),
        "resultado_intento1": resultado1,
        "fec_intento2": intento2_ts.dt.date,
        "hra_intento2": intento2_ts.dt.strftime("%H:%M:%S"),
        "resultado_intento2": resultado2,
        "fec_entrega_real": entrega_ts.dt.date,
        "estado_final": np.where(entregado, "Entregado", "No_entregado"),
        "motivo_fallo_cod": causas,
        "vr_declarado": np.clip(rng.lognormal(mean=12.2, sigma=0.9, size=n), 20_000, 15_000_000).round(0),
    })

    # Nulos solo en campos no críticos; los campos naturalmente opcionales se mantienen aparte.
    _aplicar_nulos(df, ["vr_declarado"], ctx.cfg["porcentaje_nulos"], rng)

    # Anomalías inconsistentes dentro del volumen base.
    p_peso = float(ctx.cfg["anomalias"]["peso_negativo"])
    p_fecha = float(ctx.cfg["anomalias"]["fecha_entrega_invalida"])
    n_peso = max(1, int(n * p_peso))
    n_fecha = max(1, int(n * p_fecha))
    idx_peso = rng.choice(df.index.to_numpy(), size=min(n_peso, n), replace=False)
    df.loc[idx_peso, "peso_kg"] = -df.loc[idx_peso, "peso_kg"].abs()
    elegibles = df.index[df["estado_final"].eq("Entregado")].to_numpy()
    if len(elegibles):
        idx_fecha = rng.choice(elegibles, size=min(n_fecha, len(elegibles)), replace=False)
        fechas_invalidas = [
            fecha - timedelta(days=1)
            for fecha in df.loc[idx_fecha, "fec_recepcion"]
        ]
        df.loc[idx_fecha, "fec_entrega_real"] = fechas_invalidas
    return df


def generar_envios(ctx: Contexto, n: int, conductores: pd.DataFrame,
                    remitentes: pd.DataFrame, zonas: pd.DataFrame, formatos: list[str]) -> int:
    escritor = EscritorPorBloques("TMS_ENVIOS", ctx.out_dir, formatos)
    chunk_size = 100_000 if n > 100_000 else max(1_000, n)
    total = 0
    duplicados_reservados: list[pd.DataFrame] = []
    try:
        for inicio in range(0, n, chunk_size):
            tam = min(chunk_size, n - inicio)
            bloque = _envios_bloque(ctx, inicio, tam, conductores, remitentes, zonas)
            if inicio == 0:
                n_dup = max(1, int(n * float(ctx.cfg["anomalias"]["duplicados_envios"])))
                duplicados_reservados.append(bloque.sample(n=min(n_dup, len(bloque)), random_state=int(ctx.cfg["seed"])))
            escritor.escribir(bloque)
            total += len(bloque)
        # Los duplicados exactos se anexan: el volumen configurado es el mínimo base.
        for dup in duplicados_reservados:
            escritor.escribir(dup)
            total += len(dup)
    finally:
        escritor.cerrar()
    return total


def generar_rutas(ctx: Contexto, n: int, conductores: pd.DataFrame) -> pd.DataFrame:
    fec = _muestra_fechas(ctx, n)
    inicio_h = ctx.rng.integers(5, 11, size=n)
    duracion = np.clip(ctx.rng.normal(8.2, 1.5, size=n), 3, 13)
    fin_h = np.minimum((inicio_h + duracion).astype(int), 23)
    km = np.clip(ctx.rng.gamma(3.0, 22.0, size=n), 5, 300)
    plan = ctx.rng.integers(10, 55, size=n)
    real = np.maximum(1, plan + ctx.rng.integers(-8, 7, size=n))
    df = pd.DataFrame({
        "id_ruta": _ids("RUT", n, 8),
        "cond_id": ctx.rng.choice(conductores["cond_id"].to_numpy(), size=n),
        "fec_ruta": fec.date,
        "hra_inicio": [f"{h:02d}:00:00" for h in inicio_h],
        "hra_fin": [f"{h:02d}:00:00" for h in fin_h],
        "km_recorridos": km.round(2),
        "num_paradas_plan": plan,
        "num_paradas_real": real,
        "desviacion_ruta_km": np.clip(ctx.rng.gamma(1.7, 3.0, size=n), 0, 45).round(2),
        "consumo_combustible": np.clip(km / ctx.rng.uniform(8, 34, size=n), 0.1, 40).round(2),
    })
    _aplicar_nulos(df, ["consumo_combustible"], ctx.cfg["porcentaje_nulos"], ctx.rng)
    return df


def generar_calificaciones(ctx: Contexto, n: int, n_envios_base: int) -> pd.DataFrame:
    envio_nums = ctx.rng.choice(np.arange(1, n_envios_base + 1), size=n, replace=False if n <= n_envios_base else True)
    fechas = _muestra_fechas(ctx, n)
    puntajes = ctx.rng.choice([1, 2, 3, 4, 5], size=n, p=[0.03, 0.05, 0.12, 0.34, 0.46])
    comentarios = np.array(["Entrega correcta" if p >= 4 else "Revisar experiencia de entrega" for p in puntajes], dtype=object)
    df = pd.DataFrame({
        "id_calificacion": _ids("CAL", n, 8),
        "id_envio": [f"ENV{i:010d}" for i in envio_nums],
        "fec_calificacion": fechas.date,
        "puntaje_1_5": puntajes,
        "comentario_texto": comentarios,
        "canal_calificacion": ctx.rng.choice(["App", "SMS", "Web", "CallCenter"], size=n, p=[0.55, 0.20, 0.17, 0.08]),
    })
    _aplicar_nulos(df, ["comentario_texto"], ctx.cfg["porcentaje_nulos"], ctx.rng)
    return df


def generar_novedades(ctx: Contexto, n: int, n_envios_base: int) -> pd.DataFrame:
    envio_nums = ctx.rng.choice(np.arange(1, n_envios_base + 1), size=n, replace=True)
    fechas = _muestra_fechas(ctx, n)
    tipos = ctx.rng.choice(["Cambio_direccion", "Destinatario_ausente", "Trafico", "Reprogramacion", "Devolucion", "Contacto"],
                           size=n, p=[0.12, 0.28, 0.20, 0.16, 0.08, 0.16])
    df = pd.DataFrame({
        "id_novedad": _ids("NOV", n, 8),
        "id_envio": [f"ENV{i:010d}" for i in envio_nums],
        "fec_novedad": fechas.date,
        "tip_novedad": tipos,
        "desc_novedad": [f"Evento operacional: {x}" for x in tipos],
        "id_agente_registro": [f"AGE{x:04d}" for x in ctx.rng.integers(1, 501, size=n)],
        "requiere_accion": ctx.rng.choice([True, False], size=n, p=[0.62, 0.38]),
    })
    _aplicar_nulos(df, ["desc_novedad"], ctx.cfg["porcentaje_nulos"], ctx.rng)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera datos sinteticos de LogiTrack")
    parser.add_argument("--profile", choices=["dev", "prod"], default="dev")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--formatos", nargs="+", choices=["csv", "parquet"], default=None)
    args = parser.parse_args()

    cfg = cargar_config(args.config)
    vol = cfg["profiles"][args.profile]
    formatos = args.formatos or cfg["formatos"]
    out_dir = args.output or (HERE / "output" / args.profile)
    out_dir.mkdir(parents=True, exist_ok=True)
    fechas, pesos = _fechas_contexto(cfg)
    ctx = Contexto(cfg=cfg, profile=args.profile, out_dir=out_dir,
                   rng=np.random.default_rng(int(cfg["seed"])), fechas=fechas, pesos_fecha=pesos)

    zonas = generar_zonas(ctx, int(vol["GEO_ZONAS"]))
    conductores = generar_conductores(ctx, int(vol["OPE_CONDUCTORES"]), zonas)
    remitentes = generar_remitentes(ctx, int(vol["CLI_REMITENTES"]))
    _escribir_tabla(conductores, "OPE_CONDUCTORES", out_dir, formatos)
    _escribir_tabla(remitentes, "CLI_REMITENTES", out_dir, formatos)
    _escribir_tabla(zonas, "GEO_ZONAS", out_dir, formatos)

    total_envios = generar_envios(ctx, int(vol["TMS_ENVIOS"]), conductores, remitentes, zonas, formatos)
    rutas = generar_rutas(ctx, int(vol["GPS_RUTAS"]), conductores)
    calificaciones = generar_calificaciones(ctx, int(vol["CAL_DESTINATARIOS"]), int(vol["TMS_ENVIOS"]))
    novedades = generar_novedades(ctx, int(vol["DIR_NOVEDADES"]), int(vol["TMS_ENVIOS"]))
    _escribir_tabla(rutas, "GPS_RUTAS", out_dir, formatos)
    _escribir_tabla(calificaciones, "CAL_DESTINATARIOS", out_dir, formatos)
    _escribir_tabla(novedades, "DIR_NOVEDADES", out_dir, formatos)

    manifest = {
        "profile": args.profile,
        "seed": int(cfg["seed"]),
        "fecha_inicio": cfg["fecha_inicio"],
        "fecha_fin": cfg["fecha_fin"],
        "formatos": formatos,
        "volumen_base": vol,
        "filas_tms_envios_incluyendo_duplicados": total_envios,
        "anomalias": cfg["anomalias"],
        "porcentaje_nulos_objetivo": cfg["porcentaje_nulos"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
