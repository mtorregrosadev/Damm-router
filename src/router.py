"""
Damm Smart Truck — Optimitzador de Ruta
Algorisme: VRP amb Time Windows (VRPTW) via OR-Tools

INPUT:  Hackaton.xlsx + Horarios.XLSX  →  ruta + data concreta
OUTPUT: Ordre òptim de visita dels clients + hora estimada d'arribada

ESTRUCTURA:
  1. Carregar i preparar dades
  2. Geocodificar adreces (lat/lon)
  3. Construir matriu de temps
  4. Llegir time windows dels horaris
  5. Configurar i córrer OR-Tools
  6. Mostrar resultat
"""

import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


# ═══════════════════════════════════════════════════════════════════
# BLOC 1 — CONSTANTS I CONFIGURACIÓ
# ═══════════════════════════════════════════════════════════════════

RUTA        = 'DR0006'
DATA        = '19/03/2026'
DIA_SETMANA = 4          # 1=Dll 2=Dm 3=Dc 4=Dj 5=Dv

# Magatzem DDI Mollet del Vallès (punt de partida i tornada)
DEPOT_LAT = 41.5396
DEPOT_LON =  2.2100

# Jornada laboral en segons des de les 06:00h
# Exemple: 06:00h = 0s, 07:00h = 3600s, 15:00h = 32400s
JORNADA_INICI_H = 6      # El camió surt a les 6h
JORNADA_FI_H    = 18     # Límit màxim de la jornada

# Velocitat mitjana de repartiment (km/h, àrea urbana)
VELOCITAT_KMH = 35

# Temps de servei per defecte per parada (minuts) — temps per descarregar
TEMPS_SERVEI_MIN = 12

# ── Temps de descàrrega variable per client (en minuts) ──────────
# Si un client no apareix aquí, s'usarà TEMPS_SERVEI_MIN per defecte
TEMPS_DESCÀRREGA: dict[str, int] = {
    # 'Nom exacte del client': minuts_descàrrega
    # Exemples:
    # 'SUPERMERCATS BONPREU': 25,
    # 'BAR LA LLUNA': 8,
}

# ── Penalitzacions per saltar-se clients ─────────────────────────
PENALITZACIO_ALTA     = 99999  # Client prioritari, quasi obligatori
PENALITZACIO_NORMAL   = 3600   # Client estàndard (equiv. 1h de retard)
PENALITZACIO_OPCIONAL = 500    # Client de poc volum, es pot saltar

# Nivell de penalització per client (nom → penalització). Default: NORMAL
PRIORITATS_CLIENT: dict[str, int] = {
    # 'Nom exacte del client': PENALITZACIO_ALTA,
    # Exemples:
    # 'BAR CENTRAL': PENALITZACIO_ALTA,
    # 'QUIOSC PARETS': PENALITZACIO_OPCIONAL,
}

# ── Arcs prohibits ────────────────────────────────────────────────
# Llista de tuples (idx_node_origen, idx_node_desti)
# 0 = dipòsit, 1..N = clients en ordre del DataFrame de parades
ARCS_PROHIBITS: list[tuple[int, int]] = [
    # Exemples ficticis (descomenta per activar):
    # (1, 3),   # No pot anar de parada 1 directament a parada 3
    # (5, 2),   # No pot anar de parada 5 directament a parada 2
]

# ── Tràfic històric per franja horària ───────────────────────────
ZONES_TRAFIC_MATINAL  = {'MOLLET RAMBLA NOVA', 'MOLLET CAN BORRELL'}
FACTOR_TRAFIC_MATINAL = 1.4
RUSH_HOUR_INICI_S     = 7200   # 08:00h → 2h des de les 06:00h
RUSH_HOUR_FI_S        = 10800  # 09:00h → 3h des de les 06:00h


# ═══════════════════════════════════════════════════════════════════
# BLOC 2 — CARREGAR DADES
# ═══════════════════════════════════════════════════════════════════

