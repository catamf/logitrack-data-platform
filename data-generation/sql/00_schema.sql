-- Esquema relacional fuente LogiTrack.
-- Los nombres de negocio conservan la nomenclatura del enunciado (PostgreSQL los normaliza a minúscula).
-- ts_actualizacion es un campo técnico para soportar la extracción incremental de ADF.

CREATE TABLE IF NOT EXISTS ope_conductores (
    cond_id varchar(16) PRIMARY KEY,
    nomb_cond varchar(80) NOT NULL,
    apell_cond varchar(80) NOT NULL,
    tip_doc varchar(8) NOT NULL,
    num_doc_hash varchar(64) NOT NULL,
    fec_ingreso date NOT NULL,
    id_ciudad_base varchar(8) NOT NULL,
    tip_vehiculo varchar(30) NOT NULL,
    cod_zona_asignada varchar(16) NOT NULL,
    activo boolean NOT NULL,
    calific_promedio_acum numeric(4,2),
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cli_remitentes (
    id_remitente varchar(16) PRIMARY KEY,
    razon_social varchar(160) NOT NULL,
    tipo_cliente varchar(40) NOT NULL,
    ciudad_principal varchar(80) NOT NULL,
    sla_entrega_horas integer NOT NULL,
    penalidad_porc numeric(7,4) NOT NULL,
    activo boolean NOT NULL,
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geo_zonas (
    id_zona varchar(16) PRIMARY KEY,
    nom_zona varchar(120) NOT NULL,
    id_ciudad varchar(8) NOT NULL,
    barrio_referencia varchar(120),
    latitud_centroide numeric(10,6) NOT NULL,
    longitud_centroide numeric(10,6) NOT NULL,
    nivel_trafico_prom numeric(4,1) NOT NULL,
    tip_zona varchar(40) NOT NULL,
    distancia_bodega_km numeric(10,2) NOT NULL,
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Sin PK intencional: la fuente contiene duplicados controlados para que Silver demuestre deduplicación.
CREATE TABLE IF NOT EXISTS tms_envios (
    id_envio varchar(20) NOT NULL,
    id_remitente varchar(16) NOT NULL,
    cond_id varchar(16) NOT NULL,
    id_zona_destino varchar(16) NOT NULL,
    tip_paquete varchar(30) NOT NULL,
    peso_kg numeric(12,2),
    fec_recepcion date NOT NULL,
    hra_recepcion time NOT NULL,
    fec_entrega_programada date NOT NULL,
    fec_intento1 date,
    hra_intento1 time,
    resultado_intento1 varchar(30),
    fec_intento2 date,
    hra_intento2 time,
    resultado_intento2 varchar(30),
    fec_entrega_real date,
    estado_final varchar(40) NOT NULL,
    motivo_fallo_cod varchar(40),
    vr_declarado numeric(18,2),
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_tms_envios_id_envio ON tms_envios(id_envio);
CREATE INDEX IF NOT EXISTS ix_tms_envios_ts_actualizacion ON tms_envios(ts_actualizacion);

CREATE TABLE IF NOT EXISTS gps_rutas (
    id_ruta varchar(20) PRIMARY KEY,
    cond_id varchar(16) NOT NULL,
    fec_ruta date NOT NULL,
    hra_inicio time NOT NULL,
    hra_fin time NOT NULL,
    km_recorridos numeric(12,2) NOT NULL,
    num_paradas_plan integer NOT NULL,
    num_paradas_real integer NOT NULL,
    desviacion_ruta_km numeric(12,2) NOT NULL,
    consumo_combustible numeric(12,2),
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cal_destinatarios (
    id_calificacion varchar(20) PRIMARY KEY,
    id_envio varchar(20) NOT NULL,
    fec_calificacion date NOT NULL,
    puntaje_1_5 integer NOT NULL,
    comentario_texto text,
    canal_calificacion varchar(40) NOT NULL,
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dir_novedades (
    id_novedad varchar(20) PRIMARY KEY,
    id_envio varchar(20) NOT NULL,
    fec_novedad date NOT NULL,
    tip_novedad varchar(60) NOT NULL,
    desc_novedad text,
    id_agente_registro varchar(20) NOT NULL,
    requiere_accion boolean NOT NULL,
    ts_actualizacion timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS log_ingesta_adf (
    log_id bigserial PRIMARY KEY,
    batch_id varchar(100) NOT NULL,
    tabla varchar(80) NOT NULL,
    watermark_inicio timestamptz,
    watermark_fin timestamptz,
    registros_procesados bigint NOT NULL DEFAULT 0,
    bytes_escritos bigint NOT NULL DEFAULT 0,
    duracion_segundos numeric(18,3),
    estado varchar(30) NOT NULL,
    registrado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_log_ingesta_adf_batch ON log_ingesta_adf(batch_id, tabla);

CREATE TABLE IF NOT EXISTS control_ingesta (
    tabla varchar(80) PRIMARY KEY,
    watermark_utc timestamptz NOT NULL DEFAULT '1900-01-01 00:00:00+00',
    ultima_ejecucion_id varchar(100),
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO control_ingesta(tabla) VALUES
 ('ope_conductores'), ('cli_remitentes'), ('geo_zonas'), ('tms_envios'),
 ('gps_rutas'), ('cal_destinatarios'), ('dir_novedades')
ON CONFLICT (tabla) DO NOTHING;

CREATE OR REPLACE FUNCTION set_ts_actualizacion() RETURNS trigger AS $$
BEGIN
    NEW.ts_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['ope_conductores','cli_remitentes','geo_zonas','tms_envios','gps_rutas','cal_destinatarios','dir_novedades']
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_ts_actualizacion ON %I', t);
        EXECUTE format('CREATE TRIGGER trg_ts_actualizacion BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_ts_actualizacion()', t);
    END LOOP;
END $$;
