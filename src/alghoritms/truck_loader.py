"""
Sistema de optimización de carga de camiones con matrices 3D.
Camión Estrella Damm — APERTURA LATERAL (ambos lados).

Doble matriz por posición:
  tipo  → 0=vacío  1=caja  2=barril  3=CJ13 (caja vacía cargada en ruta)
  ids   → 0=vacío  N=parada propietaria

Dimensiones:
  Palet:  X=4 × Y=3 × Z=5 = 60 unidades
  Camión: 2 columnas × 3 filas = 6 palets = 360 unidades

Restricción física: ningún barril puede estar encima de una caja
en la misma columna (x, y). Garantizado por algoritmo de doble pasada.
"""

import numpy as np
from math import ceil
from typing import List, Dict, Tuple, Optional


# ─── Constantes ───────────────────────────────────────────────────────────────

PALET_X: int = 4
PALET_Y: int = 3
PALET_Z: int = 5
PALET_CAP: int = PALET_X * PALET_Y * PALET_Z  # 60

CAMION_COLS: int = 2
CAMION_FILAS: int = 3

TIPO_VACIO:  int = 0
TIPO_CAJA:   int = 1
TIPO_BARRIL: int = 2
TIPO_CJ13:   int = 3


# ─── Avance de posición ───────────────────────────────────────────────────────

def _avanzar(p: int, x: int, y: int, z: int) -> Tuple[int, int, int, int]:
    """Avanza una posición en orden x→y→z→siguiente palet."""
    x += 1
    if x == PALET_X:
        x = 0
        y += 1
    if y == PALET_Y:
        y = 0
        z += 1
    if z == PALET_Z:
        p += 1
        x, y, z = 0, 0, 0
    return p, x, y, z


# ─── Fase 1: Llenado de palets ────────────────────────────────────────────────

