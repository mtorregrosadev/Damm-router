"""
Damm Smart Truck — Optimitzador de Ruta
Algorisme: VRP amb Time Windows (VRPTW) via OR-Tools

INPUT:  MongoDB (detalle_entrega, horarios_entrega)  →  ruta + data concreta
OUTPUT: Ordre òptim de visita dels clients + hora estimada d'arribada

Ús com a mòdul:
    from router import executar_ruta
    resultat = executar_ruta('DR0006', '19/03/2026', 4)

Ús directe:
    python router.py --ruta DR0006 --data 19/03/2026 --dia 4
"""

import argparse
import json
import sys
import ssl
import certifi
import urllib.request
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path

import numpy as np
import pandas as pd
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

import folium

ssl_context = ssl.create_default_context(cafile=certifi.where())

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR.parent / 'db'))

from mongo import get_db  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
# BLOC 1 — CONSTANTS I CONFIGURACIÓ
# ═══════════════════════════════════════════════════════════════════

DEPOT_LAT = 41.5396
DEPOT_LON =  2.2100

JORNADA_INICI_H = 6
JORNADA_FI_H    = 18

VELOCITAT_KMH = 35

# Temps de servei per defecte (si no hi ha dades de càrrega)
TEMPS_SERVEI_MIN = 12
TEMPS_SERVEI_MINIM_MIN  = 5
TEMPS_SERVEI_MAXIM_MIN  = 30

# Temps de descàrrega per unitat de càrrega
MINUTS_PER_CAIXA   = 0.5
MINUTS_PER_BARRIL  = 2.0
MINUTS_PER_UNITAT  = 0.3

# Distància màxima (metres) per agrupar clients com a parada compartida
DISTANCIA_PARADA_COMPARTIDA_M = 80

TEMPS_DESCÀRREGA: dict[str, int] = {}

PENALITZACIO_ALTA     = 99999
PENALITZACIO_NORMAL   = 3600
PENALITZACIO_OPCIONAL = 500

PRIORITATS_CLIENT: dict[str, int] = {}

ARCS_PROHIBITS: list[tuple[int, int]] = []

ZONES_TRAFIC_MATINAL  = {'MOLLET RAMBLA NOVA', 'MOLLET CAN BORRELL'}
FACTOR_TRAFIC_MATINAL = 1.4
RUSH_HOUR_INICI_S     = 7200
RUSH_HOUR_FI_S        = 10800


# ═══════════════════════════════════════════════════════════════════
# BLOC 2 — CARREGAR DADES
# ═══════════════════════════════════════════════════════════════════

def calcular_temps_descarrega(caixes: float, barrils: float, unitats: float) -> int:
    """Retorna els minuts de descàrrega segons la càrrega real."""
    minuts = (caixes * MINUTS_PER_CAIXA
              + barrils * MINUTS_PER_BARRIL
              + unitats * MINUTS_PER_UNITAT)
    return int(max(TEMPS_SERVEI_MINIM_MIN,
                   min(TEMPS_SERVEI_MAXIM_MIN, minuts)))


