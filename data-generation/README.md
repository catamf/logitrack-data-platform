# Generación y carga de datos

Estos scripts se ejecutan desde la raíz del repositorio dentro del entorno administrado por Poetry. El desarrollo sigue una secuencia **local-first**: primero PostgreSQL 16 en Docker; después Azure Database for PostgreSQL con el mismo código.

## 1. Generar datos DEV

```powershell
poetry run python data-generation/generar_datos.py --profile dev
```

`config.yaml` centraliza semilla, fechas, porcentajes y volúmenes. `dev` genera un conjunto pequeño para iterar rápido; `prod` contiene los volúmenes mínimos de la prueba. El generador escribe CSV y Parquet en `data-generation/output/<profile>/`. Para `TMS_ENVIOS` usa escritura por bloques para no mantener dos millones de filas completas en memoria.

## 2. Probar primero con PostgreSQL local

```powershell
Copy-Item .env.local.example .env.local
docker compose --env-file .env.local up -d
poetry run python data-generation/cargar_postgresql.py --profile dev --truncate --env-file .env.local
```

`compose.yaml` solo contiene el servicio PostgreSQL y un volumen persistente. La contraseña local vive en `.env.local`, que no se versiona.

`--truncate` vuelve reproducible la carga durante desarrollo: vacía las siete tablas, reinicia el watermark y vuelve a cargar el conjunto generado. No se usa en ejecuciones incrementales de ADF.

## 3. Reutilizar la misma carga en Azure

Cuando Terraform haya creado Azure Database for PostgreSQL, configura `PGHOST`, `PGDATABASE`, `PGUSER` y `AZURE_KEY_VAULT_URL` en la sesión y ejecuta:

```powershell
poetry run python data-generation/cargar_postgresql.py --profile dev --truncate
```

No pases `.env.local` en la carga cloud. El script usa la configuración de la sesión y recupera la contraseña desde Key Vault si está disponible.

Las anomalías se documentan en `docs/anomalias.md`. El generador mantiene FK válidas en los registros base; las inconsistencias intencionales afectan duplicidad, peso y fechas.
