-- Sustituir <env> por dev o prod.
-- Los grants efectivos se declaran en Terraform (infra/databricks.tf).

SHOW GRANTS ON CATALOG logitrack_<env>;
SHOW GRANTS ON SCHEMA logitrack_<env>.bronze;
SHOW GRANTS ON SCHEMA logitrack_<env>.silver;
SHOW GRANTS ON SCHEMA logitrack_<env>.gold;

-- Iniciar sesión con la cuenta configurada como analyst_user_name.
-- Debe funcionar:
SELECT *
FROM logitrack_<env>.gold.kpi_logistica_diaria
LIMIT 10;

-- Deben devolver PERMISSION_DENIED:
SELECT * FROM logitrack_<env>.silver.tms_envios LIMIT 1;
SELECT * FROM logitrack_<env>.bronze.tms_envios LIMIT 1;