def carregar_parades(ruta: str, data: str) -> pd.DataFrame:
    """
    Retorna un DataFrame amb una fila per parada, incloent volums de càrrega.
    Columnes: nom, carrer, cp, poblacio, zona, deudor,
              caixes, barrils, unitats, temps_descarrega_min
    """
    mdb = get_db()

    # Parades bàsiques: una per entrega+deudor
    pipeline = [
        {"$match": {"ruta": ruta, "fecha": data}},
        {"$group": {
            "_id": {"entrega": "$entrega", "deudor": "$destinatario_mc_a_1"},
            "nom":      {"$first": "$nombre_1"},
            "carrer":   {"$first": "$calle"},
            "cp":       {"$first": "$cp"},
            "poblacio": {"$first": "$poblaci_n"},
            "zona":     {"$first": "$zonatransp_1"},
        }},
        {"$project": {
            "_id": 0,
            "entrega": "$_id.entrega",
            "deudor":  "$_id.deudor",
            "nom": 1, "carrer": 1, "cp": 1, "poblacio": 1, "zona": 1,
        }},
    ]
    parades = pd.DataFrame(list(mdb["detalle_entrega"].aggregate(pipeline)))

    # Volums per entrega: fetch i processa en Python (valors guardats com a string)
    docs_vol = list(mdb["detalle_entrega"].find(
        {"ruta": ruta, "fecha": data},
        {"entrega": 1, "un_medida_venta": 1, "cantidad_entrega": 1, "_id": 0}
    ))
    vol_df = pd.DataFrame(docs_vol)
    if not vol_df.empty:
        vol_df['cantidad_entrega'] = pd.to_numeric(
            vol_df['cantidad_entrega'].str.replace(',', '.', regex=False),
            errors='coerce'
        ).fillna(0)
        vol_df['um'] = vol_df['un_medida_venta'].str.upper()
        caixes  = vol_df[vol_df['um'] == 'CAJ'].groupby('entrega')['cantidad_entrega'].sum().rename('caixes')
        barrils = vol_df[vol_df['um'] == 'BRL'].groupby('entrega')['cantidad_entrega'].sum().rename('barrils')
        unitats = vol_df[vol_df['um'] == 'UN'].groupby('entrega')['cantidad_entrega'].sum().rename('unitats')
        volums  = pd.concat([caixes, barrils, unitats], axis=1).fillna(0).reset_index()
    else:
        volums = pd.DataFrame(columns=['entrega', 'caixes', 'barrils', 'unitats'])

    parades = parades.merge(volums, on='entrega', how='left')
    parades[['caixes', 'barrils', 'unitats']] = (
        parades[['caixes', 'barrils', 'unitats']].fillna(0)
    )

    parades['temps_descarrega_min'] = parades.apply(
        lambda r: calcular_temps_descarrega(r['caixes'], r['barrils'], r['unitats']),
        axis=1
    )

    print(f"[OK] {len(parades)} parades carregades per ruta {ruta} del {data}")
    return parades


def carregar_horaris(dia_setmana: int) -> pd.DataFrame:
    """
    Retorna les time windows per al dia de la setmana indicat.
    Columnes: deudor, tw_inici_s, tw_fi_s, tancat
    """
    mdb  = get_db()
    docs = list(mdb["horarios_entrega"].find(
        {"d_a_semana": str(dia_setmana)},
        {"deudor": 1, "horario_inicia_a": 1, "horario_termina_a": 1, "cierre_si_no": 1, "_id": 0}
    ))
    h = pd.DataFrame(docs)
    if h.empty:
        return pd.DataFrame(columns=['deudor', 'tw_inici_s', 'tw_fi_s', 'tancat'])

    h = h.rename(columns={
        "horario_inicia_a":  "Horario inicia a",
        "horario_termina_a": "Horario termina a",
        "cierre_si_no":      "Cierre Si/No",
    })

    def parse_hora(valor):
        if pd.isna(valor) or valor == '':
            return None
        if isinstance(valor, str):
            if 'day' in valor:
                parts = valor.split(',')[-1].strip().split(':')
                hores = 24 + int(parts[0]) + int(parts[1]) / 60
            else:
                parts = valor.split(':')
                hores = int(parts[0]) + int(parts[1]) / 60
        elif isinstance(valor, (int, float)):
            hores = float(valor) * 24
        else:
            hores = 0
        return int((hores - JORNADA_INICI_H) * 3600)

    h['tw_inici_s'] = h['Horario inicia a'].apply(parse_hora)
    h['tw_fi_s']    = h['Horario termina a'].apply(parse_hora)
    h['tancat']     = h['Cierre Si/No'].apply(
        lambda x: x is not None and str(x).strip() != ''
    )

    jornada_s = (JORNADA_FI_H - JORNADA_INICI_H) * 3600
    h['tw_inici_s'] = h['tw_inici_s'].clip(lower=0)
    h['tw_fi_s']    = h['tw_fi_s'].clip(upper=jornada_s)

    return h[['deudor', 'tw_inici_s', 'tw_fi_s', 'tancat']]


# ═══════════════════════════════════════════════════════════════════
# BLOC 3 — GEOCODIFICACIÓ
# ═══════════════════════════════════════════════════════════════════