def carregar_parades(ruta: str, data: str) -> pd.DataFrame:
    """
    Retorna un DataFrame amb una fila per parada.
    Columnes: Entrega, Nombre1, Calle, CP, Población, ZonaTransp, Deudor
    """
    df = pd.read_excel('BD/Hackaton.xlsx', sheet_name='Detalle entrega')
    dia = df[(df['Ruta'] == ruta) & (df['FECHA'] == data)]

    parades = dia.groupby('Entrega').agg({
        'Nombre 1':              'first',
        'Calle':                 'first',
        'CP':                    'first',
        'Población':             'first',
        'ZonaTransp.1':          'first',
        'Destinatario mcía..1':  'first',   # ID client numèric (Deudor)
    }).reset_index()

    parades = parades.rename(columns={
        'Nombre 1':              'nom',
        'Calle':                 'carrer',
        'CP':                    'cp',
        'Población':             'poblacio',
        'ZonaTransp.1':          'zona',
        'Destinatario mcía..1':  'deudor',
    })

    print(f"[OK] {len(parades)} parades carregades per ruta {ruta} del {data}")
    return parades


def carregar_horaris(dia_setmana: int) -> pd.DataFrame:
    """
    Retorna les time windows de cada client per al dia de la setmana indicat.
    Columnes resultants: deudor, tw_inici_s, tw_fi_s, tancat
    (temps en segons des de JORNADA_INICI_H)
    """
    h = pd.read_excel('BD/Horarios_Entrega.XLSX')
    h = h[h['Día semana'] == dia_setmana].copy()

    def parse_hora(valor):
        """Converteix '10:30:00' o 0.4375 → segons des de jornada_inici"""
        if pd.isna(valor):
            return None
        if isinstance(valor, str):
            parts = valor.split(':')
            hores = int(parts[0]) + int(parts[1])/60
        elif isinstance(valor, (int, float)):
            hores = float(valor) * 24  # fracció de dia → hores
        else:
            hores = 0
        return int((hores - JORNADA_INICI_H) * 3600)

    h['tw_inici_s'] = h['Horario inicia a'].apply(parse_hora)
    h['tw_fi_s']    = h['Horario termina a'].apply(parse_hora)
    h['tancat']     = h['Cierre Si/No'].notna()

    jornada_s = (JORNADA_FI_H - JORNADA_INICI_H) * 3600
    h['tw_inici_s'] = h['tw_inici_s'].clip(lower=0)
    h['tw_fi_s']    = h['tw_fi_s'].clip(upper=jornada_s)

    return h[['Deudor', 'tw_inici_s', 'tw_fi_s', 'tancat']].rename(
        columns={'Deudor': 'deudor'}
    )


# ═══════════════════════════════════════════════════════════════════
# BLOC 3 — GEOCODIFICACIÓ (lat/lon per a cada adreça)
# ═══════════════════════════════════════════════════════════════════

# OPCIÓ A — Coordenades aproximades per zona (hackathon, sense API)
# Mollet del Vallès i voltants. En producció: usar geopy o Google Maps API.
COORDS_PER_ZONA = {
    'MOLLET CAN BORRELL':    (41.5430,  2.2115),
    'MOLLET RAMBLA NOVA':    (41.5380,  2.2140),
    'PARETS SUD / LOURDE':   (41.5640,  2.2240),
    'MARTORELLES':           (41.5670,  2.2440),
    'ST FOST CAMPSENTELL':   (41.5380,  2.2700),
    'MOLL PRATRIBA/POMPE':   (41.5360,  2.1980),
    'MOLL.PANTIQ/MAGAROL':   (41.5290,  2.2060),
    'MOLLET ILLA/E.FRANÇ':   (41.5400,  2.2080),
    'MOLLET TARDA':          (41.5350,  2.2200),
    'MOLLET BARRI OLIVA':    (41.5450,  2.2050),
    'PARETS NORD':           (41.5710,  2.2300),
    'LA ROCA':               (41.6100,  2.3400),
    'LLIÇA DE VALL':         (41.6020,  2.2780),
}


def geocodificar_parades(parades: pd.DataFrame) -> pd.DataFrame:
    """
    Afegeix columnes lat i lon a cada parada.
    En producció: usar geopy.geocoders.Nominatim o Google Maps API.
    Aquí usem coordenades per zona com a proxy per al hackathon.
    """
    lats, lons = [], []
    for _, row in parades.iterrows():
        zona = row['zona']
        if zona in COORDS_PER_ZONA:
            lat, lon = COORDS_PER_ZONA[zona]
            lat += np.random.uniform(-0.003, 0.003)
            lon += np.random.uniform(-0.004, 0.004)
        else:
            lat, lon = DEPOT_LAT, DEPOT_LON  # fallback
        lats.append(lat)
        lons.append(lon)

    parades = parades.copy()
    parades['lat'] = lats
    parades['lon'] = lons
    return parades