def llenar_palets(
    paradas: List[int],
    cajas_por_parada: Dict[int, int],
    barriles_por_parada: Dict[int, int],
    cj13_por_parada: Optional[Dict[int, int]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rellena los palets con doble pasada: barriles primero, cajas después.

    Garantía física: en cualquier columna (x, y), todos los barriles tienen
    z ≤ z de todas las cajas → nunca un barril encima de una caja.

    Garantía logística: dentro de cada tipo, última parada → z bajo
    (fondo, descarga tardía) y primera parada → z alto (techo, 1ª descarga).

    CJ13: posiciones vacías, preferiblemente adyacentes a posiciones de
    paradas anteriores (zonas que estarán libres cuando llegue esa parada).

    Returns:
        tipo (N_palets, X, Y, Z): 0/1/2/3
        ids  (N_palets, X, Y, Z): ID de parada (0 = vacío)
    """
    if cj13_por_parada is None:
        cj13_por_parada = {}

    total_entrega = (sum(cajas_por_parada.values())
                     + sum(barriles_por_parada.values()))
    total_cj13 = sum(cj13_por_parada.values())
    total = total_entrega + total_cj13
    n_palets = max(1, ceil(total / PALET_CAP))

    tipo = np.zeros((n_palets, PALET_X, PALET_Y, PALET_Z), dtype=np.int32)
    ids  = np.zeros((n_palets, PALET_X, PALET_Y, PALET_Z), dtype=np.int32)

    p, x, y, z = 0, 0, 0, 0

    # Pasada A — barriles (última parada → posición más baja, z=0)
    for id_parada in reversed(paradas):
        restantes = barriles_por_parada.get(id_parada, 0)
        while restantes > 0:
            tipo[p, x, y, z] = TIPO_BARRIL
            ids[p, x, y, z]  = id_parada
            restantes -= 1
            p, x, y, z = _avanzar(p, x, y, z)

    # Pasada B — cajas (continúan desde donde dejaron los barriles)
    for id_parada in reversed(paradas):
        restantes = cajas_por_parada.get(id_parada, 0)
        while restantes > 0:
            tipo[p, x, y, z] = TIPO_CAJA
            ids[p, x, y, z]  = id_parada
            restantes -= 1
            p, x, y, z = _avanzar(p, x, y, z)

    # Fase CJ13
    if cj13_por_parada:
        _colocar_cj13(tipo, ids, paradas, cj13_por_parada)

    return tipo, ids


def _colocar_cj13(
    tipo: np.ndarray,
    ids: np.ndarray,
    paradas: List[int],
    cj13_por_parada: Dict[int, int],
) -> None:
    """Marca posiciones vacías con CJ13. Modifica tipo e ids in-place."""
    n_palets, PX, PY, PZ = tipo.shape

    for k_idx, stop_k in enumerate(paradas):
        n_cj13 = cj13_por_parada.get(stop_k, 0)
        if n_cj13 == 0:
            continue

        paradas_anteriores = set(paradas[:k_idx])
        preferidos: List[Tuple] = []
        fallback:   List[Tuple] = []

        for pp in range(n_palets):
            for xx in range(PX):
                for yy in range(PY):
                    for zz in range(PZ):
                        if tipo[pp, xx, yy, zz] != TIPO_VACIO:
                            continue
                        if _tiene_vecino_anterior(
                            ids, pp, xx, yy, zz, n_palets, PX, PY, PZ,
                            paradas_anteriores
                        ):
                            preferidos.append((pp, xx, yy, zz))
                        else:
                            fallback.append((pp, xx, yy, zz))

        colocados = 0
        for pos in preferidos + fallback:
            if colocados >= n_cj13:
                break
            pp, xx, yy, zz = pos
            if tipo[pp, xx, yy, zz] == TIPO_VACIO:
                tipo[pp, xx, yy, zz] = TIPO_CJ13
                ids[pp, xx, yy, zz]  = stop_k
                colocados += 1


def _tiene_vecino_anterior(
    ids: np.ndarray,
    p: int, x: int, y: int, z: int,
    n_palets: int, PX: int, PY: int, PZ: int,
    paradas_anteriores: set,
) -> bool:
    for dp, dx, dy, dz in [
        (0,1,0,0),(0,-1,0,0),(0,0,1,0),(0,0,-1,0),(0,0,0,1),(0,0,0,-1),
    ]:
        np_, nx, ny, nz = p+dp, x+dx, y+dy, z+dz
        if (0 <= np_ < n_palets and 0 <= nx < PX
                and 0 <= ny < PY and 0 <= nz < PZ):
            if ids[np_, nx, ny, nz] in paradas_anteriores:
                return True
    return False


# ─── Fase 2: Emparejamiento de palets por fila ────────────────────────────────

def _info_palet(ids_palet: np.ndarray) -> Tuple[int, int, float]:
    vals = ids_palet[ids_palet > 0]
    if len(vals) == 0:
        return (9999, 9999, 9999.0)
    unique, counts = np.unique(vals, return_counts=True)
    return int(unique.min()), int(unique[np.argmax(counts)]), float(np.mean(vals))


def emparejar_palets(ids: np.ndarray) -> List[Tuple[int, Optional[int]]]:
    """Agrupa palets en pares (col0, col1) optimizando descarga simultánea."""
    info = [(i, *_info_palet(ids[i])) for i in range(len(ids))]
    info.sort(key=lambda t: (t[1], t[2], t[3]))
    indices = [t[0] for t in info]
    pares: List[Tuple[int, Optional[int]]] = []
    for i in range(0, len(indices), 2):
        pares.append((indices[i], indices[i+1] if i+1 < len(indices) else None))
    return pares


# ─── Fase 3: Ensamblado en matrices del camión ───────────────────────────────

def ensamblar_camion(
    tipo: np.ndarray,
    ids: np.ndarray,
    cols: int = CAMION_COLS,
    filas: int = CAMION_FILAS,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Ensambla los palets en las matrices 3D del camión completo.

    Returns:
        camion_tipo (cols*X, filas*Y, Z)
        camion_ids  (cols*X, filas*Y, Z)
    """
    tx = cols  * PALET_X
    ty = filas * PALET_Y

    camion_tipo = np.zeros((tx, ty, PALET_Z), dtype=np.int32)
    camion_ids  = np.zeros((tx, ty, PALET_Z), dtype=np.int32)

    pares = emparejar_palets(ids)

    for fila, (idx_izq, idx_der) in enumerate(pares):
        if fila >= filas:
            break
        yo = fila * PALET_Y

        camion_tipo[0:PALET_X, yo:yo+PALET_Y, :]          = tipo[idx_izq]
        camion_ids [0:PALET_X, yo:yo+PALET_Y, :]          = ids [idx_izq]

        if idx_der is not None:
            camion_tipo[PALET_X:2*PALET_X, yo:yo+PALET_Y, :] = tipo[idx_der]
            camion_ids [PALET_X:2*PALET_X, yo:yo+PALET_Y, :] = ids [idx_der]

    return camion_tipo, camion_ids


# ─── Pipeline principal ───────────────────────────────────────────────────────

def cargar_camion(
    paradas: List[int],
    cajas_por_parada: Dict[int, int],
    barriles_por_parada: Dict[int, int],
    cj13_por_parada: Optional[Dict[int, int]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Pipeline completo: llenar → emparejar → ensamblar.

    Args:
        paradas:             IDs en orden de entrega [1, 2, ..., N]
        cajas_por_parada:    {id_parada: num_cajas}
        barriles_por_parada: {id_parada: num_barriles}
        cj13_por_parada:     {id_parada: num_cajas_vacias}  (opcional)

    Returns:
        palet_tipo  (N, X, Y, Z): uso interno
        palet_ids   (N, X, Y, Z): uso interno
        camion_tipo (8, 9, 5):    sale a la web
        camion_ids  (8, 9, 5):    sale a la web
    """
    capacidad = CAMION_COLS * CAMION_FILAS * PALET_CAP
    total = (sum(cajas_por_parada.values())
             + sum(barriles_por_parada.values())
             + sum((cj13_por_parada or {}).values()))

    if total > capacidad:
        raise ValueError(
            f"Overflow: {total} unidades > capacidad del camión {capacidad}"
        )

    p_tipo, p_ids = llenar_palets(
        paradas, cajas_por_parada, barriles_por_parada, cj13_por_parada
    )
    t_tipo, t_ids = ensamblar_camion(p_tipo, p_ids)
    return p_tipo, p_ids, t_tipo, t_ids


# ─── Utilidades de visualización ─────────────────────────────────────────────

_SIM = {TIPO_VACIO: '·', TIPO_CAJA: 'C', TIPO_BARRIL: 'B', TIPO_CJ13: 'V'}


def ver_camion_lateral(
    camion_tipo: np.ndarray, camion_ids: np.ndarray, z: int
) -> None:
    etiquetas = {PALET_Z-1: f"TECHO Z={PALET_Z-1} (1ª descarga)", 0: "SUELO Z=0 (última)"}
    print(f"\nCamión — {etiquetas.get(z, f'CAPA Z={z}')}")
    print(f"  {'LAT. IZQ (col 0)':^22}  {'LAT. DER (col 1)':^22}")
    print("-" * 52)
    for fila in range(CAMION_FILAS):
        y0 = fila * PALET_Y
        print(f"  --- Fila {fila} ---")
        for y in range(PALET_Y):
            def _render(x_range):
                return " ".join(
                    f"{_SIM[camion_tipo[x,y0+y,z]]}{camion_ids[x,y0+y,z]:02d}"
                    if camion_ids[x,y0+y,z] else "  · "
                    for x in x_range
                )
            print(f"  [{_render(range(PALET_X))}]  [{_render(range(PALET_X,2*PALET_X))}]")


def resumen(
    paradas: List[int],
    cajas_por_parada: Dict[int, int],
    barriles_por_parada: Dict[int, int],
    cj13_por_parada: Optional[Dict[int, int]],
    p_tipo: np.ndarray,
    p_ids: np.ndarray,
) -> None:
    if cj13_por_parada is None:
        cj13_por_parada = {}
    total = (sum(cajas_por_parada.values())
             + sum(barriles_por_parada.values())
             + sum(cj13_por_parada.values()))
    pares = emparejar_palets(p_ids)

    print("=" * 65)
    print("PLAN DE CARGA — CAMIÓN APERTURA LATERAL")
    print("=" * 65)
    print(f"  Paradas       : {paradas}")
    print(f"  Cajas entrega : {sum(cajas_por_parada.values())}")
    print(f"  Barriles      : {sum(barriles_por_parada.values())}")
    print(f"  CJ13 recogida : {sum(cj13_por_parada.values())}")
    print(f"  Total         : {total}")
    print(f"  Palets usados : {len(p_tipo)} / {CAMION_COLS * CAMION_FILAS}")
    print(f"  Ocupación     : {100*total/(CAMION_COLS*CAMION_FILAS*PALET_CAP):.1f}%")
    print()
    print("  LATERAL IZQ (col 0)              LATERAL DER (col 1)")
    print("-" * 65)
    for fila, (idx_izq, idx_der) in enumerate(pares):
        def _desc(idx):
            if idx is None:
                return "[  VACÍO  ]"
            vals = p_ids[idx][p_ids[idx] > 0]
            stops = sorted(int(v) for v in np.unique(vals))
            nc = int(np.sum(p_tipo[idx] == TIPO_CAJA))
            nb = int(np.sum(p_tipo[idx] == TIPO_BARRIL))
            nv = int(np.sum(p_tipo[idx] == TIPO_CJ13))
            return f"Pal {idx} stops={stops} C={nc} B={nb} V={nv}"
        print(f"  Fila {fila}: {_desc(idx_izq):<32} {_desc(idx_der)}")
    print("=" * 65)


# ─── Ejemplo standalone ───────────────────────────────────────────────────────

if __name__ == "__main__":
    paradas  = [1, 2, 3, 4]
    cajas    = {1: 10, 2: 30, 3: 40, 4: 20}
    barriles = {1:  5, 2:  0, 3: 10, 4:  5}
    cj13     = {2:  6, 4:  4}

    p_tipo, p_ids, t_tipo, t_ids = cargar_camion(paradas, cajas, barriles, cj13)
    resumen(paradas, cajas, barriles, cj13, p_tipo, p_ids)
    for z in range(PALET_Z - 1, -1, -1):
        ver_camion_lateral(t_tipo, t_ids, z)