def geocodificar_parades(parades: pd.DataFrame) -> pd.DataFrame:
    """Afegeix lat i lon a cada parada via Nominatim (OSM)."""
    geolocator = Nominatim(
        user_agent="damm_smart_truck_hackathon", ssl_context=ssl_context
    )
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)

    lats, lons = [], []
    cache: dict = {}

    print(f"\n[INFO] Geocodificant {len(parades)} parades amb Nominatim...")

    for _, row in parades.iterrows():
        carrer   = str(row.get('carrer', '')).strip()
        poblacio = str(row.get('poblacio', '')).strip()
        cp       = str(row.get('cp', '')).strip()
        adreca   = f"{carrer}, {cp} {poblacio}, España"

        if adreca in cache:
            lat, lon = cache[adreca]
        else:
            try:
                location = geocode(adreca)
                if location:
                    lat, lon = location.latitude, location.longitude
                else:
                    location = geocode(f"{cp} {poblacio}, España")
                    if location:
                        lat, lon = location.latitude, location.longitude
                    else:
                        print(f"[AVÍS] No s'ha trobat '{adreca}', usant coordenades magatzem.")
                        lat, lon = DEPOT_LAT, DEPOT_LON
            except Exception as e:
                print(f"[ERROR] Geocodificant {adreca}: {e}")
                lat, lon = DEPOT_LAT, DEPOT_LON
            cache[adreca] = (lat, lon)

        lats.append(lat)
        lons.append(lon)

    parades = parades.copy()
    parades['lat'] = lats
    parades['lon'] = lons
    print("[OK] Geocodificació completada.")
    return parades


# ═══════════════════════════════════════════════════════════════════
# BLOC 4 — PARADES COMPARTIDES (clients molt propers)
# ═══════════════════════════════════════════════════════════════════

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distància en metres entre dos punts GPS."""
    R = 6_371_000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2)
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def agrupar_parades_properes(parades: pd.DataFrame) -> tuple[pd.DataFrame, list[list[int]]]:
    """
    Agrupa clients a menys de DISTANCIA_PARADA_COMPARTIDA_M metres.
    Retorna:
      - nodes_df: DataFrame amb una fila per node OR-Tools
                  (centroide del grup, temps_descarrega sumat, camps del primer client)
      - grups:    llista de llistes d'índexs originals de parades per node
    """
    n = len(parades)
    assignat = [-1] * n  # grup assignat a cada client (-1 = sense grup)
    grups: list[list[int]] = []

    lats = parades['lat'].values
    lons = parades['lon'].values

    for i in range(n):
        if assignat[i] != -1:
            continue
        grup_actual = [i]
        assignat[i] = len(grups)
        for j in range(i + 1, n):
            if assignat[j] != -1:
                continue
            dist = haversine_m(lats[i], lons[i], lats[j], lons[j])
            if dist <= DISTANCIA_PARADA_COMPARTIDA_M:
                grup_actual.append(j)
                assignat[j] = len(grups)
        grups.append(grup_actual)

    # Construir DataFrame de nodes (un per grup)
    files_nodes = []
    for num_grup, membres in enumerate(grups):
        subdf = parades.iloc[membres]
        centroide_lat = subdf['lat'].mean()
        centroide_lon = subdf['lon'].mean()
        temps_total   = subdf['temps_descarrega_min'].sum()
        temps_total   = int(min(TEMPS_SERVEI_MAXIM_MIN, max(TEMPS_SERVEI_MINIM_MIN, temps_total)))
        fila_base     = subdf.iloc[0].to_dict()
        fila_base['lat']                 = centroide_lat
        fila_base['lon']                 = centroide_lon
        fila_base['temps_descarrega_min'] = temps_total
        fila_base['num_grup']             = num_grup
        fila_base['membres_grup']         = membres
        files_nodes.append(fila_base)

    nodes_df = pd.DataFrame(files_nodes).reset_index(drop=True)

    n_compartides = sum(1 for g in grups if len(g) > 1)
    if n_compartides > 0:
        print(f"[INFO] {n_compartides} parades compartides detectades "
              f"({sum(len(g) for g in grups if len(g) > 1)} clients agrupats)")

    return nodes_df, grups


# ═══════════════════════════════════════════════════════════════════
# BLOC 5 — MATRIU DE TEMPS
# ═══════════════════════════════════════════════════════════════════

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Distància en km entre dos punts GPS."""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (sin(dlat / 2) ** 2
         + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2)
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def construir_matriu_temps(locations: list, nodes_df: pd.DataFrame) -> list:
    """
    Construeix la matriu NxN de temps de viatge (en segons) via OSRM Table API.
    El temps de descàrrega de cada node s'afegeix a la columna corresponent.
    locations: [(lat, lon)] — index 0 = dipòsit
    nodes_df:  DataFrame de nodes OR-Tools (sense dipòsit), amb temps_descarrega_min
    """
    n = len(locations)
    coords_str = ";".join(f"{lon},{lat}" for lat, lon in locations)
    url = (f"http://router.project-osrm.org/table/v1/driving/{coords_str}"
           f"?annotations=duration")

    print("\n[INFO] Sol·licitant matriu de temps a OSRM...")
    durations = None
    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'damm_smart_truck_hackathon'}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data.get('code') != 'Ok':
            raise ValueError(f"Error OSRM: {data.get('code')}")
        durations = data['durations']
    except Exception as e:
        print(f"[ERROR] OSRM ha fallat: {e}. Usant Haversine com a alternativa.")

    matriu = []
    for i in range(n):
        fila = []
        for j in range(n):
            if i == j:
                fila.append(0)
            else:
                if durations and durations[i][j] is not None:
                    temps_s = int(durations[i][j])
                else:
                    km = haversine_km(
                        locations[i][0], locations[i][1],
                        locations[j][0], locations[j][1]
                    )
                    temps_s = int((km / VELOCITAT_KMH) * 3600)

                if j > 0:
                    # Temps de descàrrega basat en càrrega real
                    service_min = int(nodes_df.iloc[j - 1]['temps_descarrega_min'])
                    temps_s += service_min * 60

                fila.append(temps_s)
        matriu.append(fila)

    print(f"[OK] Matriu construïda ({n}x{n})")
    return matriu


