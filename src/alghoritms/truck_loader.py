"""
Sistema de optimización de carga de camiones con matrices 3D.
Adaptado para camión Estrella Damm con APERTURA LATERAL (ambos lados).

╔══════════════════════════════════════════════════════════════╗
║  MODELO DE ACCESO — APERTURA LATERAL                        ║
║                                                              ║
║  LATERAL IZQUIERDO          LATERAL DERECHO                 ║
║  ← acceso                          acceso →                 ║
║  ┌──────────┬──────────┐                                    ║
║  │  col 0   │  col 1   │                                    ║
║  │ [Palet A]│[Palet B] │  fila 0                           ║
║  │ [Palet C]│[Palet D] │  fila 1                           ║
║  │ [Palet E]│[Palet F] │  fila 2                           ║
║  └──────────┴──────────┘                                    ║
║                                                              ║
║  Con apertura lateral, TODOS los palets son igualmente      ║
║  accesibles desde cualquiera de los dos lados.              ║
║  El criterio de optimización cambia:                        ║
║    → Agrupar palets del mismo pedido en la misma FILA       ║
║    → Permite descargar ambos lados a la vez (col0 + col1)   ║
║                                                              ║
║  Lo que NO cambia: ordenación VERTICAL dentro de cada palet ║
║    z=0 (suelo) = paradas tardías (últimas en descargar)     ║
║    z=2 (techo) = paradas tempranas (primeras en descargar)  ║
╚══════════════════════════════════════════════════════════════╝

Dimensiones:
  Palet:  X=4 × Y=3 × Z=5 (alto) = 60 cajas
  Camión: 2 columnas × 3 filas = 6 palets = 360 cajas
"""

import numpy as np
from math import ceil
from typing import List, Dict, Tuple, Optional


# ─── Constantes ───────────────────────────────────────────────────────────────

PALET_X: int = 4
PALET_Y: int = 3
PALET_Z: int = 5   # alto — el único que importa para el orden de descarga
PALET_CAP: int = PALET_X * PALET_Y * PALET_Z  # 60 cajas

CAMION_COLS: int = 2   # palets lado a lado (izquierdo / derecho)
CAMION_FILAS: int = 3  # palets a lo largo del camión


# ─── Fase 1: Llenado de palets ────────────────────────────────────────────────

