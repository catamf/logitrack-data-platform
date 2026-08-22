"""Carga los CSV generados a PostgreSQL sin almacenar credenciales en el repositorio."""

from __future__ import annotations

import argparse
import csv
import getpass
import os
from pathlib import Path

from dotenv import load_dotenv
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
except ImportError:
    DefaultAzureCredential = None
    SecretClient = None


HERE = Path(__file__).resolve().parent

TABLAS = [
    "OPE_CONDUCTORES",
    "CLI_REMITENTES",
    "GEO_ZONAS",
    "TMS_ENVIOS",
    "GPS_RUTAS",
    "CAL_DESTINATARIOS",
    "DIR_NOVEDADES",
]


def obtener_password() -> str:
    """Obtiene la contraseña desde entorno, Key Vault o entrada interactiva."""
    if os.getenv("PGPASSWORD"):
        return os.environ["PGPASSWORD"]

    vault_url = os.getenv("AZURE_KEY_VAULT_URL")
    secret_name = os.getenv(
        "AZURE_POSTGRES_PASSWORD_SECRET",
        "postgresql-admin-password",
    )

    if vault_url and DefaultAzureCredential and SecretClient:
        cliente = SecretClient(
            vault_url=vault_url,
            credential=DefaultAzureCredential(),
        )
        return cliente.get_secret(secret_name).value

    return getpass.getpass(
        "Contraseña PostgreSQL (no se mostrará): "
    )


def conexion_url(password: str) -> URL:
    """Construye la URL de conexión sin exponer la contraseña."""
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("PGUSER", "logitrack_admin"),
        password=password,
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        database=os.getenv("PGDATABASE", "logitrack"),
    )


def ejecutar_schema(engine) -> None:
    """Crea las tablas y objetos técnicos si todavía no existen."""
    schema_path = HERE / "sql" / "00_schema.sql"
    script = schema_path.read_text(encoding="utf-8")

    raw = engine.raw_connection()

    try:
        with raw.cursor() as cursor:
            cursor.execute(script)

        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def columnas_csv(path: Path) -> list[str]:
    """Lee y normaliza el encabezado de un CSV."""
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as archivo:
        reader = csv.reader(archivo)

        try:
            columnas = next(reader)
        except StopIteration as exc:
            raise ValueError(
                f"El CSV está vacío: {path}"
            ) from exc

    if not columnas:
        raise ValueError(
            f"El CSV no contiene columnas: {path}"
        )

    return [
        columna.strip().lower()
        for columna in columnas
    ]


def cargar_csv(engine, tabla: str, path: Path) -> int:
    """Carga un CSV usando COPY y conserva los tipos definidos por PostgreSQL."""
    if tabla not in TABLAS:
        raise ValueError(
            f"Tabla no permitida: {tabla}"
        )

    columnas = columnas_csv(path)
    nombre_tabla = tabla.lower()

    copy_sql = sql.SQL(
        "COPY {} ({}) "
        "FROM STDIN "
        "WITH (FORMAT CSV, HEADER TRUE)"
    ).format(
        sql.Identifier(nombre_tabla),
        sql.SQL(", ").join(
            sql.Identifier(columna)
            for columna in columnas
        ),
    )

    count_sql = sql.SQL(
        "SELECT COUNT(*) FROM {}"
    ).format(
        sql.Identifier(nombre_tabla)
    )

    raw = engine.raw_connection()

    try:
        with raw.cursor() as cursor:
            cursor.execute(count_sql)
            filas_antes = cursor.fetchone()[0]

            with cursor.copy(copy_sql) as copy:
                with path.open("rb") as archivo:
                    while bloque := archivo.read(1024 * 1024):
                        copy.write(bloque)

            cursor.execute(count_sql)
            filas_despues = cursor.fetchone()[0]

        raw.commit()

    except Exception:
        raw.rollback()
        raise

    finally:
        raw.close()

    filas_cargadas = filas_despues - filas_antes

    print(
        f"{tabla}: "
        f"{filas_cargadas:,} filas cargadas"
    )

    return filas_cargadas


def truncar_fuente(engine) -> None:
    """Vacía la fuente y reinicia los watermarks para una carga inicial."""
    with engine.begin() as conexion:
        for tabla in reversed(TABLAS):
            conexion.execute(
                text(
                    f"TRUNCATE TABLE {tabla.lower()};"
                )
            )

        conexion.execute(
            text(
                "UPDATE control_ingesta "
                "SET watermark_utc = "
                "'1900-01-01 00:00:00+00';"
            )
        )


def mostrar_conteos(engine) -> None:
    """Muestra evidencia de filas cargadas por tabla."""
    print("\nConteos en PostgreSQL:")

    with engine.connect() as conexion:
        for tabla in TABLAS:
            cantidad = conexion.execute(
                text(
                    f"SELECT COUNT(*) "
                    f"FROM {tabla.lower()}"
                )
            ).scalar_one()

            print(
                f"{tabla}: {cantidad:,}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--profile",
        choices=["dev", "prod"],
        default="dev",
    )

    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Vacía las siete tablas antes de cargar",
    )

    parser.add_argument(
        "--env-file",
        type=Path,
        help=(
            "Archivo .env opcional. "
            "Úsalo solo para desarrollo local, "
            "por ejemplo .env.local"
        ),
    )

    args = parser.parse_args()

    if args.env_file:
        if not args.env_file.exists():
            raise SystemExit(
                f"No existe el archivo de entorno: "
                f"{args.env_file}"
            )

        load_dotenv(
            args.env_file,
            override=False,
        )

    out_dir = (
        HERE
        / "output"
        / args.profile
    )

    if not out_dir.exists():
        raise SystemExit(
            f"No existe {out_dir}. "
            "Ejecuta primero generar_datos.py"
        )

    engine = create_engine(
        conexion_url(
            obtener_password()
        ),
        pool_pre_ping=True,
    )

    ejecutar_schema(engine)

    if args.truncate:
        truncar_fuente(engine)

    for tabla in TABLAS:
        csv_path = (
            out_dir
            / f"{tabla}.csv"
        )

        if not csv_path.exists():
            raise FileNotFoundError(
                csv_path
            )

        cargar_csv(
            engine,
            tabla,
            csv_path,
        )

    mostrar_conteos(engine)

    engine.dispose()


if __name__ == "__main__":
    main()
