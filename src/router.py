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

# Temps de servei per parada (minuts) — temps per descarregar
TEMPS_SERVEI_MIN = 12

# Penalització per no complir una time window (en temps equivalent)
# Si és molt alt, OR-Tools intentarà a tota costa complir-la
PENALITZACIO_TW = 3600  # 1 hora de penalització


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
        # Convertir a segons des de JORNADA_INICI_H
        return int((hores - JORNADA_INICI_H) * 3600)

    h['tw_inici_s'] = h['Horario inicia a'].apply(parse_hora)
    h['tw_fi_s']    = h['Horario termina a'].apply(parse_hora)
    h['tancat']     = h['Cierre Si/No'].notna()

    # Clamp: si inici < 0, posem 0 (client disponible des del principi)
    # Si fi > jornada total, posem el límit de la jornada
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
            # Petita variació aleatòria per diferenciar clients de la mateixa zona
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

def construir_matriu_temps(locations: list) -> list:
    """
    Construeix la matriu NxN de temps de viatge en segons.
    locations: [(lat0,lon0), (lat1,lon1), ...] — index 0 = dipòsit
    
    OR-Tools necessita enters, multipliquem per 10 per tenir precisió
    sense decimals (ex: 1.5 min → 15, 12.3 min → 123).
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
                # Temps en segments de 6 segons (×10 precisió)
                temps_min = (km / VELOCITAT_KMH) * 60
                temps_s   = int(temps_min * 60)
                # Afegir temps de servei al destí (descàrrega)
                temps_s  += TEMPS_SERVEI_MIN * 60
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
      - num_vehicles:   sempre 1 (un camió, una ruta)
      - depot:          0 (índex del dipòsit)
    """
    jornada_s = (JORNADA_FI_H - JORNADA_INICI_H) * 3600

    # Merge parades + horaris per obtenir les time windows
    parades_h = parades.merge(
        horaris, on='deudor', how='left'
    )

    # Defecte si no té horari registrat: disponible tota la jornada
    parades_h['tw_inici_s'] = parades_h['tw_inici_s'].fillna(0).astype(int)
    parades_h['tw_fi_s']    = parades_h['tw_fi_s'].fillna(jornada_s).astype(int)
    parades_h['tancat']     = parades_h['tancat'].fillna(False).astype(bool)

    # Eliminar clients tancats aquell dia
    oberts = parades_h[~parades_h['tancat']].copy()
    tancats = parades_h[parades_h['tancat']]
    if len(tancats) > 0:
        print(f"[INFO] {len(tancats)} clients tancats eliminats: "
              f"{tancats['nom'].tolist()}")

    # Construir llista de locations: dipòsit primer
    locations = [(DEPOT_LAT, DEPOT_LON)]  # index 0 = DDI Mollet
    for _, row in oberts.iterrows():
        locations.append((row['lat'], row['lon']))

    # Time windows: dipòsit disponible tota la jornada
    time_windows = [(0, jornada_s)]
    for _, row in oberts.iterrows():
        tw_i = max(0, row['tw_inici_s'])
        tw_f = min(jornada_s, row['tw_fi_s'])
        # Assegurar que tw_f > tw_i
        if tw_f <= tw_i:
            tw_f = jornada_s
        time_windows.append((tw_i, tw_f))

    time_matrix = construir_matriu_temps(locations)

    context = {
        'locations':     locations,
        'time_matrix':   time_matrix,
        'time_windows':  time_windows,
        'num_vehicles':  1,
        'depot':         0,
        'parades_df':    oberts.reset_index(drop=True),
    }

    print(f"[OK] Context preparat: {len(locations)-1} clients + 1 dipòsit")
    print(f"     Matriu de temps: {len(time_matrix)}x{len(time_matrix[0])}")
    return context


# ═══════════════════════════════════════════════════════════════════
# BLOC 6 — OR-TOOLS: CONFIGURAR I RESOLDRE
# ═══════════════════════════════════════════════════════════════════