def llenar_palets(
    paradas: List[int],
    cajas_por_parada: Dict[int, int],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rellena los palets respetando el orden de descarga vertical.

    Regla invariante: dentro de cualquier columna (x, y) de un palet,
    el ID de parada es NO CRECIENTE de z=0 a z=2.
    Esto garantiza que las cajas de paradas tempranas siempre quedan
    encima de las de paradas tardías, independientemente del acceso lateral.

    Orden de avance de posición: x → y → z → siguiente palet

    Args:
        paradas:          IDs de parada en orden de entrega [1, 2, ..., N]
        cajas_por_parada: {id_parada: num_cajas}

    Returns:
        binario (N_palets, X, Y, Z): 1 donde hay caja, 0 vacío
        ids     (N_palets, X, Y, Z): ID de parada en cada posición ocupada
    """
    total = sum(cajas_por_parada.values())
    n_palets = ceil(total / PALET_CAP)

    binario = np.zeros((n_palets, PALET_X, PALET_Y, PALET_Z), dtype=np.int32)
    ids = np.zeros((n_palets, PALET_X, PALET_Y, PALET_Z), dtype=np.int32)

    p, x, y, z = 0, 0, 0, 0

    for id_parada in reversed(paradas):   # última parada → fondo del palet
        restantes = cajas_por_parada[id_parada]
        while restantes > 0:
            binario[p, x, y, z] = 1
            ids[p, x, y, z] = id_parada
            restantes -= 1

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

    return binario, ids


# ─── Fase 2: Emparejamiento de palets por fila (optimización lateral) ─────────

def _info_palet(ids_palet: np.ndarray) -> Tuple[int, int, float]:
    """
    Devuelve (stop_minimo, stop_dominante, media_ponderada) de un palet.
    stop_minimo    = parada más temprana que contiene (prioridad de acceso).
    stop_dominante = parada con más cajas (identidad del palet).
    """
    vals = ids_palet[ids_palet > 0]
    if len(vals) == 0:
        return (9999, 9999, 9999.0)
    unique, counts = np.unique(vals, return_counts=True)
    stop_min = int(unique.min())
    stop_dom = int(unique[np.argmax(counts)])
    media = float(np.mean(vals))
    return stop_min, stop_dom, media


def emparejar_palets(ids: np.ndarray) -> List[Tuple[int, Optional[int]]]:
    """
    Fase 2 — exclusiva de apertura lateral.

    Agrupa los palets en pares (lateral_izquierdo, lateral_derecho) para
    maximizar la descarga simultánea por ambos lados en cada parada.

    Estrategia:
      1. Ordenar palets por (stop_mínimo_presente, stop_dominante, media)
         → los palets con entregas más tempranas quedan primero
      2. Emparejar de 2 en 2: cada par ocupa una fila del camión
         → los dos palets de la misma fila idealmente pertenecen al mismo stop

    Returns:
        Lista de tuplas (idx_palet_col0, idx_palet_col1 | None) por fila.
    """
    n = len(ids)
    info = [(i, *_info_palet(ids[i])) for i in range(n)]
    # Ordenar: stop_min ASC, luego stop_dom ASC, luego media ASC
    info.sort(key=lambda t: (t[1], t[2], t[3]))

    pares: List[Tuple[int, Optional[int]]] = []
    indices = [t[0] for t in info]
    for i in range(0, len(indices), 2):
        izq = indices[i]
        der = indices[i + 1] if i + 1 < len(indices) else None
        pares.append((izq, der))

    return pares


# ─── Fase 3: Ensamblado en matrices del camión ───────────────────────────────

def ensamblar_camion(
    binario: np.ndarray,
    ids: np.ndarray,
    cols: int = CAMION_COLS,
    filas: int = CAMION_FILAS,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Construye las matrices 3D completas del camión a partir de los palets.

    Disposición con apertura lateral (vista desde arriba):

        LATERAL IZQ      LATERAL DER
           col 0            col 1
    fila 0 [Pal A]  ←→  [Pal B]   ← misma fila = descarga simultánea
    fila 1 [Pal C]  ←→  [Pal D]
    fila 2 [Pal E]  ←→  [Pal F]

    Cada fila recibe los dos palets del mismo pedido (emparejados en Fase 2).

    Returns:
        camion_bin (cols*X, filas*Y, Z): 0/1
        camion_ids (cols*X, filas*Y, Z): ID de parada
    """
    tx = cols * PALET_X
    ty = filas * PALET_Y
    tz = PALET_Z

    camion_bin = np.zeros((tx, ty, tz), dtype=np.int32)
    camion_ids = np.zeros((tx, ty, tz), dtype=np.int32)

    pares = emparejar_palets(ids)

    for fila, (idx_izq, idx_der) in enumerate(pares):
        if fila >= filas:
            break
        yo = fila * PALET_Y

        # Lateral izquierdo (col 0)
        xo_izq = 0
        camion_bin[xo_izq:xo_izq + PALET_X, yo:yo + PALET_Y, :] = binario[idx_izq]
        camion_ids[xo_izq:xo_izq + PALET_X, yo:yo + PALET_Y, :] = ids[idx_izq]

        # Lateral derecho (col 1)
        if idx_der is not None:
            xo_der = PALET_X
            camion_bin[xo_der:xo_der + PALET_X, yo:yo + PALET_Y, :] = binario[idx_der]
            camion_ids[xo_der:xo_der + PALET_X, yo:yo + PALET_Y, :] = ids[idx_der]

    return camion_bin, camion_ids


# ─── Pipeline principal ───────────────────────────────────────────────────────

def cargar_camion(
    paradas: List[int],
    cajas_por_parada: Dict[int, int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Pipeline completo: llenar → emparejar → ensamblar.

    Returns:
        palet_bin  (N, 4, 5, 3): matriz binaria por palet
        palet_ids  (N, 4, 5, 3): IDs de parada por palet
        camion_bin (8, 15, 3):   matriz binaria del camión completo
        camion_ids (8, 15, 3):   IDs de parada del camión completo
    """
    capacidad_total = CAMION_COLS * CAMION_FILAS * PALET_CAP
    total_cajas = sum(cajas_por_parada.values())

    if total_cajas > capacidad_total:
        raise ValueError(
            f"Overflow: {total_cajas} cajas > capacidad del camión {capacidad_total}"
        )

    p_bin, p_ids = llenar_palets(paradas, cajas_por_parada)
    t_bin, t_ids = ensamblar_camion(p_bin, p_ids)
    return p_bin, p_ids, t_bin, t_ids


# ─── Utilidades de visualización ─────────────────────────────────────────────

def resumen(
    paradas: List[int],
    cajas_por_parada: Dict[int, int],
    p_bin: np.ndarray,
    p_ids: np.ndarray,
) -> None:
    """Imprime el plan de carga adaptado a apertura lateral."""
    total = sum(cajas_por_parada.values())
    n_palets = len(p_bin)
    pares = emparejar_palets(p_ids)

    print("=" * 65)
    print("PLAN DE CARGA — CAMIÓN APERTURA LATERAL")
    print("=" * 65)
    print(f"  Paradas en ruta : {paradas}")
    print(f"  Total cajas     : {total}")
    print(f"  Palets usados   : {n_palets} / {CAMION_COLS * CAMION_FILAS}")
    print(f"  Ocupación       : {100*total/(CAMION_COLS*CAMION_FILAS*PALET_CAP):.1f}%")
    print()
    print("  LATERAL IZQ (col 0)          LATERAL DER (col 1)")
    print("-" * 65)

    for fila, (idx_izq, idx_der) in enumerate(pares):
        def _desc(idx):
            if idx is None:
                return "  [  VACÍO  ]           "
            vals = p_ids[idx][p_ids[idx] > 0]
            stops = sorted(int(v) for v in np.unique(vals))
            n_cajas = int(np.sum(p_bin[idx]))
            return f"  Pal {idx} stops={stops} {n_cajas}/{PALET_CAP}c"

        izq_desc = _desc(idx_izq)
        der_desc = _desc(idx_der)
        print(f"  Fila {fila}: {izq_desc:<30} {der_desc}")

    print("=" * 65)


def ver_palet(p_ids: np.ndarray, idx_palet: int) -> None:
    """Imprime las capas de un palet de arriba (Z=2) a abajo (Z=0)."""
    print(f"\nPalet {idx_palet} — Z=2 arriba (1ª descarga) → Z=0 abajo (última):")
    print("-" * 42)
    for z in range(PALET_Z - 1, -1, -1):
        nombre = {PALET_Z - 1: f"TECHO Z={PALET_Z-1} (1ª descarga)", 0: "SUELO Z=0 (última)"}.get(
            z, f"CAPA  Z={z}"
        )
        print(f"  {nombre}:")
        capa = p_ids[idx_palet, :, :, z]
        for y in range(PALET_Y):
            fila = " ".join(f"{capa[x, y]:2d}" for x in range(PALET_X))
            print(f"    y={y}: [{fila}]")
    print()


def ver_camion_lateral(camion_ids: np.ndarray, z: int) -> None:
    """
    Imprime una capa Z del camión orientada para apertura lateral.

    Muestra col_izq | col_der por cada fila, reflejando la vista del operario
    que abre ambos laterales.
    """
    nombre_z = {PALET_Z - 1: f"TECHO Z={PALET_Z-1} (1ª descarga)", 0: "SUELO Z=0 (última)"}.get(z, f"CAPA Z={z}")
    print(f"\nCamión lateral — {nombre_z}")
    print(f"  {'LAT. IZQ':^20}  {'LAT. DER':^20}")
    print(f"  {'(col 0)':^20}  {'(col 1)':^20}")
    print("-" * 48)

    capa = camion_ids[:, :, z]  # (TX, TY)
    for fila in range(CAMION_FILAS):
        y0 = fila * PALET_Y
        print(f"  --- Fila {fila} ---")
        for y in range(PALET_Y):
            izq = " ".join(f"{capa[x, y0+y]:2d}" for x in range(PALET_X))
            der = " ".join(f"{capa[x, y0+y]:2d}" for x in range(PALET_X, 2*PALET_X))
            print(f"  [{izq}]  [{der}]")
    print()


# ─── Ejemplo de uso ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Escenario con 4 paradas para demostrar el emparejamiento lateral
    paradas = [1, 2, 3, 4]
    cajas = {
        1: 20,   # primera entrega
        2: 60,   # segunda entrega  (1 palet completo)
        3: 80,   # tercera entrega  (necesita 2 palets)
        4: 40,   # cuarta entrega
    }

    p_bin, p_ids, t_bin, t_ids = cargar_camion(paradas, cajas)

    resumen(paradas, cajas, p_bin, p_ids)

    for i in range(len(p_bin)):
        ver_palet(p_ids, i)

    for z in range(PALET_Z):
        ver_camion_lateral(t_ids, z)
