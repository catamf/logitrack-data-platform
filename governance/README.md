# Gobierno y seguridad

La segmentación de acceso se implementa con Unity Catalog para los datos y con permisos de Databricks para el compute. La intención es aplicar mínimo privilegio sin crear clusters innecesarios.

## Roles implementados

| Rol | Principal usado | Compute | Bronze | Silver | Gold |
|---|---|---|---:|---:|---:|
| Data Engineer técnico | Managed Identity de ADF registrada como service principal | cluster ETL | lectura/escritura | lectura/escritura | lectura/escritura |
| Analyst | usuario indicado en `analyst_user_name` | SQL Warehouse | sin grants | sin grants | `SELECT` |
| Admin | usuario que ejecuta Terraform | cluster ETL + SQL Warehouse | control total | control total | control total |

La Managed Identity de ADF recibe `CAN_ATTACH_TO` sobre el cluster ETL y los grants necesarios sobre Bronze/Silver/Gold. Analyst no recibe permisos sobre ese cluster. Para consumo, Analyst recibe `CAN_USE` sobre SQL Warehouse y `SELECT` únicamente sobre Gold. Admin, como administrador autenticado del workspace, conserva control de ambos tipos de compute y de los objetos de datos; Databricks no permite rebajar los permisos de `admins`.

No se crea un cluster por usuario ni un grupo de clusters por persona: esa separación sería innecesaria para esta prueba y aumentaría costo y complejidad.

El rol Analyst es opcional durante la construcción para no inventar una identidad. Antes de tomar la evidencia final, configura `analyst_user_name` con una cuenta real a la que puedas iniciar sesión.

> Nota técnica: los grupos creados únicamente a nivel de workspace son grupos legacy y no son adecuados para `GRANT` de Unity Catalog. Por eso esta versión usa principals válidos (usuario/service principal) para mantener la configuración reproducible sin requerir administración adicional del Databricks Account Console.

`permisos.sql` contiene las consultas de verificación para las capturas de evidencia.

## Consumo analítico

No existe una capa física `consumo`. Analyst usa Databricks SQL Warehouse para consultar objetos de `gold` autorizados por Unity Catalog. Esto evita duplicar datos y mantiene el modelo solicitado: Bronze/Silver denegados y Gold de solo lectura.
