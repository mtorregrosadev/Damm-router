"""
Guarda el resultado del algoritmo de carga en la base de datos.

Tabla nueva: resultado_carga_camion
  - Vinculada a resultado_rutas_ortools por id_ruta_algoritmo
  - Las matrices se guardan como JSON en SQLite y como arrays nativos en MongoDB

Flujo completo:
  1. Leer paradas ordenadas de resultado_rutas_ortools para un id_ruta
  2. Leer cantidad de cajas de detalle_entrega
  3. Ejecutar truck_loader.cargar_camion()
  4. Guardar ambas matrices en resultado_carga_camion (SQLite + MongoDB)
"""

import sqlite3
import json
import numpy as np
from truck_loader import cargar_camion
from mongo import get_db

DB_PATH = "/Users/jportabellag/Documents/Cursos/InterHack/hackaton.db"


def crear_tabla(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resultado_carga_camion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_ruta_algoritmo TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            -- Matrices del camión completo (JSON de array 3D)
            camion_binario TEXT NOT NULL,
            camion_ids     TEXT NOT NULL,

            -- Matrices por palet (JSON de array 4D: [n_palets, X, Y, Z])
            palets_binario TEXT NOT NULL,
            palets_ids     TEXT NOT NULL,

            -- Metadata útil para el frontend
            n_palets_usados INTEGER,
            n_paradas       INTEGER,
            total_cajas     INTEGER,
            ocupacion_pct   REAL
        )
    """)
    conn.commit()


def obtener_ruta(conn: sqlite3.Connection, id_ruta: str):
    """
    Devuelve (paradas_ordenadas, cajas_por_parada) a partir de la BD.

    paradas_ordenadas: [1, 2, 3, ...] en orden de entrega
    cajas_por_parada:  {1: 40, 2: 20, ...}
    """
    cursor = conn.execute("""
        SELECT orden_parada, id_destinatario_mercancia
        FROM resultado_rutas_ortools
        WHERE id_ruta_algoritmo = ?
        ORDER BY orden_parada
    """, (id_ruta,))
    filas = cursor.fetchall()

    if not filas:
        raise ValueError(f"No se encontró la ruta: {id_ruta}")

    paradas = list(range(1, len(filas) + 1))

    cajas_por_parada = {}
    for orden, dest in filas:
        cursor2 = conn.execute("""
            SELECT COALESCE(SUM(CAST(cantidad_entrega AS REAL)), 0)
            FROM detalle_entrega
            WHERE destinatario_mc_a = ?
        """, (dest,))
        total = int(cursor2.fetchone()[0])
        cajas_por_parada[orden] = max(total, 1)

    return paradas, cajas_por_parada


def guardar_resultado(conn: sqlite3.Connection, id_ruta: str) -> dict:
    """
    Ejecuta el algoritmo de carga para una ruta y guarda el resultado en BD.
    Devuelve un dict con un resumen para confirmar.
    """
    paradas, cajas_por_parada = obtener_ruta(conn, id_ruta)

    p_bin, p_ids, t_bin, t_ids = cargar_camion(paradas, cajas_por_parada)

    total_cajas = sum(cajas_por_parada.values())
    n_palets = len(p_bin)
    from truck_loader import CAMION_COLS, CAMION_FILAS, PALET_CAP
    ocupacion = 100 * total_cajas / (CAMION_COLS * CAMION_FILAS * PALET_CAP)

    camion_bin_json  = json.dumps(t_bin.tolist())
    camion_ids_json  = json.dumps(t_ids.tolist())
    palets_bin_json  = json.dumps(p_bin.tolist())
    palets_ids_json  = json.dumps(p_ids.tolist())

    doc = {
        "id_ruta_algoritmo": id_ruta,
        "camion_binario": t_bin.tolist(),
        "camion_ids":     t_ids.tolist(),
        "palets_binario": p_bin.tolist(),
        "palets_ids":     p_ids.tolist(),
        "n_palets_usados": n_palets,
        "n_paradas":       len(paradas),
        "total_cajas":     total_cajas,
        "ocupacion_pct":   round(ocupacion, 1),
    }

    # ── SQLite ───────────────────────────────────────────────
    conn.execute(
        "DELETE FROM resultado_carga_camion WHERE id_ruta_algoritmo = ?",
        (id_ruta,)
    )
    conn.execute("""
        INSERT INTO resultado_carga_camion
            (id_ruta_algoritmo, camion_binario, camion_ids,
             palets_binario, palets_ids,
             n_palets_usados, n_paradas, total_cajas, ocupacion_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_ruta,
        camion_bin_json, camion_ids_json,
        palets_bin_json, palets_ids_json,
        n_palets, len(paradas), total_cajas, round(ocupacion, 1)
    ))
    conn.commit()

    # ── MongoDB ──────────────────────────────────────────────
    col = get_db()["resultado_carga_camion"]
    col.replace_one({"id_ruta_algoritmo": id_ruta}, doc, upsert=True)

    return {
        "id_ruta": id_ruta,
        "n_paradas": len(paradas),
        "total_cajas": total_cajas,
        "n_palets_usados": n_palets,
        "ocupacion_pct": round(ocupacion, 1),
    }


def leer_resultado(conn: sqlite3.Connection, id_ruta: str) -> dict:
    """
    Lee el resultado guardado y devuelve las matrices como arrays numpy.
    """
    cursor = conn.execute("""
        SELECT camion_binario, camion_ids, palets_binario, palets_ids,
               n_palets_usados, n_paradas, total_cajas, ocupacion_pct
        FROM resultado_carga_camion
        WHERE id_ruta_algoritmo = ?
    """, (id_ruta,))
    fila = cursor.fetchone()

    if not fila:
        raise ValueError(f"No hay resultado de carga para la ruta: {id_ruta}")

    camion_bin, camion_ids, palets_bin, palets_ids, n_palets, n_paradas, total, ocup = fila

    return {
        "camion_binario": np.array(json.loads(camion_bin)),
        "camion_ids":     np.array(json.loads(camion_ids)),
        "palets_binario": np.array(json.loads(palets_bin)),
        "palets_ids":     np.array(json.loads(palets_ids)),
        "meta": {
            "n_palets_usados": n_palets,
            "n_paradas": n_paradas,
            "total_cajas": total,
            "ocupacion_pct": ocup,
        }
    }


# ─── Uso directo ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    crear_tabla(conn)

    cursor = conn.execute(
        "SELECT DISTINCT id_ruta_algoritmo FROM resultado_rutas_ortools"
    )
    rutas = [r[0] for r in cursor.fetchall()]

    for id_ruta in rutas:
        try:
            resultado = guardar_resultado(conn, id_ruta)
            print(f"OK  {resultado}")
        except Exception as e:
            print(f"ERR {id_ruta}: {e}")

    conn.close()