def resoldre_ruta(context: dict) -> list:
    """
    Crida a OR-Tools VRPTW i retorna l'ordre òptim de visita.
    Retorna llista d'índexs: [0, 3, 1, 5, ..., 0]  (0 = dipòsit)
    """
    # ── Pas 1: Crear el manager ──────────────────────────────────
    # Paràmetres: nombre de nodes, nombre de vehicles, índex del dipòsit
    manager = pywrapcp.RoutingIndexManager(
        len(context['time_matrix']),   # N nodes (dipòsit + clients)
        context['num_vehicles'],        # 1 camió
        context['depot']               # índex del dipòsit = 0
    )

    # ── Pas 2: Crear el model de routing ─────────────────────────
    routing = pywrapcp.RoutingModel(manager)

    # ── Pas 3: Definir la funció de cost (temps de viatge) ───────
    def time_callback(from_index, to_index):
        """Retorna el temps en segons entre dos nodes"""
        from_node = manager.IndexToNode(from_index)
        to_node   = manager.IndexToNode(to_index)
        return context['time_matrix'][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)

    # Definir que el cost a minimitzar és el temps total de ruta
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # ── Pas 4: Afegir la dimensió de temps (Time Windows) ────────
    routing.AddDimension(
        transit_callback_index,
        60 * 60,          # slack_max: el camió pot esperar fins 1h si arriba aviat
        (JORNADA_FI_H - JORNADA_INICI_H) * 3600,  # màxim temps total de jornada
        False,            # no forcem que comenci a 0 (el camió pot sortir quan vulgui)
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    # ── Pas 5: Aplicar les Time Windows a cada node ──────────────
    for node_idx in range(1, len(context['time_windows'])):  # saltem el dipòsit
        index = manager.NodeToIndex(node_idx)
        tw_inici, tw_fi = context['time_windows'][node_idx]

        time_dimension.CumulVar(index).SetRange(tw_inici, tw_fi)

        # Penalitzar (no eliminar) si no es pot complir la time window
        routing.AddDisjunction(
            [index],
            PENALITZACIO_TW,  # cost de saltar-se aquest client
            1                  # màxim 1 node per disjunció
        )

    # ── Pas 6: Restricció del dipòsit ────────────────────────────
    # El camió pot sortir i tornar en qualsevol moment de la jornada
    depot_start = manager.NodeToIndex(context['depot'])
    time_dimension.CumulVar(depot_start).SetRange(0, (JORNADA_FI_H - JORNADA_INICI_H) * 3600)

    # ── Pas 7: Estratègia de cerca ───────────────────────────────
    search_params = pywrapcp.DefaultRoutingSearchParameters()

    # Solució inicial: PATH_CHEAPEST_ARC (greedy ràpid per inicialitzar)
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    # Millorar amb Guided Local Search (el millor per VRPTW)
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

    # Temps màxim de cerca: 30 segons (més que suficient per 22 parades)
    search_params.time_limit.seconds = 30
    search_params.log_search = False

    # ── Pas 8: RESOLDRE ──────────────────────────────────────────
    print("\n[...] Resolent amb OR-Tools (màxim 30s)...")
    solution = routing.SolveWithParameters(search_params)

    if not solution:
        print("[ERROR] OR-Tools no ha trobat solució!")
        return []

    # ── Pas 9: Extreure la ruta de la solució ────────────────────
    ruta_indices = []
    index = routing.Start(0)  # vehicle 0, node inicial (dipòsit)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        ruta_indices.append(node)
        index = solution.Value(routing.NextVar(index))
    ruta_indices.append(manager.IndexToNode(index))  # afegir dipòsit final

    return ruta_indices, solution, routing, manager, time_dimension


# ═══════════════════════════════════════════════════════════════════
# BLOC 7 — FORMATAR I MOSTRAR RESULTAT
# ═══════════════════════════════════════════════════════════════════

def mostrar_resultat(ruta_indices, solution, routing, manager,
                     time_dimension, context):
    """Imprimeix la ruta optimitzada amb horaris i detalls"""
    parades_df = context['parades_df']
    jornada_inici = JORNADA_INICI_H * 3600  # per convertir a hora real

    print("\n" + "═"*65)
    print(f"  RUTA OPTIMITZADA — {RUTA} · {DATA}")
    print("═"*65)
    print(f"  {'#':<3} {'Client':<30} {'Zona':<22} {'Arriba':<8}")
    print("─"*65)

    total_km = 0
    for step, node_idx in enumerate(ruta_indices):
        index = manager.NodeToIndex(node_idx)
        temps_s = solution.Value(time_dimension.CumulVar(index))
        hora_real = JORNADA_INICI_H + temps_s / 3600
        hora_hhmm = f"{int(hora_real):02d}:{int((hora_real % 1)*60):02d}h"

        if node_idx == 0:
            if step == 0:
                print(f"  {'0':<3} {'DDI Mollet (sortida)':<30} {'Magatzem':<22} {hora_hhmm}")
            else:
                print("─"*65)
                print(f"  {'─':<3} {'DDI Mollet (retorn)':<30} {'Magatzem':<22} {hora_hhmm}")
        else:
            fila = parades_df.iloc[node_idx - 1]
            nom  = fila['nom'][:28]
            zona = fila['zona'][:20]
            print(f"  {step:<3} {nom:<30} {zona:<22} {hora_hhmm}")

    print("═"*65)

    # Resum
    inici_idx = manager.NodeToIndex(0)
    temps_total_s = solution.Value(time_dimension.CumulVar(
        manager.NodeToIndex(ruta_indices[-1])
    ))
    clients_visitats = len(ruta_indices) - 2
    print(f"\n  Clients visitats:  {clients_visitats}/{len(parades_df)}")
    cost_total = solution.ObjectiveValue()
    print(f"  Temps total ruta:  {temps_total_s//3600}h {(temps_total_s%3600)//60}min")
    print(f"  Cost (OR-Tools):   {cost_total:,} seg")
    print()


# ═══════════════════════════════════════════════════════════════════
# MAIN — EXECUCIÓ COMPLETA
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    np.random.seed(42)  # Reproducibilitat

    # 1. Carregar dades
    parades  = carregar_parades(RUTA, DATA)
    horaris  = carregar_horaris(DIA_SETMANA)

    # 2. Geocodificar (coordenades aproximades per zona)
    parades  = geocodificar_parades(parades)

    # 3. Preparar context per OR-Tools
    context  = preparar_context(parades, horaris)

    # 4. Resoldre
    resultat = resoldre_ruta(context)
    if resultat:
        ruta_indices, solution, routing, manager, time_dim = resultat
        mostrar_resultat(ruta_indices, solution, routing, manager, time_dim, context)