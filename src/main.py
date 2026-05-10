"""
Damm Smart Truck — Punt d'entrada principal

Orquestra el flux complet en 3 passos per a TOTES les rutes del Excel:
  1. excel_to_sql  — Carregar dades Excel → MongoDB
  2. router        — Optimitzar ruta amb OR-Tools + OSRM  (per a cada ruta)
  3. carga_async   — Generar matrius de càrrega del camió → MongoDB  (per a cada ruta)

Ús:
    cd src/
    python main.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# ── Resolució d'imports interns ───────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
for _sub in ('db', 'alghoritms', 'utils'):
    sys.path.insert(0, str(BASE_DIR / _sub))

from db.excel_to_sql import load_excel_to_sqlite   # noqa: E402
from alghoritms.router import executar_ruta         # noqa: E402
from utils.carga_async import generar_carga         # noqa: E402
from mongo import get_db                            # noqa: E402


# ── Descoberta de rutes ────────────────────────────────────────────────────────

def obtenir_totes_rutes() -> list[dict]:
    """
    Retorna una entrada per cada identificador de ruta únic del Excel.
    La data s'agafa del primer document trobat per aquella ruta.
    """
    pipeline = [
        {"$group": {"_id": "$ruta", "fecha": {"$first": "$fecha"}}},
        {"$project": {"_id": 0, "ruta": "$_id", "fecha": 1}},
        {"$sort":    {"ruta": 1}},
    ]
    return list(get_db()["detalle_entrega"].aggregate(pipeline))


def dia_setmana_de_data(data: str) -> int:
    """
    Converteix una data 'DD/MM/YYYY' al dia de la setmana (1=Dll … 5=Dv).
    Dissabte → 6, Diumenge → 7.
    """
    return datetime.strptime(data, '%d/%m/%Y').isoweekday()


# ── Glue: traduir la sortida de router a l'entrada de carga_async ─────────────

def obtenir_transporte(ruta: str, data: str) -> str:
    doc = get_db()["detalle_entrega"].find_one(
        {"ruta": ruta, "fecha": data},
        {"transporte": 1}
    )
    if doc is None:
        raise RuntimeError(
            f"No s'ha trobat cap registre per ruta='{ruta}', data='{data}'."
        )
    return str(doc["transporte"])


def ids_parada_en_ordre(parades_ruta: list, ruta: str, data: str) -> list[str]:
    """
    Converteix la llista de parades de router en la llista d'ids_parada
    que espera carga_async (id_destinatario_mercancia, deduplicat per node).
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
            print(f"  [AVÍS] Deudor no trobat per '{p['nom']}' — s'omet de la càrrega")
            continue
        if deudor not in vistos:
            ids.append(deudor)
            vistos.add(deudor)
    return ids


# ── Processar una sola ruta (PAS 2 + PAS 3) ──────────────────────────────────

def processar_ruta(ruta: str, data: str) -> dict:
    """
    Executa l'optimització i la càrrega per a una ruta+data concreta.
    Retorna un dict amb 'ok' (bool) i 'error' (str si ha fallat).
    """
    dia_setmana = dia_setmana_de_data(data)

    # PAS 2 — Optimització
    try:
        resultat = executar_ruta(ruta, data, dia_setmana)
    except Exception as exc:
        return {'ok': False, 'error': f"Router: {exc}"}

    if 'error' in resultat:
        return {'ok': False, 'error': resultat['error']}

    print(f"  Clients visitats: {resultat['clients_visitats']}  |  "
          f"saltats: {resultat['clients_saltats']}  |  "
          f"temps: {resultat['temps_total_min']} min")

    # PAS 3 — Càrrega del camió
    try:
        transporte        = obtenir_transporte(ruta, data)
        id_ruta_algoritmo = f"{data}|{transporte}|{ruta}"
        ids_parada        = ids_parada_en_ordre(resultat['parades_ruta'], ruta, data)

        print(f"  id_ruta: {id_ruta_algoritmo}  |  parades: {len(ids_parada)}")
        carga = asyncio.run(generar_carga(id_ruta_algoritmo, ids_parada))

        print(f"  Càrrega: {carga['total_cajas']} caixes · {carga['n_camiones']} camions")
        for cam in carga['camiones']:
            print(f"    Camió {cam['n_camion']}: {cam['n_cajas']} caixes · "
                  f"{cam['n_palets_usados']}/6 palets · {cam['ocupacion_pct']}%")
    except Exception as exc:
        return {'ok': False, 'error': f"Càrrega: {exc}"}

    return {'ok': True}


# ── Flux principal ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    # ─── PAS 1: Carregar dades Excel → MongoDB (una sola vegada) ────────────
    print("\n" + "═" * 62)
    print("  PAS 1 — Carregant dades Excel → MongoDB")
    print("═" * 62)
    load_excel_to_sqlite()

    # ─── Descobrir totes les rutes ───────────────────────────────────────────
    rutes = obtenir_totes_rutes()
    print(f"\n  Rutes trobades a la DB: {len(rutes)}")
    for r in rutes:
        print(f"    {r['ruta']}  {r['fecha']}")

    # ─── PAS 2 + 3: Iterar per cada ruta ────────────────────────────────────
    errors: list[tuple[str, str, str]] = []

    for i, item in enumerate(rutes, 1):
        ruta = item['ruta']
        data = item['fecha']

        print("\n" + "═" * 62)
        print(f"  [{i}/{len(rutes)}]  Ruta {ruta}  ·  {data}")
        print("═" * 62)

        resultat = processar_ruta(ruta, data)
        if not resultat['ok']:
            print(f"  [ERROR] {resultat['error']}")
            errors.append((ruta, data, resultat['error']))

    # ─── Resum final ──────────────────────────────────────────────────────────
    ok_count = len(rutes) - len(errors)
    print("\n" + "═" * 62)
    print(f"  RESUM FINAL:  {ok_count}/{len(rutes)} rutes processades correctament")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for ruta, data, msg in errors:
            print(f"    ✗  {ruta}  {data}  —  {msg}")
    else:
        print("  Totes les rutes s'han processat sense errors.")
    print("═" * 62)
