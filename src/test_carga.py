"""
Test de generar_carga con la ruta real completa:
  19/03/2026 | transporte 11588007 | ruta DR0016
  29 paradas, ~605 cajas
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from carga_async import generar_carga

ID_RUTA = "19/03/2026|11588007|DR0016"

# IDs de parada en orden de entrega (tal como los mandaría el compañero)
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


def imprimir_camion(n_camion: int, cam: dict, paradas_camion: list[dict]) -> None:
    t_bin = cam["camion_binario"]
    t_ids = cam["camion_ids"]
    TX = len(t_bin)
    TY = len(t_bin[0])
    TZ = len(t_bin[0][0])

    print(f"\n  {'─'*61}")
    print(f"  CAMIÓN {n_camion}  —  {cam['n_cajas']} cajas  |  "
          f"{cam['n_palets_usados']}/6 palets  |  {cam['ocupacion_pct']}% ocupación")
    print(f"  {'─'*61}")

    print("  Paradas incluidas:")
    for p in paradas_camion:
        print(f"    Parada {p['orden']:>2} | {p['id_destinatario']:<12} | {p['cajas']:>4} cajas")

    print(f"\n  MATRICES  (ancho×largo×alto = {TX}×{TY}×{TZ})")
    print("  Cada número = orden de parada en la ruta  (0 = vacío)")
    print("  ■ = caja ocupada  · = vacío\n")

    num_filas = TY // PALET_Y
    for z in range(TZ - 1, -1, -1):
        if z == TZ - 1:
            etiqueta = f"Z={z} TECHO — 1ª descarga"
        elif z == 0:
            etiqueta = f"Z={z} SUELO — última descarga"
        else:
            etiqueta = f"Z={z}"
        print(f"  ┌─ {etiqueta} {'─'*(36-len(etiqueta))}")
        print(f"  │  {'LAT. IZQ (col 0)':^18}  {'LAT. DER (col 1)':^18}")

        for fila in range(num_filas):
            print(f"  │  ── Fila {fila} ─────────────────────────")
            for y in range(PALET_Y):
                iy = fila * PALET_Y + y
                ids_izq = " ".join(f"{t_ids[x][iy][z]:>2}" for x in range(PALET_X))
                ids_der = " ".join(f"{t_ids[x][iy][z]:>2}" for x in range(PALET_X, TX))
                ocu_izq = " ".join("■" if t_bin[x][iy][z] else "·" for x in range(PALET_X))
                ocu_der = " ".join("■" if t_bin[x][iy][z] else "·" for x in range(PALET_X, TX))
                print(f"  │  [{ids_izq}]  [{ids_der}]   {ocu_izq} | {ocu_der}")
        print("  └" + "─" * 50)


def imprimir_resultado(resultado: dict) -> None:
    paradas   = resultado["paradas"]
    camiones  = resultado["camiones"]

    print("\n" + "═" * 65)
    print(f"  RUTA: {ID_RUTA}")
    print("═" * 65)
    print(f"  Paradas    : {resultado['n_paradas']}")
    print(f"  Total cajas: {resultado['total_cajas']}")
    print(f"  Camiones   : {resultado['n_camiones']}")

    # Agrupar paradas por camión
    paradas_por_camion: list[list[dict]] = [[] for _ in camiones]
    idx = 0
    for n_cam, cam in enumerate(camiones):
        n_paradas_cam = len([p for p in paradas
                             if cam["n_camion"] == n_cam + 1
                             or True])  # calcular desde n_cajas
        # Recalcular cuántas paradas tiene este camión por sus cajas acumuladas
        cajas_acum = 0
        paradas_cam = []
        while idx < len(paradas) and cajas_acum + paradas[idx]["cajas"] <= cam["n_cajas"]:
            paradas_cam.append(paradas[idx])
            cajas_acum += paradas[idx]["cajas"]
            idx += 1
        paradas_por_camion[n_cam] = paradas_cam

    for cam, paradas_cam in zip(camiones, paradas_por_camion):
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
