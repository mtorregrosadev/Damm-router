"""
API async de generación de matrices de carga.

Interfaz principal:
    await generar_carga(id_ruta, ids_parada)

Entradas:
    id_ruta   : str        — "fecha|transporte|ruta"  e.g. "19/03/2026|11588007|DR0016"
    ids_parada: list[str]  — IDs de destinatario EN ORDEN de entrega

Salida (dict) — documento guardado en MongoDB colección 'resultado_carga_camion':
    id_ruta_algoritmo, generado_en, version, n_paradas, n_camiones,
    total_cajas, estado_procesamiento, paradas[], camiones[]

    Cada camión incluye (campos existentes más los nuevos):
      camion_tipo, camion_ids, n_palets_usados, n_cajas, ocupacion_pct,
      capacidad_total, dimensiones, resumen_inicial, paradas_asignadas,
      estados_por_parada[]

Reglas de material (un_medida_venta):
    CAJ  → caja
    BRL  → barril
    PAL  → 60 cajas
    CJ13 → caja vacía (recogida durante la ruta)
    UN, BOT → ignorar
"""

import asyncio
try:
    from src.alghoritms.truck_loader import cargar_camion, CAMION_COLS, CAMION_FILAS, PALET_CAP
except ImportError:
    from truck_loader import cargar_camion, CAMION_COLS, CAMION_FILAS, PALET_CAP

try:
    from src.db.mongo import get_db
except ImportError:
    from mongo import get_db

CAPACIDAD_CAMION = CAMION_COLS * CAMION_FILAS * PALET_CAP  # 360
_PAL_UNIDADES = 60
_VERSION = "2.0"


# ─── Helpers síncronos ────────────────────────────────────────────────────────

def _cargas_parada(transporte: str, id_parada: str) -> dict:
    """
    Consulta MongoDB: unidades por tipo para una parada.

    Returns:
        {
          "cajas": int, "barriles": int, "cj13": int,
          "nombre": str | None,
          "materiales_originales": [{"un_medida_venta": str, "cantidad": int}, ...]
        }
    """
    docs = list(get_db()["detalle_entrega"].find(
        {"destinatario_mc_a_1": id_parada, "transporte": transporte},
        {"un_medida_venta": 1, "cantidad_entrega": 1, "nombre_1": 1, "_id": 0},
    ))

    nombre: str | None = None
    cajas = barriles = cj13 = 0
    materiales_originales: list[dict] = []

    for doc in docs:
        if nombre is None and doc.get("nombre_1"):
            nombre = str(doc["nombre_1"]).strip()

        um = str(doc.get("un_medida_venta", "")).strip().upper()
        try:
            qty = float(str(doc.get("cantidad_entrega", "0")).replace(",", "."))
        except ValueError:
            qty = 0.0
        qty = max(0, int(qty))

        materiales_originales.append({"un_medida_venta": um, "cantidad": qty})

        if um == "CAJ":
            cajas += qty
        elif um == "BRL":
            barriles += qty
        elif um == "PAL":
            cajas += qty * _PAL_UNIDADES
        elif um == "CJ13":
            cj13 += qty
        # UN, BOT → ignorar

    # Garantía mínima: si la parada tiene docs pero todo era UN/BOT,
    # contamos al menos 1 caja para no dejar la parada en blanco.
    if cajas == 0 and barriles == 0 and cj13 == 0 and docs:
        cajas = 1

    return {
        "cajas":                 cajas,
        "barriles":              barriles,
        "cj13":                  cj13,
        "nombre":                nombre,
        "materiales_originales": materiales_originales,
    }


def _dividir_en_camiones(
    ids_parada: list[str],
    cargas: list[dict],
) -> list[list[tuple[str, dict]]]:
    """
    Agrupa paradas en camiones respetando la capacidad máxima (360 unidades).
    Cada elemento de cargas: {"cajas": int, "barriles": int, "cj13": int, ...}
    """
    camiones: list[list[tuple[str, dict]]] = []
    camion_actual: list[tuple[str, dict]] = []
    total_camion = 0

    for id_p, carga in zip(ids_parada, cargas):
        total_parada = carga["cajas"] + carga["barriles"] + carga["cj13"]
        total_parada = min(total_parada, CAPACIDAD_CAMION)

        if total_camion + total_parada > CAPACIDAD_CAMION and camion_actual:
            camiones.append(camion_actual)
            camion_actual = []
            total_camion = 0

        camion_actual.append((id_p, carga))
        total_camion += total_parada

    if camion_actual:
        camiones.append(camion_actual)

    return camiones


