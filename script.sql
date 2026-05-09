-- Input SQL para optimizacion de rutas con OR-Tools + Google Maps.
-- Base de datos: hackaton.db (SQLite)
--
-- Uso:
--   sqlite3 hackaton.db < script.sql
--
-- La vista principal que debe consumir Python es:
--   vw_ortools_paradas
--
-- Nota importante sobre IDs:
--   - ruta se repite en distintos transportes/dias.
--   - por eso id_ruta_algoritmo combina fecha + transporte + ruta.

DROP VIEW IF EXISTS vw_ortools_paradas;
DROP VIEW IF EXISTS vw_entregas_enriquecidas;
DROP VIEW IF EXISTS vw_horarios_cliente;
DROP VIEW IF EXISTS vw_direcciones_cliente;
DROP TABLE IF EXISTS resultado_rutas_ortools;

CREATE VIEW vw_direcciones_cliente AS
SELECT
    cliente,
    MAX(NULLIF(TRIM(nombre_1), '')) AS nombre_1,
    MAX(NULLIF(TRIM(nombre_2), '')) AS nombre_2,
    MAX(NULLIF(TRIM(calle), '')) AS calle,
    MAX(NULLIF(TRIM(cp), '')) AS cp,
    MAX(NULLIF(TRIM(poblaci_n), '')) AS poblaci_n
FROM direcciones
GROUP BY cliente;

CREATE VIEW vw_horarios_cliente AS
SELECT
    deudor AS id_destinatario_mercancia,
    MAX(
        CASE
            WHEN horario_inicia_a IS NOT NULL
             AND horario_termina_a IS NOT NULL
             AND NOT (
                horario_inicia_a IN ('00:00:00', '')
                AND horario_termina_a IN ('23:59:59', '00:00:00', '')
             )
            THEN 1
            ELSE 0
        END
    ) AS tiene_prioridad_horaria,
    GROUP_CONCAT(
        DISTINCT
        CASE
            WHEN d_a_semana IS NOT NULL AND d_a_semana <> ''
            THEN d_a_semana || ':' || COALESCE(turno, '') || ':' ||
                 COALESCE(horario_inicia_a, '') || '-' || COALESCE(horario_termina_a, '')
        END
    ) AS ventanas_horarias
FROM horarios_entrega
GROUP BY deudor;

CREATE VIEW vw_entregas_enriquecidas AS
SELECT
    de.fecha,
    de.transporte AS id_transporte,
    de.ruta AS id_ruta,
    de.fecha || '|' || de.transporte || '|' || de.ruta AS id_ruta_algoritmo,
    de.repartidor AS id_repartidor,
    de.entrega AS id_entrega,

    -- Cliente/parada real de la entrega.
    de.destinatario_mc_a_1 AS id_destinatario_mercancia,
    COALESCE(NULLIF(TRIM(dir.nombre_1), ''), NULLIF(TRIM(de.nombre_1), '')) AS nombre_destinatario,
    COALESCE(NULLIF(TRIM(dir.nombre_2), ''), NULLIF(TRIM(de.nombre_2), '')) AS nombre_destinatario_2,
    COALESCE(NULLIF(TRIM(dir.calle), ''), NULLIF(TRIM(de.calle), '')) AS calle,
    COALESCE(NULLIF(TRIM(dir.cp), ''), NULLIF(TRIM(de.cp), '')) AS cp,
    COALESCE(NULLIF(TRIM(dir.poblaci_n), ''), NULLIF(TRIM(de.poblaci_n), '')) AS poblacion,
    TRIM(
        COALESCE(NULLIF(TRIM(dir.calle), ''), NULLIF(TRIM(de.calle), '')) || ', ' ||
        COALESCE(NULLIF(TRIM(dir.cp), ''), NULLIF(TRIM(de.cp), '')) || ' ' ||
        COALESCE(NULLIF(TRIM(dir.poblaci_n), ''), NULLIF(TRIM(de.poblaci_n), '')) || ', España'
    ) AS direccion_completa,

    -- Zona de transporte. Se deja visible para que el algoritmo pueda priorizar.
    de.zonatransp AS id_zona_transporte,
    COALESCE(z.nombre_zonas, de.zonatransp_1) AS nombre_zona_transporte,
    z.rutreal AS ruta_real_zona,
    z.denominaci_n AS denominacion_ruta_zona,

    -- Material.
    de.material AS id_material,
    de.denominaci_n AS material_descripcion,
    mz.ubic AS ubicacion_material,
    de.un_medida_venta,
    CAST(REPLACE(de.cantidad_entrega, ',', '.') AS REAL) AS cantidad_entrega,
    CASE
        WHEN UPPER(de.denominaci_n) LIKE '%RET%'
          OR UPPER(de.denominaci_n) LIKE '%VACIO%'
          OR UPPER(de.material) LIKE 'CJ%'
          OR UPPER(de.material) LIKE 'PL%'
          OR UPPER(de.material) LIKE 'BRL%'
        THEN 1
        ELSE 0
    END AS es_retornable,

    -- Horarios de entrega agregados por cliente para no duplicar cantidades.
    COALESCE(h.tiene_prioridad_horaria, 0) AS tiene_prioridad_horaria,
    h.ventanas_horarias
