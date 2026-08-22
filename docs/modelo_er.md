# Modelo Entidad–Relación

```mermaid
erDiagram
  OPE_CONDUCTORES ||--o{ TMS_ENVIOS : conduce
  OPE_CONDUCTORES ||--o{ GPS_RUTAS : realiza
  CLI_REMITENTES ||--o{ TMS_ENVIOS : remite
  GEO_ZONAS ||--o{ TMS_ENVIOS : destino
  GEO_ZONAS ||--o{ OPE_CONDUCTORES : asigna
  TMS_ENVIOS ||--o| CAL_DESTINATARIOS : recibe
  TMS_ENVIOS ||--o{ DIR_NOVEDADES : genera

  OPE_CONDUCTORES {
    string cond_id PK
    string num_doc_hash
    date fec_ingreso
    string tip_vehiculo
    string cod_zona_asignada FK
  }
  CLI_REMITENTES {
    string id_remitente PK
    string razon_social
    int sla_entrega_horas
    decimal penalidad_porc
  }
  GEO_ZONAS {
    string id_zona PK
    string id_ciudad
    string tip_zona
    decimal distancia_bodega_km
  }
  TMS_ENVIOS {
    string id_envio
    string id_remitente FK
    string cond_id FK
    string id_zona_destino FK
    date fec_recepcion
    date fec_entrega_real
    string estado_final
  }
  GPS_RUTAS {
    string id_ruta PK
    string cond_id FK
    date fec_ruta
    decimal km_recorridos
  }
  CAL_DESTINATARIOS {
    string id_calificacion PK
    string id_envio FK
    int puntaje_1_5
  }
  DIR_NOVEDADES {
    string id_novedad PK
    string id_envio FK
    date fec_novedad
    string tip_novedad
  }
```

`TMS_ENVIOS` no impone `PRIMARY KEY` física en PostgreSQL para permitir el patrón de duplicado intencional requerido para probar la capa Silver. La clave de negocio esperada sigue siendo `id_envio`.
