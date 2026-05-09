"""
Damm Smart Truck — Punt d'entrada principal

Orquestra el flux complet en 3 passos:
  1. excel_to_sql  — Carregar dades Excel → MongoDB
  2. router        — Optimitzar ruta amb OR-Tools + OSRM
  3. carga_async   — Generar matrius de càrrega del camió → MongoDB

Ús:
    cd src/
    python main.py
"""

import asyncio
import sys
from pathlib import Path

# ── Resolució d'imports interns ───────────────────────────────────────────────
# Cada submòdul fa imports relatius al seu propi directori (bare imports).
# Cal afegir-los tots a sys.path ABANS de qualsevol import del projecte.
BASE_DIR = Path(__file__).parent
for _sub in ('db', 'alghoritms', 'utils'):
    sys.path.insert(0, str(BASE_DIR / _sub))

from db.excel_to_sql import load_excel_to_sqlite   # noqa: E402
from alghoritms.router import executar_ruta         # noqa: E402
from utils.carga_async import generar_carga         # noqa: E402
from mongo import get_db                            # noqa: E402

# ── Paràmetres de la ruta ─────────────────────────────────────────────────────
RUTA        = 'DR0006'
DATA        = '19/03/2026'
DIA_SETMANA = 4           # 1=Dll  2=Dm  3=Dc  4=Dj  5=Dv


# ── Glue: traduir la sortida de router a l'entrada de carga_async ─────────────

def obtenir_transporte(ruta: str, data: str) -> str:
    """
    Retorna l'ID de transport per a la ruta i data donades.
    Necessari per construir l'id_ruta_algoritmo que espera carga_async.
    """
    doc = get_db()["detalle_entrega"].find_one(
        {"ruta": ruta, "fecha": data},
        {"transporte": 1}
    )
    if doc is None:
        raise RuntimeError(
            f"[ERROR] No s'ha trobat cap registre per ruta='{ruta}', data='{data}'. "
            "Comprova que els Excel s'han carregat correctament (PAS 1)."
        )
    return str(doc["transporte"])


def ids_parada_en_ordre(parades_ruta: list, ruta: str, data: str) -> list[str]:
    """
    Converteix la llista de parades de router en la llista de ids_parada
    que espera carga_async.

    router retorna noms de clients en ordre de lliurament.
    carga_async necessita id_destinatario_mercancia (deudor) en el mateix ordre.

    Les parades compartides (múltiples clients al mateix punt físic) comparteixen
    el mateix deudor — s'inclou una sola vegada per node.
    """
    pipeline = [
        {"$match": {"ruta": ruta, "fecha": data}},
        {"$group": {"_id": "$destinatario_mc_a_1", "nom": {"$first": "$nombre_1"}}},
    ]
    nom_a_deudor: dict[str, str] = {
        d["nom"]: str(d["_id"])
        for d in get_db()["detalle_entrega"].aggregate(pipeline)
    }

    vistos: set[str] = set()
    ids: list[str] = []
    for p in parades_ruta:
        if p['nom'] in ('DDI Mollet (sortida)', 'DDI Mollet (retorn)'):
            continue
        deudor = nom_a_deudor.get(p['nom'])
        if deudor is None:
            print(f"[AVÍS] Deudor no trobat per al client '{p['nom']}' — s'omet de la càrrega")
            continue
        if deudor not in vistos:
            ids.append(deudor)
            vistos.add(deudor)
    return ids


# ── Flux principal ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    # ─── PAS 1: Carregar dades Excel → MongoDB ──────────────────────────────
    print("\n" + "═" * 62)
    print("  PAS 1 — Carregant dades Excel → MongoDB")
    print("═" * 62)
    load_excel_to_sqlite()

    # ─── PAS 2: Optimitzar ruta ──────────────────────────────────────────────
    print("\n" + "═" * 62)
    print(f"  PAS 2 — Optimitzant ruta {RUTA} del {DATA} (dia {DIA_SETMANA})")
    print("═" * 62)
    resultat = executar_ruta(RUTA, DATA, DIA_SETMANA)

    if 'error' in resultat:
        print(f"\n[ERROR] {resultat['error']}")
        sys.exit(1)

    print(f"\n── Resum de la ruta ──────────────────────────────────")
    print(f"  Ruta:              {resultat['ruta']}")
    print(f"  Data:              {resultat['data']}")
    print(f"  Clients visitats:  {resultat['clients_visitats']}")
    print(f"  Clients saltats:   {resultat['clients_saltats']}")
    print(f"  Temps total:       {resultat['temps_total_min']} min")

    # ─── PAS 3: Generar matriu de càrrega del camió ──────────────────────────
    print("\n" + "═" * 62)
    print("  PAS 3 — Generant matriu de càrrega → MongoDB")
    print("═" * 62)

    transporte        = obtenir_transporte(RUTA, DATA)
    id_ruta_algoritmo = f"{DATA}|{transporte}|{RUTA}"
    ids_parada        = ids_parada_en_ordre(resultat['parades_ruta'], RUTA, DATA)

    print(f"  id_ruta:            {id_ruta_algoritmo}")
    print(f"  Parades a carregar: {len(ids_parada)}")

    carga = asyncio.run(generar_carga(id_ruta_algoritmo, ids_parada))

    print(f"\n── Resum de la càrrega ───────────────────────────────")
    print(f"  Total caixes:   {carga['total_cajas']}")
    print(f"  Camions:        {carga['n_camiones']}")
    for cam in carga['camiones']:
        print(
            f"  Camió {cam['n_camion']}: "
            f"{cam['n_cajas']} caixes · "
            f"{cam['n_palets_usados']}/6 palets · "
            f"{cam['ocupacion_pct']}% ocupació"
        )
    print(f"\n  [OK] Guardat a MongoDB (col·lecció: resultado_carga_camion)")