# ═══════════════════════════════════════════════════════════════════
# BLOC 6 — PREPARAR CONTEXT PER A OR-TOOLS
# ═══════════════════════════════════════════════════════════════════

def preparar_context(parades: pd.DataFrame, horaris: pd.DataFrame) -> dict:
    """
    Construeix el diccionari de dades per a OR-Tools.
    Agrupa parades properes en nodes compartits abans de passar a l'algorisme.
    """
    jornada_s = (JORNADA_FI_H - JORNADA_INICI_H) * 3600

    parades_h = parades.merge(horaris, on='deudor', how='left')
    parades_h['tw_inici_s'] = parades_h['tw_inici_s'].fillna(0).astype(int)
    parades_h['tw_fi_s']    = parades_h['tw_fi_s'].fillna(jornada_s).astype(int)
    parades_h['tancat']     = parades_h['tancat'].fillna(False).astype(bool)

    oberts  = parades_h[~parades_h['tancat']].copy().reset_index(drop=True)
    tancats = parades_h[parades_h['tancat']]
    if len(tancats) > 0:
        print(f"[INFO] {len(tancats)} clients tancats eliminats: "
              f"{tancats['nom'].tolist()}")

    # Agrupar clients molt propers → nodes OR-Tools
    nodes_df, grups = agrupar_parades_properes(oberts)

    # Locations: dipòsit (0) + un punt per node
    locations = [(DEPOT_LAT, DEPOT_LON)]
    for _, row in nodes_df.iterrows():
        locations.append((row['lat'], row['lon']))

    # Time windows: usem la del primer client del grup
    time_windows = [(0, jornada_s)]
    for _, row in nodes_df.iterrows():
        tw_i = max(0, int(row['tw_inici_s']))
        tw_f = min(jornada_s, int(row['tw_fi_s']))
        if tw_f <= tw_i:
            tw_f = jornada_s
        time_windows.append((tw_i, tw_f))

    time_matrix = construir_matriu_temps(locations, nodes_df)

    node_zones: dict[int, str | None] = {0: None}
    for idx, row in enumerate(nodes_df.itertuples(), start=1):
        node_zones[idx] = row.zona

    context = {
        'locations':    locations,
        'time_matrix':  time_matrix,
        'time_windows': time_windows,
        'node_zones':   node_zones,
        'num_vehicles': 1,
        'depot':        0,
        'parades_df':   oberts,   # clients individuals (originals, sense agrupació)
        'nodes_df':     nodes_df, # nodes OR-Tools (agrupats)
        'grups':        grups,    # grups[i] = llista d'índexs originals del node i
    }

    print(f"[OK] Context preparat: {len(oberts)} clients → "
          f"{len(nodes_df)} nodes OR-Tools + 1 dipòsit")
    return context


# ═══════════════════════════════════════════════════════════════════
# BLOC 7 — OR-TOOLS: CONFIGURAR I RESOLDRE
# ═══════════════════════════════════════════════════════════════════