def _matrices_camion(grupo: list[tuple[str, dict]], offset_orden: int) -> dict:
    """Genera matrices tipo+ids y estados por parada para un grupo de paradas (un camión)."""
    paradas_local = list(range(1, len(grupo) + 1))

    cajas_local    = {i+1: g["cajas"]    for i, (_, g) in enumerate(grupo)}
    barriles_local = {i+1: g["barriles"] for i, (_, g) in enumerate(grupo)}
    cj13_local     = {i+1: g["cj13"]     for i, (_, g) in enumerate(grupo)}

    # Ignorar cj13_local si todos son 0 para no penalizar palets
    if not any(cj13_local.values()):
        cj13_local = None

    p_tipo_local, p_ids_local, t_tipo_local, t_ids_local = cargar_camion(
        paradas_local, cajas_local, barriles_local, cj13_local
    )

    # Traducir IDs locales (1..N) → orden global en la ruta
    t_tipo = t_tipo_local.copy()
    t_ids  = np.zeros_like(t_ids_local)
    p_ids  = np.zeros_like(p_ids_local)

    for local in paradas_local:
        global_orden = local + offset_orden
        t_ids[t_ids_local == local] = global_orden
        p_ids[p_ids_local == local] = global_orden

    total_entrega = sum(cajas_local.values()) + sum(barriles_local.values())
    n_palets = int(((p_ids_local > 0).sum(axis=(1, 2, 3)) > 0).sum())

    paradas_globales = [local + offset_orden for local in paradas_local]
    estados          = generar_estados_por_parada(t_tipo, t_ids, paradas_globales)

    return {
        # ── Campos existentes (compatibilidad garantizada) ────────────────
        "camion_tipo":     t_tipo.tolist(),
        "camion_ids":      t_ids.tolist(),
        "n_palets_usados": n_palets,
        "n_cajas":         total_entrega,
        "ocupacion_pct":   round(100 * total_entrega / CAPACIDAD_CAMION, 1),
        # ── Campos nuevos ─────────────────────────────────────────────────
        "capacidad_total":    CAPACIDAD_CAMION,
        "dimensiones":        {"x": 8, "y": 9, "z": 5},
        "resumen_inicial":    resumen_tipo(t_tipo),
        "paradas_asignadas":  paradas_globales,
        "estados_por_parada": estados,
    }


def _guardar_mongo(id_ruta: str, doc: dict) -> None:
    get_db()["resultado_carga_camion"].replace_one(
        {"id_ruta_algoritmo": id_ruta}, doc, upsert=True
    )


# ─── API pública ──────────────────────────────────────────────────────────────

async def generar_carga(id_ruta: str, ids_parada: list[str]) -> dict:
    """
    Genera las matrices de carga para una ruta y las guarda en MongoDB.

    Args:
        id_ruta:    "fecha|transporte|ruta"
        ids_parada: IDs de destinatario EN ORDEN de entrega

    Returns dict con todos los datos de la ruta, camiones y estados por parada.
    Retrocompatible: no elimina campos existentes.
    """
    partes = id_ruta.split("|")
    transporte = partes[1] if len(partes) >= 2 else ""

    # Consultar cargas de todas las paradas en paralelo
    cargas: list[dict] = await asyncio.gather(*[
        asyncio.to_thread(_cargas_parada, transporte, id_p)
        for id_p in ids_parada
    ])

    grupos = _dividir_en_camiones(ids_parada, cargas)

    # Mapeo orden_global → n_camion (para asignar cada parada a su camión)
    orden_to_camion: dict[int, int] = {}
    _global = 1
    for n_cam, grupo in enumerate(grupos, start=1):
        for _ in grupo:
            orden_to_camion[_global] = n_cam
            _global += 1

    # Generar matrices de cada camión en paralelo
    offset = 0
    tareas = []
    for grupo in grupos:
        tareas.append(asyncio.to_thread(_matrices_camion, grupo, offset))
        offset += len(grupo)

    matrices_por_camion = await asyncio.gather(*tareas)

    camiones = [{"n_camion": n, **mat}
                for n, mat in enumerate(matrices_por_camion, start=1)]

    total_cajas = sum(c["cajas"] + c["barriles"] for c in cargas)

    doc = {
        # ── Metadata ──────────────────────────────────────────────────────
        "id_ruta_algoritmo":    id_ruta,
        "generado_en":          datetime.now(timezone.utc).isoformat(),
        "version":              _VERSION,
        "estado_procesamiento": "completado",
        # ── Resumen general ───────────────────────────────────────────────
        "n_paradas":   len(ids_parada),
        "n_camiones":  len(camiones),
        "total_cajas": total_cajas,
        # ── Paradas ───────────────────────────────────────────────────────
        "paradas": [
            {
                "orden":           i + 1,
                "id_destinatario": id_p,
                "nombre":          c.get("nombre"),
                "cajas":           c["cajas"],
                "barriles":        c["barriles"],
                "cj13":            c["cj13"],
                "tiene_descarga":        (c["cajas"] + c["barriles"]) > 0,
                "tiene_carga_cj13":      c["cj13"] > 0,
                "tiene_descarga_y_carga": (c["cajas"] + c["barriles"]) > 0 and c["cj13"] > 0,
                "n_camion":              orden_to_camion[i + 1],
                "materiales_originales": c.get("materiales_originales", []),
            }
            for i, (id_p, c) in enumerate(zip(ids_parada, cargas))
        ],
        # ── Camiones ──────────────────────────────────────────────────────
        "camiones": camiones,
    }

    await asyncio.to_thread(_guardar_mongo, id_ruta, doc)
    return doc


async def procesar_rutas(rutas: list[tuple[str, list[str]]]) -> list[dict]:
    """Procesa múltiples rutas en paralelo."""
    return await asyncio.gather(*[
        generar_carga(id_ruta, ids_parada)
        for id_ruta, ids_parada in rutas
    ])
