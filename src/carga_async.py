"""
API async de generación de matrices de carga.

Interfaz principal:
    await generar_carga(id_ruta, ids_parada)

Tu compañero publica rutas en la DB → este código corre en paralelo,
lee las cajas por parada y genera + guarda las matrices en MongoDB.

Entradas:
    id_ruta   : str        — "fecha|transporte|ruta"  e.g. "19/03/2026|11588007|DR0016"
    ids_parada: list[str]  — IDs de destinatario EN ORDEN de entrega
                             e.g. ["9100087801", "9100559291", ...]

Salida (dict):
    camion_binario  — array 3D  [8][9][5]  con 0/1
    camion_ids      — array 3D  [8][9][5]  con ID de parada (orden en la ruta)
    palets_binario  — array 4D  [N][4][3][5]
    palets_ids      — array 4D  [N][4][3][5]
    meta            — {n_palets_usados, n_paradas, total_cajas, ocupacion_pct}
"""

import asyncio
import sqlite3
from pathlib import Path

from truck_loader import cargar_camion, CAMION_COLS, CAMION_FILAS, PALET_CAP
from mongo import get_db

DB_PATH = Path(__file__).parent.parent / "hackaton.db"
CAPACIDAD_CAMION = CAMION_COLS * CAMION_FILAS * PALET_CAP  # 360 cajas


# ─── Helpers síncronos (se ejecutan en threads para no bloquear el loop) ──────

def _cajas_parada(transporte: str, id_parada: str) -> int:
    """Consulta SQLite: total de cajas de una parada en un transporte."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(CAST(cantidad_entrega AS REAL)), 0)
            FROM detalle_entrega
            WHERE destinatario_mc_a_1 = ?
              AND transporte           = ?
            """,
            (id_parada, transporte),
        ).fetchone()
        return max(1, int(row[0]))
    finally:
        conn.close()


def _dividir_en_camiones(
    ids_parada: list[str], cantidades: list[int]
) -> list[list[tuple[str, int]]]:
    """
    Agrupa paradas en camiones respetando la capacidad máxima.
    Devuelve lista de camiones, cada uno con lista de (id_parada, cajas).
    """
    camiones: list[list[tuple[str, int]]] = []
    camion_actual: list[tuple[str, int]] = []
    cajas_camion = 0

    for id_p, cajas in zip(ids_parada, cantidades):
        cajas = min(cajas, CAPACIDAD_CAMION)  # una parada no puede superar 1 camión
        if cajas_camion + cajas > CAPACIDAD_CAMION and camion_actual:
            camiones.append(camion_actual)
            camion_actual = []
            cajas_camion = 0
        camion_actual.append((id_p, cajas))
        cajas_camion += cajas

    if camion_actual:
        camiones.append(camion_actual)

    return camiones


def _matrices_camion(grupo: list[tuple[str, int]], offset_orden: int) -> dict:
    """Genera matrices para un grupo de paradas (un camión)."""
    paradas_local = list(range(1, len(grupo) + 1))
    cajas_local   = {i + 1: cajas for i, (_, cajas) in enumerate(grupo)}

    p_bin, p_ids_local, t_bin, t_ids_local = cargar_camion(paradas_local, cajas_local)

    # Traducir IDs locales (1..N) → orden global en la ruta
    import numpy as np
    t_ids = np.zeros_like(t_ids_local)
    p_ids = np.zeros_like(p_ids_local)
    for local in paradas_local:
        global_orden = local + offset_orden
        t_ids[t_ids_local == local] = global_orden
        p_ids[p_ids_local == local] = global_orden

    total = sum(cajas_local.values())
    n_palets = int((p_bin.sum(axis=(1, 2, 3)) > 0).sum())

    return {
        "camion_binario": t_bin.tolist(),
        "camion_ids":     t_ids.tolist(),
        "palets_binario": p_bin.tolist(),
        "palets_ids":     p_ids.tolist(),
        "n_palets_usados": n_palets,
        "n_cajas":         total,
        "ocupacion_pct":   round(100 * total / CAPACIDAD_CAMION, 1),
    }