def resoldre_ruta(context: dict):
    """
    Crida OR-Tools VRPTW i retorna l'ordre òptim de visita dels nodes.
    Retorna: (ruta_indices, solution, routing, manager, time_dimension)
    """
    node_zones = context.get('node_zones', {})
    nodes_df   = context['nodes_df']

    manager = pywrapcp.RoutingIndexManager(
        len(context['time_matrix']),
        context['num_vehicles'],
        context['depot']
    )
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node  = manager.IndexToNode(from_index)
        to_node    = manager.IndexToNode(to_index)
        temps_base = context['time_matrix'][from_node][to_node]
        to_zone    = node_zones.get(to_node)
        if to_zone in ZONES_TRAFIC_MATINAL:
            hora_est = context['time_matrix'][0][from_node]
            if RUSH_HOUR_INICI_S <= hora_est <= RUSH_HOUR_FI_S:
                return int(temps_base * FACTOR_TRAFIC_MATINAL)
        return temps_base

    transit_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    routing.AddDimension(
        transit_idx,
        60 * 60,
        (JORNADA_FI_H - JORNADA_INICI_H) * 3600,
        False,
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    for node_idx in range(1, len(context['time_windows'])):
        index = manager.NodeToIndex(node_idx)
        tw_i, tw_f = context['time_windows'][node_idx]
        time_dimension.CumulVar(index).SetRange(tw_i, tw_f)
        nom_node     = nodes_df.iloc[node_idx - 1]['nom']
        penalitzacio = PRIORITATS_CLIENT.get(nom_node, PENALITZACIO_NORMAL)
        routing.AddDisjunction([index], penalitzacio, 1)

    depot_idx = manager.NodeToIndex(context['depot'])
    time_dimension.CumulVar(depot_idx).SetRange(
        0, (JORNADA_FI_H - JORNADA_INICI_H) * 3600
    )

    n_nodes = len(context['time_matrix'])
    for (node_orig, node_dest) in ARCS_PROHIBITS:
        if 0 <= node_orig < n_nodes and 0 <= node_dest < n_nodes:
            routing.NextVar(manager.NodeToIndex(node_orig)).RemoveValue(
                manager.NodeToIndex(node_dest)
            )

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 30
    search_params.log_search = False

    print("\n[...] Resolent amb OR-Tools (màxim 30s)...")
    solution = routing.SolveWithParameters(search_params)

    if not solution:
        print("[ERROR] OR-Tools no ha trobat solució!")
        return []

    ruta_indices = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        ruta_indices.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    ruta_indices.append(manager.IndexToNode(index))

    return ruta_indices, solution, routing, manager, time_dimension


# ═══════════════════════════════════════════════════════════════════
# BLOC 8 — GEOMETRIA REAL DELS TRAMS (OSRM Route API)
# ═══════════════════════════════════════════════════════════════════

def _osrm_geometria_tram(lon_i, lat_i, lon_j, lat_j) -> list:
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon_i},{lat_i};{lon_j},{lat_j}"
        f"?geometries=geojson&overview=full"
    )
    resposta = urllib.request.urlopen(
        urllib.request.Request(url, headers={'User-Agent': 'damm_smart_truck_hackathon'}),
        timeout=30
    )
    dades = json.loads(resposta.read().decode('utf-8'))
    if dades.get('code') != 'Ok':
        raise RuntimeError(f"OSRM Route error: {dades.get('code')}")
    coords = dades['routes'][0]['geometry']['coordinates']
    return [[lat, lon] for lon, lat in coords]


def _segons_a_hhmm(segons: int) -> str:
    hora = JORNADA_INICI_H + segons / 3600
    return f"{int(hora):02d}:{int((hora % 1) * 60):02d}h"


