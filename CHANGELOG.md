# CHANGELOG

Todos los cambios significativos del proyecto deben registrarse aquí.

## Registro cronologico

| Fecha | Autor | Descripcion | Referencia |
|---|---|---|---|
| 2026-08-22 | catamf | Inicializacion de la plataforma LogiTrack y estructura base del repositorio. | `bf80d0f` |
| 2026-08-23 | catamf | Fases A-C: generacion, PostgreSQL, infraestructura Azure y validacion end-to-end del pipeline Medallion. | `2050154` |
| 2026-08-23 | catamf | Fase D: Unity Catalog, SQL Warehouse, minimo privilegio, aislamiento de notebooks ETL y validacion del rol Analyst. | `ab98d26` |
| 2026-08-23 | catamf | Fase E: volumen completo requerido, carga en Azure PostgreSQL DEV, trigger diario 02:00 Bogota, notificaciones, calidad y auditoria de acceso. | Cierre final |

## [Unreleased]

### Added
- PostgreSQL 16 local con `compose.yaml` para validar generación/esquema/carga antes de Azure.
- `.env.local.example` y soporte `--env-file` en el loader para separar configuración local de credenciales cloud.
- Diagrama `11_desarrollo_local_a_cloud.mmd` y roadmap local-first.
- Estructura inicial del repositorio.
- Generador reproducible de datos sintéticos para LogiTrack.
- Carga a PostgreSQL y control de watermark para ingesta incremental.
- Infraestructura Azure declarada con Terraform para ambientes `dev` y `prod`.
- ADF como ingestor y orquestador, definido como código.
- Notebooks PySpark para Bronze, Silver, Gold y calidad.
- Gobierno con Unity Catalog y SQL Warehouse implementado y validado en DEV.
- Documentación, catálogo, linaje y checklist de evidencias.

### Changed
- El orden de desarrollo ahora es local-first: Poetry → generación DEV → PostgreSQL local → validación incremental → Azure/Terraform → ADF/Databricks.
- Se reemplazó `venv`/`requirements.txt` por un único entorno local administrado con Poetry mediante `pyproject.toml` y `poetry.toml`; `.venv/` queda dentro del proyecto y fuera de Git.
- La configuración de pytest se centralizó en `pyproject.toml` para evitar archivos de configuración redundantes.
- Se implementó backoff exponencial explícito para la ingesta Bronze (30/60 s) y retry selectivo para I/O Spark (5/10/20 s).
- La alerta de volumen ahora se notifica de forma diferenciada y detiene el pipeline antes de Silver.
- El resumen diario ahora incluye conteos por capa, rechazados, calidad y duración y puede enviarse a un webhook guardado directamente en Key Vault mediante un script con entrada oculta.
- Las excepciones operacionales de notebooks se registran en `silver.errores_pipeline` antes de propagarse.
- Se redujeron reintentos innecesarios de errores no transitorios y se limpiaron caches locales del paquete final.
- Se centralizaron fallo, anomalía y resumen en un pipeline ADF reutilizable de notificaciones para evitar JSON duplicado.
- Se aclaró la arquitectura final: `Consumo analítico` es acceso gobernado a Gold mediante Unity Catalog + SQL Warehouse; no se crea una cuarta capa, esquema ni copia de datos.
- Se documentó y validó la segmentación mínima de compute: Data Engineer técnico/ADF usa el cluster ETL, Analyst usa SQL Warehouse y Admin gestiona ambos; no se crean clusters por persona.
- En `dev`, el trigger `trg_diario_0200_bogota` esta habilitado con frecuencia diaria a las 07:00 UTC, equivalente a las 02:00 hora de Bogota; SQL Warehouse permanece habilitado como Serverless X-Small para consumo analitico.
- Se añadió `docs/arquitectura.mmd` y se actualizó el diagrama Mermaid para mostrar flujo de datos, gobierno, compute y roles.
- Se validó el acceso del service principal Analyst a Gold mediante SQL Warehouse y la ausencia de acceso a Silver y Bronze.
- Los notebooks ETL se trasladaron de `/Shared/logitrack/dev` a `/Engineering/logitrack/dev` después de identificar permisos heredados de `/Shared`.
- Se validó que Analyst no puede acceder a los notebooks ETL ni utilizar el cluster ETL.
- Después del hardening de permisos, el pipeline ADF end-to-end volvió a ejecutarse correctamente.
- El plan final de Terraform en DEV confirmó `No changes`.
