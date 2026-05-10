"""
Test de generar_carga con datos reales de MongoDB.
Ruta: 19/03/2026 | transporte 11588007 | DR0016
"""

import asyncio
import sys
from pathlib import Path

BASE = Path(__file__).parent
for sub in ("db", "alghoritms", "utils"):
    sys.path.insert(0, str(BASE / sub))

from carga_async import generar_carga

ID_RUTA = "19/03/2026|11588007|DR0016"

IDS_PARADA = [
    "9100087801",  #  1 — CASA CHUECOS
    "9100559291",  #  2 — INDOORWALL GRANOLLERS
    "9100480482",  #  3 — BAR MILANA BRASERIA
    "9100698912",  #  4 — EL SAZON DE ROSARIO
    "9100521678",  #  5 — PAPUA COLL DE LA MANYA
    "9100043893",  #  6 — BAR RESTAURANT PAVEPIC
    "9100340260",  #  7 — BAR RESTAURANTE MERLY'S
    "9100043381",  #  8 — LA BAGUETINA
    "9100507921",  #  9 — KARMA'S
    "9100310143",  # 10 — BAR RESTAURANT TROYA
    "9100044469",  # 11 — BAR EL RECONET
    "9100681218",  # 12 — BAR ZHOU
    "9100682473",  # 13 — CAL JOAN
    "9100550379",  # 14 — BAR LONDEN 2
    "9100227012",  # 15 — NUNA'S
    "9100420786",  # 16 — CAFETERIA FORN LA FLAIRE
    "9100253786",  # 17 — BAR LA RAMBLA
    "9100525754",  # 18 — BAR NEVADA II
    "9100121164",  # 19 — EL RACO DE LES MORERES
    "9100743172",  # 20 — FORN LA CARMEN
    "9100743868",  # 21 — BAR XARANA GRANOLLERS
    "9100653355",  # 22 — EL TIRO DE GRANOLLERS
    "9100752730",  # 23 — CAFE LEO
    "9100658144",  # 24 — CAN SANO
    "9100250393",  # 25 — RTE AYOPAYA
    "9100626587",  # 26 — JAVIS 3
    "9100747591",  # 27 — Dania's Bistro & Grill
    "118135",      # 28 — BK GRANOLLERS
    "9100652617",  # 29 — PADEL INDOOR GRANOLLERS
]

PALET_X = 4
PALET_Y = 3
PALET_Z = 5
_SIM = {0: '·', 1: 'C', 2: 'B', 3: 'V'}


def imprimir_camion(n_camion: int, cam: dict, paradas_camion: list) -> None:
    t_tipo = cam["camion_tipo"]
    t_ids  = cam["camion_ids"]
    TX = len(t_tipo)
    TY = len(t_tipo[0])
    TZ = len(t_tipo[0][0])

    print(f"\n  {'─'*63}")
    print(f"  CAMIÓN {n_camion}  —  {cam['n_cajas']} uds entrega  |  "
          f"{cam['n_palets_usados']}/6 palets  |  {cam['ocupacion_pct']}% ocupación")
    print(f"  {'─'*63}")

    print("  Paradas incluidas:")
    for p in paradas_camion:
        print(f"    Parada {p['orden']:>2} | {p['id_destinatario']:<14} | "
              f"CAJ={p['cajas']:>3}  BRL={p['barriles']:>2}  CJ13={p['cj13']:>2}")

    print(f"\n  MATRICES  ({TX}×{TY}×{TZ})  "
          f"· =vacío  C=caja  B=barril  V=CJ13  (núm = parada)")

    num_filas = TY // PALET_Y
    for z in range(TZ - 1, -1, -1):
        etiqueta = (
            f"TECHO Z={TZ-1} — 1ª descarga" if z == TZ-1
            else f"SUELO Z=0  — última" if z == 0
            else f"Z={z}"
        )
        print(f"\n  ┌─ {etiqueta} {'─'*(38-len(etiqueta))}")
        print(f"  │  {'IZQ (col 0)':^22}  {'DER (col 1)':^22}")
        for fila in range(num_filas):
            print(f"  │  ── Fila {fila} ───────────────────────────────")
            for y in range(PALET_Y):
                iy = fila * PALET_Y + y
                def _r(x_range):
                    return " ".join(
                        f"{_SIM[t_tipo[x][iy][z]]}{t_ids[x][iy][z]:02d}"
                        if t_ids[x][iy][z] else "  · "
                        for x in x_range
                    )
                print(f"  │  [{_r(range(PALET_X))}]  [{_r(range(PALET_X, TX))}]")
        print(f"  └{'─'*52}")


def imprimir_resultado(resultado: dict) -> None:
    paradas  = resultado["paradas"]
    camiones = resultado["camiones"]

    print("\n" + "═" * 65)
    print(f"  RUTA: {ID_RUTA}")
    print("═" * 65)
    print(f"  Paradas    : {resultado['n_paradas']}")
    print(f"  Total uds  : {resultado['total_cajas']}")
    print(f"  Camiones   : {resultado['n_camiones']}")

    # Distribuir paradas por camión según acumulado
    idx = 0
    for cam in camiones:
        tope = cam["n_cajas"]
        acum = 0
        paradas_cam = []
        while idx < len(paradas):
            p = paradas[idx]
            unidades = p["cajas"] + p["barriles"]
            if acum + unidades > tope and paradas_cam:
                break
            paradas_cam.append(p)
            acum += unidades
            idx += 1
        imprimir_camion(cam["n_camion"], cam, paradas_cam)

    print("\n" + "═" * 65)
    print("  Guardado en MongoDB ✓")
    print("═" * 65)


async def main():
    print(f"Generando carga para ruta real ({len(IDS_PARADA)} paradas)...")
    resultado = await generar_carga(ID_RUTA, IDS_PARADA)
    imprimir_resultado(resultado)


if __name__ == "__main__":
    asyncio.run(main())