def obtenir_geometria_ruta(ruta_indices, solution, routing, manager,
                           time_dimension, context) -> list:
    """
    Per cada tram, obté la geometria real via OSRM.
    Retorna una llista de dicts per node visitat.
    Cada client individual d'una parada compartida s'expandeix en el resultat.
    """
    nodes_df   = context['nodes_df']
    parades_df = context['parades_df']
    locations  = context['locations']
    grups      = context['grups']

    parades_ruta = []

    for step, node_idx in enumerate(ruta_indices):
        index  = manager.NodeToIndex(node_idx)
        hora_s = solution.Value(time_dimension.CumulVar(index))

        if node_idx == 0:
            if step == 0:
                parades_ruta.append({
                    'ordre':              0,
                    'nom':                'DDI Mollet (sortida)',
                    'zona':               'Magatzem',
                    'lat':                DEPOT_LAT,
                    'lon':                DEPOT_LON,
                    'hora_s':             hora_s,
                    'hora':               _segons_a_hhmm(hora_s),
                    'geometria':          [],
                    'temps_descarrega':   0,
                    'parada_compartida':  None,
                    'clients_grup':       [],
                })
            else:
                lat_i, lon_i = locations[ruta_indices[step - 1]]
                geometria = _osrm_geometria_tram(lon_i, lat_i, DEPOT_LON, DEPOT_LAT)
                parades_ruta.append({
                    'ordre':              step,
                    'nom':                'DDI Mollet (retorn)',
                    'zona':               'Magatzem',
                    'lat':                DEPOT_LAT,
                    'lon':                DEPOT_LON,
                    'hora_s':             hora_s,
                    'hora':               _segons_a_hhmm(hora_s),
                    'geometria':          geometria,
                    'temps_descarrega':   0,
                    'parada_compartida':  None,
                    'clients_grup':       [],
                })
        else:
            fila_node  = nodes_df.iloc[node_idx - 1]
            lat_i, lon_i = locations[ruta_indices[step - 1]]
            lat_j, lon_j = fila_node['lat'], fila_node['lon']
            geometria    = _osrm_geometria_tram(lon_i, lat_i, lon_j, lat_j)

            membres = grups[node_idx - 1]
            es_compartida = len(membres) > 1
            num_parada = len([p for p in parades_ruta
                              if p['parada_compartida'] is not None]) + 1 if es_compartida else None

            # Expandim cada client individual del grup
            for pos_membre, idx_original in enumerate(membres):
                client = parades_df.iloc[idx_original]
                parades_ruta.append({
                    'ordre':              step,
                    'nom':                str(client['nom']),
                    'zona':               str(client['zona']),
                    'lat':                float(client['lat']),
                    'lon':                float(client['lon']),
                    'hora_s':             hora_s,
                    'hora':               _segons_a_hhmm(hora_s),
                    'geometria':          geometria if pos_membre == 0 else [],
                    'temps_descarrega':   int(client['temps_descarrega_min']),
                    'parada_compartida':  num_parada if es_compartida else None,
                    'clients_grup':       (
                        [str(parades_df.iloc[m]['nom']) for m in membres]
                        if es_compartida else []
                    ),
                })

    return parades_ruta


# ═══════════════════════════════════════════════════════════════════
# BLOC 9 — MOSTRAR RESULTAT
# ═══════════════════════════════════════════════════════════════════

def mostrar_resultat(ruta_indices, solution, routing, manager,
                     time_dimension, context, ruta: str, data: str):
    """Imprimeix la ruta optimitzada amb horaris, time windows i resum."""
    nodes_df     = context['nodes_df']
    parades_df   = context['parades_df']
    time_windows = context['time_windows']
    grups        = context['grups']
    jornada_s    = (JORNADA_FI_H - JORNADA_INICI_H) * 3600

    print("\n" + "═" * 76)
    print(f"  RUTA OPTIMITZADA — {ruta} · {data}")
    print("═" * 76)
    print(f"  {'#':<3} {'Client':<30} {'Zona':<20} {'Arriba':<8}  {'Desc.':<6}  {'Finestra TW'}")
    print("─" * 76)

    nodes_visitats: set[int] = set()
    step_real = 0

    for step, node_idx in enumerate(ruta_indices):
        index   = manager.NodeToIndex(node_idx)
        temps_s = solution.Value(time_dimension.CumulVar(index))
        hora    = _segons_a_hhmm(temps_s)

        if node_idx == 0:
            if step == 0:
                print(f"  {'0':<3} {'DDI Mollet (sortida)':<30} {'Magatzem':<20} {hora:<8}  {'—':<6}  —")
            else:
                print("─" * 76)
                print(f"  {'─':<3} {'DDI Mollet (retorn)':<30} {'Magatzem':<20} {hora:<8}  {'—':<6}  —")
        else:
            nodes_visitats.add(node_idx)
            step_real += 1
            fila_node = nodes_df.iloc[node_idx - 1]
            membres   = grups[node_idx - 1]

            tw_i, tw_f = time_windows[node_idx]
            tw_str = ('—' if tw_i == 0 and tw_f == jornada_s
                      else f"{_segons_a_hhmm(tw_i)} – {_segons_a_hhmm(tw_f)}")

            if len(membres) > 1:
                # Parada compartida: mostrem cada client
                print(f"  {step_real:<3} [PARADA COMPARTIDA — {len(membres)} clients]")
                for idx_orig in membres:
                    client    = parades_df.iloc[idx_orig]
                    nom       = str(client['nom'])[:28]
                    zona      = str(client['zona'])[:18]
                    desc_min  = int(client['temps_descarrega_min'])
                    print(f"       ↳ {nom:<28} {zona:<18} {hora:<8}  {desc_min:<4}m  {tw_str}")
            else:
                nom      = str(fila_node['nom'])[:28]
                zona     = str(fila_node['zona'])[:18]
                desc_min = int(fila_node['temps_descarrega_min'])
                print(f"  {step_real:<3} {nom:<30} {zona:<20} {hora:<8}  {desc_min:<4}m  {tw_str}")

    print("═" * 76)

    tots_nodes = set(range(1, len(nodes_df) + 1))
    saltats    = tots_nodes - nodes_visitats

    clients_visitats = sum(len(grups[n - 1]) for n in nodes_visitats)
    clients_saltats  = sum(len(grups[n - 1]) for n in saltats)

    if saltats:
        print(f"\n  Nodes saltats ({len(saltats)}):")
        for n in sorted(saltats):
            for idx_orig in grups[n - 1]:
                nom_c = parades_df.iloc[idx_orig]['nom']
                pen   = PRIORITATS_CLIENT.get(nom_c, PENALITZACIO_NORMAL)
                print(f"    - {nom_c} (pen: {pen})")

    temps_total_s = solution.Value(
        time_dimension.CumulVar(manager.NodeToIndex(ruta_indices[-1]))
    )
    print(f"\n  Clients visitats:  {clients_visitats}/{len(parades_df)}")
    print(f"  Clients saltats:   {clients_saltats}")
    print(f"  Temps total ruta:  {temps_total_s // 3600}h {(temps_total_s % 3600) // 60}min")
    print(f"  Cost (OR-Tools):   {solution.ObjectiveValue():,} seg")
    print()

    return clients_visitats, clients_saltats, temps_total_s


