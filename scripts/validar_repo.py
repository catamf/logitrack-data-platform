from pathlib import Path
import json
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "poetry.toml",
    "compose.yaml",
    ".env.local.example",
    "infra/main.tf",
    "infra/variables.tf",
    "data-generation/config.yaml",
    "data-generation/generar_datos.py",
    "pipelines/databricks/01_procesar_silver.py",
    "pipelines/databricks/02_procesar_gold.py",
    "orchestration/adf/pipeline_principal.json",
    "orchestration/adf/pipeline_notificar.json",
    "docs/catalogo_datos.md",
]

missing = [path for path in REQUIRED if not (ROOT / path).exists()]
if missing:
    print("Faltan archivos:", *missing, sep="\n- ")
    sys.exit(1)



compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
postgres = compose.get("services", {}).get("postgres", {})
if not str(postgres.get("image", "")).startswith("postgres:16"):
    print("ERROR: compose.yaml debe declarar PostgreSQL 16 para desarrollo local")
    sys.exit(8)
if "healthcheck" not in postgres:
    print("ERROR: PostgreSQL local debe incluir healthcheck")
    sys.exit(9)

legacy_dependency_files = ["requirements.txt", "pytest.ini"]
legacy_found = [name for name in legacy_dependency_files if (ROOT / name).exists()]
if legacy_found:
    print("ERROR: configuracion Python duplicada encontrada:", *legacy_found, sep="\n- ")
    sys.exit(7)

for forbidden in ROOT.rglob("*"):
    if forbidden.is_file() and (
        "tfstate" in forbidden.name or forbidden.suffix == ".tfplan"
    ):
        print(f"ERROR: archivo Terraform sensible encontrado: {forbidden}")
        sys.exit(2)

patterns = [
    re.compile(
        r"(?i)(password|token|client_secret)\s*=\s*[\"\'](?!TODO|CHANGEME|)[^\"\']{5,}[\"\']"
    ),
]
for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for pattern in patterns:
        if pattern.search(text):
            print(f"ADVERTENCIA: revisa posible secreto en {path.relative_to(ROOT)}")

pipeline_path = ROOT / "orchestration/adf/pipeline_principal.json"
pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
activities = pipeline["properties"]["activities"]
activity_names = {activity["name"] for activity in activities}
expected_top_level = {
    "ForEach_tablas_fuente",
    "Auditar_Bronze",
    "If_Anomalia_Volumen",
    "Procesar_Silver",
    "Procesar_Gold",
    "Calidad_Gold",
    "Resumen_Ejecucion",
    "Notificar_Resumen_Diario",
    "Fallo_Procesar_Silver",
    "Fallo_Procesar_Gold",
    "Fallo_Calidad_Gold",
}
if not expected_top_level.issubset(activity_names):
    print("ERROR: faltan actividades obligatorias en el pipeline ADF")
    sys.exit(3)

foreach = next(a for a in activities if a["name"] == "ForEach_tablas_fuente")
nested = foreach["typeProperties"]["activities"]
nested_names = {activity["name"] for activity in nested}
expected_retry = {
    "Copy_Bronze_intento_1",
    "Espera_backoff_30s",
    "Copy_Bronze_intento_2",
    "Espera_backoff_60s",
    "Copy_Bronze_intento_3",
}
if not expected_retry.issubset(nested_names):
    print("ERROR: falta la cadena de backoff exponencial de Bronze")
    sys.exit(4)

waits = {
    activity["name"]: activity["typeProperties"].get("waitTimeInSeconds")
    for activity in nested
    if activity["type"] == "Wait"
}
if waits.get("Espera_backoff_30s") != 30 or waits.get("Espera_backoff_60s") != 60:
    print("ERROR: el backoff de Bronze debe ser 30s y 60s")
    sys.exit(5)

notification_path = ROOT / "orchestration/adf/pipeline_notificar.json"
notification = json.loads(notification_path.read_text(encoding="utf-8"))
notification_names = {activity["name"] for activity in notification["properties"]["activities"]}
if notification_names != {"If_Enviar_Notificacion", "If_Propagar_Fallo"}:
    print("ERROR: pipeline reutilizable de notificaciones incompleto")
    sys.exit(6)

print("Estructura, PostgreSQL local, secretos y orquestacion base: OK")