# ═══════════════════════════════════════════════════════════════════
# BLOC 4 — MATRIU DE TEMPS (el cor de l'algorisme)
# ═══════════════════════════════════════════════════════════════════

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Distància en km entre dos punts GPS (fórmula haversine)"""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def construir_matriu_temps(locations: list, parades_df: pd.DataFrame) -> list:
    """
    Construeix la matriu NxN de temps de viatge en segons.
    locations:  [(lat,lon), ...] — index 0 = dipòsit
    parades_df: DataFrame de clients (sense dipòsit), per obtenir temps
                de servei variable per cada destinació.
    """
    n = len(locations)
    matriu = []
    for i in range(n):
        fila = []
        for j in range(n):
            if i == j:
                fila.append(0)
            else:
                km = haversine_km(locations[i][0], locations[i][1],
                                   locations[j][0], locations[j][1])
                temps_s = int((km / VELOCITAT_KMH) * 3600)
                # Temps de servei variable: j=0 és el dipòsit (sense descàrrega)
                if j > 0:
                    nom_client = parades_df.iloc[j - 1]['nom']
                    service_min = TEMPS_DESCÀRREGA.get(nom_client, TEMPS_SERVEI_MIN)
                    temps_s += service_min * 60
                fila.append(temps_s)
        matriu.append(fila)
    return matriu


# ═══════════════════════════════════════════════════════════════════
# BLOC 5 — PREPARAR CONTEXT PER A OR-TOOLS
# ═══════════════════════════════════════════════════════════════════

def preparar_context(parades: pd.DataFrame, horaris: pd.DataFrame) -> dict:
    """
    Construeix el diccionari de dades que passarem a OR-Tools.
    Estructura:
      - locations:      [(lat,lon)] — index 0 = dipòsit
      - time_matrix:    NxN matriu de temps en segons
      - time_windows:   [(inici_s, fi_s)] per a cada node
      - node_zones:     {node_idx: zona} per al càlcul de tràfic
      - num_vehicles:   sempre 1 (un camió, una ruta)
      - depot:          0 (índex del dipòsit)
    """
    jornada_s = (JORNADA_FI_H - JORNADA_INICI_H) * 3600

    parades_h = parades.merge(horaris, on='deudor', how='left')

    # Si no té horari, finestra completa (0, 43200)
    parades_h['tw_inici_s'] = parades_h['tw_inici_s'].fillna(0).astype(int)
    parades_h['tw_fi_s']    = parades_h['tw_fi_s'].fillna(jornada_s).astype(int)
    parades_h['tancat']     = parades_h['tancat'].fillna(False).astype(bool)

    oberts  = parades_h[~parades_h['tancat']].copy().reset_index(drop=True)
    tancats = parades_h[parades_h['tancat']]
    if len(tancats) > 0:
        print(f"[INFO] {len(tancats)} clients tancats eliminats: "
              f"{tancats['nom'].tolist()}")

    # Locations: dipòsit primer (index 0), llavors clients
    locations = [(DEPOT_LAT, DEPOT_LON)]
    for _, row in oberts.iterrows():
        locations.append((row['lat'], row['lon']))

    # Time windows: dipòsit disponible tota la jornada
    time_windows = [(0, jornada_s)]
    for _, row in oberts.iterrows():
        tw_i = max(0, row['tw_inici_s'])
        tw_f = min(jornada_s, row['tw_fi_s'])
        if tw_f <= tw_i:
            tw_f = jornada_s
        time_windows.append((tw_i, tw_f))

    time_matrix = construir_matriu_temps(locations, oberts)

    # Mapa node → zona, usat per aplicar el factor de tràfic matinal
    node_zones: dict[int, str | None] = {0: None}
    for idx, row in enumerate(oberts.itertuples(), start=1):
        node_zones[idx] = row.zona

    context = {
        'locations':    locations,
        'time_matrix':  time_matrix,
        'time_windows': time_windows,
        'node_zones':   node_zones,
        'num_vehicles': 1,
        'depot':        0,
        'parades_df':   oberts,
    }

    print(f"[OK] Context preparat: {len(locations)-1} clients + 1 dipòsit")
    print(f"     Matriu de temps: {len(time_matrix)}x{len(time_matrix[0])}")
    return context


# ═══════════════════════════════════════════════════════════════════
# BLOC 6 — OR-TOOLS: CONFIGURAR I RESOLDRE
# ═══════════════════════════════════════════════════════════════════

def resoldre_ruta(context: dict):
    """
    Crida a OR-Tools VRPTW i retorna l'ordre òptim de visita.
    Retorna: (ruta_indices, solution, routing, manager, time_dimension)
    """
    node_zones  = context.get('node_zones', {})
    parades_df  = context['parades_df']

    # ── Pas 1: Crear el manager ──────────────────────────────────
    manager = pywrapcp.RoutingIndexManager(
        len(context['time_matrix']),
        context['num_vehicles'],
        context['depot']
    )

    # ── Pas 2: Crear el model de routing ─────────────────────────
    routing = pywrapcp.RoutingModel(manager)

    # ── Pas 3: Funció de cost amb tràfic per franja horària ──────
    def time_callback(from_index, to_index):
        from_node  = manager.IndexToNode(from_index)
        to_node    = manager.IndexToNode(to_index)
        temps_base = context['time_matrix'][from_node][to_node]

        # Tràfic: si el destí és zona congestionada, estimem l'hora d'arribada
        # com el temps directe depot→from_node (proxy per hackathon, ja que
        # OR-Tools no exposa el temps acumulat dins el transit callback).
        to_zone = node_zones.get(to_node)
        if to_zone in ZONES_TRAFIC_MATINAL:
            hora_estimada_s = context['time_matrix'][0][from_node]
            if RUSH_HOUR_INICI_S <= hora_estimada_s <= RUSH_HOUR_FI_S:
                return int(temps_base * FACTOR_TRAFIC_MATINAL)

        return temps_base

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # ── Pas 4: Dimensió de temps (Time Windows) ──────────────────
    routing.AddDimension(
        transit_callback_index,
        60 * 60,                                    # slack_max: espera màx. 1h
        (JORNADA_FI_H - JORNADA_INICI_H) * 3600,   # durada màx. jornada
        False,
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    # ── Pas 5: Time Windows dures + penalitzacions per client ────
    for node_idx in range(1, len(context['time_windows'])):
        index = manager.NodeToIndex(node_idx)
        tw_inici, tw_fi = context['time_windows'][node_idx]

        # Restricció dura: el camió ha d'arribar dins la finestra
        time_dimension.CumulVar(index).SetRange(tw_inici, tw_fi)

        # Penalització variable per nivell de prioritat del client
        nom_client  = parades_df.iloc[node_idx - 1]['nom']
        penalitzacio = PRIORITATS_CLIENT.get(nom_client, PENALITZACIO_NORMAL)
        routing.AddDisjunction([index], penalitzacio, 1)

    # ── Pas 6: Restricció del dipòsit ────────────────────────────
    depot_idx = manager.NodeToIndex(context['depot'])
    time_dimension.CumulVar(depot_idx).SetRange(
        0, (JORNADA_FI_H - JORNADA_INICI_H) * 3600
    )

    # ── Pas 7: Arcs prohibits ────────────────────────────────────
    n_nodes = len(context['time_matrix'])
    for (node_orig, node_dest) in ARCS_PROHIBITS:
        if 0 <= node_orig < n_nodes and 0 <= node_dest < n_nodes:
            idx_orig = manager.NodeToIndex(node_orig)
            idx_dest = manager.NodeToIndex(node_dest)
            routing.NextVar(idx_orig).RemoveValue(idx_dest)

    # ── Pas 8: Estratègia de cerca ───────────────────────────────
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 30
    search_params.log_search = False

    # ── Pas 9: RESOLDRE ──────────────────────────────────────────
    print("\n[...] Resolent amb OR-Tools (màxim 30s)...")
    solution = routing.SolveWithParameters(search_params)

    if not solution:
        print("[ERROR] OR-Tools no ha trobat solució!")
        return []

    # ── Pas 10: Extreure la ruta ──────────────────────────────────
    ruta_indices = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        ruta_indices.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    ruta_indices.append(manager.IndexToNode(index))  # dipòsit final

    return ruta_indices, solution, routing, manager, time_dimension


# ═══════════════════════════════════════════════════════════════════
# BLOC 7 — FORMATAR I MOSTRAR RESULTAT
# ═══════════════════════════════════════════════════════════════════

def _segons_a_hhmm(segons_des_inici: int) -> str:
    hora = JORNADA_INICI_H + segons_des_inici / 3600
    return f"{int(hora):02d}:{int((hora % 1) * 60):02d}h"


def mostrar_resultat(ruta_indices, solution, routing, manager,
                     time_dimension, context):
    """Imprimeix la ruta optimitzada amb horaris, time windows i resum"""
    parades_df   = context['parades_df']
    time_windows = context['time_windows']
    jornada_s    = (JORNADA_FI_H - JORNADA_INICI_H) * 3600

    print("\n" + "═"*72)
    print(f"  RUTA OPTIMITZADA — {RUTA} · {DATA}")
    print("═"*72)
    print(f"  {'#':<3} {'Client':<30} {'Zona':<22} {'Arriba':<8}  {'Finestra TW'}")
    print("─"*72)

    nodes_visitats: set[int] = set()
    step_real = 0

    for step, node_idx in enumerate(ruta_indices):
        index  = manager.NodeToIndex(node_idx)
        temps_s = solution.Value(time_dimension.CumulVar(index))
        hora_hhmm = _segons_a_hhmm(temps_s)

        if node_idx == 0:
            if step == 0:
                print(f"  {'0':<3} {'DDI Mollet (sortida)':<30} {'Magatzem':<22} {hora_hhmm:<8}  —")
            else:
                print("─"*72)
                print(f"  {'─':<3} {'DDI Mollet (retorn)':<30} {'Magatzem':<22} {hora_hhmm:<8}  —")
        else:
            nodes_visitats.add(node_idx)
            step_real += 1
            fila = parades_df.iloc[node_idx - 1]
            nom  = str(fila['nom'])[:28]
            zona = str(fila['zona'])[:20]

            tw_i, tw_f = time_windows[node_idx]
            if tw_i == 0 and tw_f == jornada_s:
                tw_str = '—'
            else:
                tw_str = f"{_segons_a_hhmm(tw_i)} – {_segons_a_hhmm(tw_f)}"

            print(f"  {step_real:<3} {nom:<30} {zona:<22} {hora_hhmm:<8}  {tw_str}")

    print("═"*72)

    # Clients saltats (inclosos al context però absents de la ruta)
    tots_nodes = set(range(1, len(parades_df) + 1))
    saltats    = tots_nodes - nodes_visitats

    if saltats:
        _NIVELLS = {
            PENALITZACIO_ALTA:     'ALTA',
            PENALITZACIO_NORMAL:   'NORMAL',
            PENALITZACIO_OPCIONAL: 'OPCIONAL',
        }
        print(f"\n  Clients saltats ({len(saltats)}):")
        for n in sorted(saltats):
            fila = parades_df.iloc[n - 1]
            nom_client   = fila['nom']
            penalitzacio = PRIORITATS_CLIENT.get(nom_client, PENALITZACIO_NORMAL)
            nivell       = _NIVELLS.get(penalitzacio, 'NORMAL')
            print(f"    - {nom_client} (prioritat: {nivell})")

    # Resum final
    temps_total_s = solution.Value(
        time_dimension.CumulVar(manager.NodeToIndex(ruta_indices[-1]))
    )
    print(f"\n  Clients visitats:  {len(nodes_visitats)}/{len(parades_df)}")
    print(f"  Clients saltats:   {len(saltats)}")
    print(f"  Temps total ruta:  {temps_total_s//3600}h {(temps_total_s%3600)//60}min")
    print(f"  Cost (OR-Tools):   {solution.ObjectiveValue():,} seg")
    print()


# ═══════════════════════════════════════════════════════════════════
# MAIN — EXECUCIÓ COMPLETA
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    np.random.seed(42)  # Reproducibilitat

    parades = carregar_parades(RUTA, DATA)
    horaris = carregar_horaris(DIA_SETMANA)
    parades = geocodificar_parades(parades)
    context = preparar_context(parades, horaris)

    resultat = resoldre_ruta(context)
    if resultat:
        ruta_indices, solution, routing, manager, time_dim = resultat
        mostrar_resultat(ruta_indices, solution, routing, manager, time_dim, context)