# ═══════════════════════════════════════════════════════════════════
# BLOC 10 — EXPORTAR MAPA I JSON
# ═══════════════════════════════════════════════════════════════════

_COLORS_MAPA = [
    'red', 'blue', 'green', 'purple', 'orange',
    'darkred', 'darkblue', 'darkgreen', 'cadetblue', 'pink',
]


def exportar_mapa_i_json(parades_ruta: list, ruta: str, data: str) -> None:
    """
    Genera ruta_optima.json i ruta_damm.html a partir de les parades calculades.
    Les parades compartides es marquen explícitament.
    """
    # ── JSON ──────────────────────────────────────────────────────
    dades_json = [
        {k: v for k, v in p.items() if k != 'geometria'}
        for p in parades_ruta
    ]
    with open('ruta_optima.json', 'w', encoding='utf-8') as f:
        json.dump(
            {'ruta': ruta, 'data': data, 'parades': dades_json},
            f, ensure_ascii=False, indent=2
        )
    print("[OK] Exportat ruta_optima.json")

    # ── Mapa Folium ───────────────────────────────────────────────
    mapa = folium.Map(
        location=[DEPOT_LAT, DEPOT_LON],
        zoom_start=13,
        tiles='OpenStreetMap',
    )

    for parada in parades_ruta:
        if parada['geometria']:
            folium.PolyLine(
                locations=parada['geometria'],
                color='royalblue',
                weight=4,
                opacity=0.8,
            ).add_to(mapa)

        ordre       = parada['ordre']
        es_magatzem = parada['nom'] in ('DDI Mollet (sortida)', 'DDI Mollet (retorn)')

        if es_magatzem:
            icona = folium.Icon(color='black', icon='home', prefix='fa')
            popup = f"<b>{parada['nom']}</b><br>{parada['hora']}"
        else:
            color = _COLORS_MAPA[ordre % len(_COLORS_MAPA)]
            icona = folium.Icon(color=color, icon='truck', prefix='fa')
            compartida_info = (
                f"<br><i>Parada compartida #{parada['parada_compartida']}</i>"
                if parada['parada_compartida'] else ''
            )
            popup = (
                f"<b>{ordre}. {parada['nom']}</b><br>"
                f"Zona: {parada['zona']}<br>"
                f"Arriba: {parada['hora']}<br>"
                f"Descàrrega: {parada['temps_descarrega']} min"
                f"{compartida_info}"
            )

        folium.Marker(
            location=[parada['lat'], parada['lon']],
            popup=folium.Popup(popup, max_width=280),
            tooltip=f"{ordre}. {parada['nom']} · {parada['hora']}",
            icon=icona,
        ).add_to(mapa)

    mapa.save('ruta_damm.html')
    print("[OK] Exportat ruta_damm.html")