def _guardar_mongo(id_ruta: str, doc: dict) -> None:
    get_db()["resultado_carga_camion"].replace_one(
        {"id_ruta_algoritmo": id_ruta}, doc, upsert=True
    )


# ─── API pública ──────────────────────────────────────────────────────────────

async def generar_carga(id_ruta: str, ids_parada: list[str]) -> dict:
    """
    Genera las matrices de carga para una ruta y las guarda en MongoDB.
    Si la ruta necesita más de un camión, devuelve uno por camión en 'camiones'.

    Args:
        id_ruta:    "fecha|transporte|ruta"  e.g. "19/03/2026|11588007|DR0016"
        ids_parada: IDs de destinatario EN ORDEN de entrega

    Returns dict con:
        paradas    — lista con orden, id, cajas de cada parada
        n_camiones — cuántos camiones necesita la ruta
        camiones   — lista de matrices (una entrada por camión)
    """
    partes = id_ruta.split("|")
    transporte = partes[1] if len(partes) >= 2 else ""

    # Cajas de todas las paradas en paralelo
    cantidades: list[int] = await asyncio.gather(*[
        asyncio.to_thread(_cajas_parada, transporte, id_p)
        for id_p in ids_parada
    ])

    # Dividir en camiones si hace falta
    grupos = _dividir_en_camiones(ids_parada, cantidades)

    # Generar matrices de cada camión en paralelo (CPU en threads)
    offset = 0
    tareas_matrices = []
    for grupo in grupos:
        tareas_matrices.append(
            asyncio.to_thread(_matrices_camion, grupo, offset)
        )
        offset += len(grupo)

    matrices_por_camion = await asyncio.gather(*tareas_matrices)

    # Añadir número de camión
    camiones = []
    for n, mat in enumerate(matrices_por_camion, start=1):
        camiones.append({"n_camion": n, **mat})

    doc = {
        "id_ruta_algoritmo": id_ruta,
        "paradas": [
            {"orden": i + 1, "id_destinatario": id_p, "cajas": c}
            for i, (id_p, c) in enumerate(zip(ids_parada, cantidades))
        ],
        "n_camiones":  len(camiones),
        "camiones":    camiones,
        "total_cajas": sum(cantidades),
        "n_paradas":   len(ids_parada),
    }

    await asyncio.to_thread(_guardar_mongo, id_ruta, doc)
    return doc


async def procesar_rutas(rutas: list[tuple[str, list[str]]]) -> list[dict]:
    """
    Procesa múltiples rutas en paralelo.

    Args:
        rutas: lista de (id_ruta, ids_parada)

    Returns:
        Lista de resultados en el mismo orden.
    """
    return await asyncio.gather(*[
        generar_carga(id_ruta, ids_parada)
        for id_ruta, ids_parada in rutas
    ])


# ─── Ejemplo de uso ───────────────────────────────────────────────────────────

async def _demo():
    # Simula lo que te manda tu compañero:
    #   id_ruta + ids de parada en orden de entrega
    id_ruta = "19/03/2026|11588007|DR0016"
    ids_parada = [
        "9100087801",
        "9100559291",
        "9100480482",
        "9100698912",
        "9100521678",
    ]

    print(f"Procesando ruta: {id_ruta}")
    resultado = await generar_carga(id_ruta, ids_parada)

    meta = resultado["meta"]
    print(f"  Paradas   : {meta['n_paradas']}")
    print(f"  Cajas     : {meta['total_cajas']}")
    print(f"  Palets    : {meta['n_palets_usados']}")
    print(f"  Ocupación : {meta['ocupacion_pct']}%")
    print(f"  Shape camion_binario: {len(resultado['camion_binario'])}x"
          f"{len(resultado['camion_binario'][0])}x"
          f"{len(resultado['camion_binario'][0][0])}")
    print("  Guardado en MongoDB ✓")


if __name__ == "__main__":
    asyncio.run(_demo())
