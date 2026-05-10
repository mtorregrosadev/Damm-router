"""
Test de truck_loader con parámetros hardcodeados.
No necesita base de datos — llama directamente a cargar_camion.

Escenarios:
  A) Solo cajas
  B) Cajas + barriles (verifica restricción física)
  C) Cajas + barriles + CJ13
  D) Parada con descarga y CJ13 simultáneos
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "alghoritms"))

from truck_loader import (
    cargar_camion,
    ver_camion_lateral,
    resumen,
    PALET_X, PALET_Y, PALET_Z,
    TIPO_VACIO, TIPO_CAJA, TIPO_BARRIL, TIPO_CJ13,
    CAMION_COLS, CAMION_FILAS, PALET_CAP,
)
import numpy as np


# ─── Verificación restricción física ─────────────────────────────────────────

def verificar_restriccion_barril(p_tipo: np.ndarray, nombre: str) -> bool:
    """
    Comprueba que en ninguna columna (x,y) haya un barril encima de una caja.
    Barril encima de caja = barril en z mayor que una caja en la misma columna.
    """
    violaciones = 0
    n, PX, PY, PZ = p_tipo.shape
    for p in range(n):
        for x in range(PX):
            for y in range(PY):
                col = p_tipo[p, x, y, :]  # Z=0..4
                z_cajas    = [z for z in range(PZ) if col[z] == TIPO_CAJA]
                z_barriles = [z for z in range(PZ) if col[z] == TIPO_BARRIL]
                if z_cajas and z_barriles:
                    max_barril = max(z_barriles)
                    min_caja   = min(z_cajas)
                    if max_barril > min_caja:
                        violaciones += 1
                        print(f"  [!] Violación en palet={p} x={x} y={y}: "
                              f"barril en z={max_barril} encima de caja en z={min_caja}")
    if violaciones == 0:
        print(f"  [OK] Restricción física correcta — ningún barril encima de caja")
        return True
    else:
        print(f"  [FAIL] {violaciones} violaciones encontradas")
        return False


def imprimir_camion(t_tipo: np.ndarray, t_ids: np.ndarray) -> None:
    _SIM = {TIPO_VACIO: '·', TIPO_CAJA: 'C', TIPO_BARRIL: 'B', TIPO_CJ13: 'V'}
    TX, TY, TZ = t_tipo.shape
    num_filas = TY // PALET_Y

    for z in range(TZ - 1, -1, -1):
        etiqueta = (
            f"TECHO Z={TZ-1} (1ª descarga)" if z == TZ-1
            else f"SUELO Z=0 (última)" if z == 0
            else f"Z={z}"
        )
        print(f"\n  ┌─ {etiqueta}")
        print(f"  │  {'IZQ (col 0)':^18}  {'DER (col 1)':^18}")
        for fila in range(num_filas):
            print(f"  │  ── Fila {fila} ─────────────────────")
            for y in range(PALET_Y):
                iy = fila * PALET_Y + y
                def _r(x_range):
                    return " ".join(
                        f"{_SIM[t_tipo[x,iy,z]]}{t_ids[x,iy,z]:02d}"
                        if t_ids[x,iy,z] else "  · "
                        for x in x_range
                    )
                print(f"  │  [{_r(range(PALET_X))}]  [{_r(range(PALET_X, TX))}]")
        print(f"  └{'─'*50}")


def correr_escenario(nombre, paradas, cajas, barriles, cj13=None):
    print(f"\n{'═'*65}")
    print(f"  ESCENARIO: {nombre}")
    print(f"{'═'*65}")
    print(f"  Paradas  : {paradas}")
    print(f"  Cajas    : {cajas}")
    print(f"  Barriles : {barriles}")
    print(f"  CJ13     : {cj13}")

    try:
        p_tipo, p_ids, t_tipo, t_ids = cargar_camion(
            paradas, cajas, barriles, cj13
        )
    except ValueError as e:
        print(f"  [ERROR] {e}")
        return

    resumen(paradas, cajas, barriles, cj13, p_tipo, p_ids)
    verificar_restriccion_barril(p_tipo, nombre)

    # Conteo por tipo en el camión
    total_c = int(np.sum(t_tipo == TIPO_CAJA))
    total_b = int(np.sum(t_tipo == TIPO_BARRIL))
    total_v = int(np.sum(t_tipo == TIPO_CJ13))
    total_0 = int(np.sum(t_tipo == TIPO_VACIO))
    print(f"\n  Camión ensamblado — posiciones:")
    print(f"    Cajas     (1): {total_c}")
    print(f"    Barriles  (2): {total_b}")
    print(f"    CJ13      (3): {total_v}")
    print(f"    Vacías    (0): {total_0}")
    print(f"    Total        : {total_c+total_b+total_v+total_0} "
          f"(esperado {CAMION_COLS*CAMION_FILAS*PALET_CAP})")

    print(f"\n  Shape camion_tipo : {list(t_tipo.shape)}")
    print(f"  Shape camion_ids  : {list(t_ids.shape)}")

    imprimir_camion(t_tipo, t_ids)


# ─── Escenarios ───────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # A) Solo cajas
    correr_escenario(
        "A — Solo cajas",
        paradas  = [1, 2, 3],
        cajas    = {1: 40, 2: 60, 3: 80},
        barriles = {1:  0, 2:  0, 3:  0},
    )

    # B) Cajas + barriles (verifica restricción física)
    correr_escenario(
        "B — Cajas + barriles",
        paradas  = [1, 2, 3, 4],
        cajas    = {1: 20, 2: 30, 3: 40, 4: 20},
        barriles = {1:  5, 2:  0, 3: 10, 4:  5},
    )

    # C) Cajas + barriles + CJ13
    correr_escenario(
        "C — Cajas + barriles + CJ13",
        paradas  = [1, 2, 3, 4],
        cajas    = {1: 10, 2: 30, 3: 40, 4: 20},
        barriles = {1:  5, 2:  0, 3: 10, 4:  5},
        cj13     = {2:  6, 4:  4},
    )

    # D) Parada con descarga y CJ13 simultáneos (parada 2 descarga Y recoge)
    correr_escenario(
        "D — Descarga y CJ13 simultáneos en parada 2",
        paradas  = [1, 2, 3],
        cajas    = {1: 30, 2: 40, 3: 50},
        barriles = {1:  0, 2: 10, 3:  0},
        cj13     = {2: 12},
    )

    # E) Escenario denso — cerca del límite de capacidad
    correr_escenario(
        "E — Alta ocupación (barriles primera parada)",
        paradas  = [1, 2, 3, 4, 5],
        cajas    = {1: 20, 2: 40, 3: 40, 4: 30, 5: 20},
        barriles = {1: 20, 2:  5, 3:  5, 4:  5, 5:  5},
        cj13     = {3: 10, 5:  5},
    )

    print(f"\n{'═'*65}")
    print("  Tests completados.")
    print(f"{'═'*65}\n")