# ═══════════════════════════════════════════════════════════════════
# BLOC 11 — GUARDAR RESULTATS A LA BASE DE DADES
# ═══════════════════════════════════════════════════════════════════

def guardar_a_db(parades_ruta: list, ruta: str, data: str,
                 clients_visitats: int, clients_saltats: int,
                 temps_total_s: int) -> None:
    """
    Persisteix els resultats a MongoDB:
      - ruta_punts:  un document per client individual
      - ruta_resum:  un document per execució
    """
    mdb = get_db()

    mdb["ruta_punts"].delete_many({"ruta": ruta, "data": data})
    mdb["ruta_resum"].delete_many({"ruta": ruta, "data": data})

    punts = []
    for p in parades_ruta:
        if p['nom'] in ('DDI Mollet (sortida)', 'DDI Mollet (retorn)'):
            continue
        punts.append({
            "ruta": ruta, "data": data,
            "ordre": p['ordre'], "nom": p['nom'], "zona": p['zona'],
            "lat": p['lat'], "lon": p['lon'],
            "hora": p['hora'], "hora_s": p['hora_s'],
            "temps_descarrega": p['temps_descarrega'],
            "parada_compartida": p['parada_compartida'],
            "geometria_json": json.dumps(p['geometria'], ensure_ascii=False) if p['geometria'] else None,
        })
    if punts:
        mdb["ruta_punts"].insert_many(punts)

    mdb["ruta_resum"].insert_one({
        "ruta": ruta, "data": data,
        "total_parades": clients_visitats + clients_saltats,
        "clients_visitats": clients_visitats,
        "clients_saltats": clients_saltats,
        "temps_total_min": temps_total_s // 60,
    })
    print(f"[OK] Resultats guardats a MongoDB "
          f"(ruta_punts: {clients_visitats} docs, ruta_resum: 1 doc)")


# ═══════════════════════════════════════════════════════════════════
# BLOC 12 — FUNCIÓ PÚBLICA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

def executar_ruta(ruta: str, data: str, dia_setmana: int) -> dict:
    """
    Executa el flux complet d'optimització de ruta.

    Paràmetres:
      ruta:        identificador de ruta (p.ex. 'DR0006')
      data:        data en format 'DD/MM/YYYY'
      dia_setmana: 1=Dll, 2=Dm, 3=Dc, 4=Dj, 5=Dv

    Retorna un diccionari amb:
      - ruta, data
      - parades_ruta:       llista de dicts per parada
      - clients_visitats:   int
      - clients_saltats:    int
      - temps_total_min:    int
    """
    np.random.seed(42)

    parades = carregar_parades(ruta, data)
    horaris = carregar_horaris(dia_setmana)
    parades = geocodificar_parades(parades)
    context = preparar_context(parades, horaris)

    resultat = resoldre_ruta(context)
    if not resultat:
        return {'ruta': ruta, 'data': data, 'error': 'OR-Tools no ha trobat solució'}

    ruta_indices, solution, routing, manager, time_dim = resultat

    clients_visitats, clients_saltats, temps_total_s = mostrar_resultat(
        ruta_indices, solution, routing, manager, time_dim, context, ruta, data
    )

    print("\n[...] Obtenint geometria real dels trams via OSRM...")
    parades_ruta = obtenir_geometria_ruta(
        ruta_indices, solution, routing, manager, time_dim, context
    )

    exportar_mapa_i_json(parades_ruta, ruta, data)
    guardar_a_db(parades_ruta, ruta, data,
                 clients_visitats, clients_saltats, temps_total_s)

    return {
        'ruta':             ruta,
        'data':             data,
        'parades_ruta':     parades_ruta,
        'clients_visitats': clients_visitats,
        'clients_saltats':  clients_saltats,
        'temps_total_min':  temps_total_s // 60,
    }


# ═══════════════════════════════════════════════════════════════════
# MAIN — ÚS DIRECTE
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Damm Smart Truck — Optimitzador de Ruta")
    parser.add_argument("--ruta", type=str, default="DR0006")
    parser.add_argument("--data", type=str, default="19/03/2026")
    parser.add_argument("--dia",  type=int, default=4,
                        help="Dia de la setmana (1=Dll … 5=Dv)")
    args = parser.parse_args()

    executar_ruta(args.ruta, args.data, args.dia)