FROM detalle_entrega de
LEFT JOIN vw_direcciones_cliente dir
    ON dir.cliente = de.destinatario_mc_a_1
LEFT JOIN zonas z
    ON z.zonas = de.zonatransp
   AND de.zonatransp <> ''
LEFT JOIN materiales_zubic mz
    ON mz.material = de.material
LEFT JOIN vw_horarios_cliente h
    ON h.id_destinatario_mercancia = de.destinatario_mc_a_1;

CREATE VIEW vw_ortools_paradas AS
WITH paradas AS (
    SELECT
        fecha,
        id_transporte,
        id_ruta,
        id_ruta_algoritmo,
        id_repartidor,
        id_destinatario_mercancia,
        nombre_destinatario,
        nombre_destinatario_2,
        calle,
        cp,
        poblacion,
        direccion_completa,
        id_zona_transporte,
        nombre_zona_transporte,
        ruta_real_zona,
        denominacion_ruta_zona,

        GROUP_CONCAT(DISTINCT id_entrega) AS ids_entrega,
        COUNT(DISTINCT id_entrega) AS num_entregas,
        COUNT(DISTINCT id_material) AS num_materiales,
        SUM(cantidad_entrega) AS cantidad_total,
        SUM(CASE WHEN es_retornable = 1 THEN cantidad_entrega ELSE 0 END) AS cantidad_retornable,
        MAX(es_retornable) AS tiene_material_retornable,

        -- Prioridad operativa: 1 si el cliente tiene alguna ventana distinta a todo el dia.
        MAX(tiene_prioridad_horaria) AS tiene_prioridad_horaria,
        MAX(ventanas_horarias) AS ventanas_horarias
    FROM vw_entregas_enriquecidas
    GROUP BY
        fecha,
        id_transporte,
        id_ruta,
        id_ruta_algoritmo,
        id_repartidor,
        id_destinatario_mercancia,
        nombre_destinatario,
        nombre_destinatario_2,
        calle,
        cp,
        poblacion,
        direccion_completa,
        id_zona_transporte,
        nombre_zona_transporte,
        ruta_real_zona,
        denominacion_ruta_zona
)
SELECT
    ROW_NUMBER() OVER (
        PARTITION BY id_ruta_algoritmo
        ORDER BY tiene_prioridad_horaria DESC, id_zona_transporte, poblacion, calle, id_destinatario_mercancia
    ) AS id_parada_inicial,
    *
FROM paradas;

CREATE TABLE resultado_rutas_ortools (
    id_resultado INTEGER PRIMARY KEY AUTOINCREMENT,
    id_ruta_algoritmo TEXT NOT NULL,
    fecha TEXT,
    id_transporte TEXT,
    id_ruta TEXT,
    id_repartidor TEXT,

    -- Orden calculado por OR-Tools.
    orden_parada INTEGER NOT NULL,
    id_destinatario_mercancia TEXT NOT NULL,
    ids_entrega TEXT,
    direccion_completa TEXT NOT NULL,

    -- Coordenadas devueltas por Google Maps Geocoding API.
    latitud REAL,
    longitud REAL,

    -- Costes de la parada/tramo, si se calculan con Distance Matrix/Routes API.
    distancia_desde_anterior_m INTEGER,
    duracion_desde_anterior_s INTEGER,
    distancia_acumulada_m INTEGER,
    duracion_acumulada_s INTEGER,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_resultado_rutas_ortools_ruta
    ON resultado_rutas_ortools (id_ruta_algoritmo, orden_parada);

-- Ejemplo: input de una ruta concreta para pasarlo a Python/OR-Tools.
-- SELECT *
-- FROM vw_ortools_paradas
-- WHERE id_ruta_algoritmo = '30/01/2026|11420136|DA0216'
-- ORDER BY id_parada_inicial;

-- Ejemplo: todas las rutas disponibles con numero de paradas.
-- SELECT id_ruta_algoritmo, fecha, id_transporte, id_ruta, id_repartidor, COUNT(*) AS paradas
-- FROM vw_ortools_paradas
-- GROUP BY id_ruta_algoritmo, fecha, id_transporte, id_ruta, id_repartidor
-- ORDER BY fecha, id_transporte, id_ruta;
