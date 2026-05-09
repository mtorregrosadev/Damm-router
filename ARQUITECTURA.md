# Arquitectura del mòdul `router.py` — Damm Smart Truck

Documentació tècnica per integrar l'optimitzador de rutes en una aplicació web.

---

## 1. Visió general

El mòdul calcula l'ordre òptim de visita per a un camió de repartiment donada una ruta i una data concreta. Implementa un problema de **VRP amb Time Windows (VRPTW)**: un vehicle, N clients amb franges horàries i una jornada laboral limitada.

### Llibreries principals

| Llibreria | Versió mínima | Ús |
|---|---|---|
| `ortools` | 9.x | Resolució del problema d'optimització |
| `pandas` / `numpy` | — | Manipulació de dades tabulars |
| `geopy` | — | Geocodificació real d'adreces (Nominatim/OSM) |
| `folium` | — | Generació del mapa HTML interactiu |
| `sqlite3` | stdlib | Lectura de dades d'entrada i escriptura de resultats |
| `requests` / `urllib` | — | Crida a OSRM (matriu de temps i geometria de trams) |

### Fitxers necessaris

```
Damm-router/
├── src/
│   ├── router.py          ← mòdul principal (API pública)
│   └── hackaton.db        ← base de dades SQLite (veure secció 4)
├── router.py              ← script autònom (versió hackathon, llegeix Excel)
├── BD/
│   ├── Hackaton.xlsx      ← dades d'entregues (només per al script root)
│   └── Horarios_Entrega.XLSX ← franges horàries (ídem)
```

**Hi ha dues versions del mòdul:**

| Fitxer | Entrada | Geocodificació | Parades compartides | DB | Ús recomanat |
|---|---|---|---|---|---|
| `src/router.py` | `hackaton.db` | Nominatim (real) | Sí | Sí | Integració web / producció |
| `router.py` (root) | Excel directe | Per zona (proxy) | No | No | Prototip ràpid / hackathon |

La resta d'aquest document descriu **`src/router.py`**, que és el mòdul amb API pública.

---

## 2. Com cridar-lo des d'un backend

### Instal·lació

```bash
pip install ortools pandas numpy geopy folium certifi requests
```

### Crida bàsica

```python
import sys
sys.path.insert(0, 'src/')          # assegurar que Python troba el mòdul
from router import executar_ruta

resultat = executar_ruta(
    ruta='DR0006',
    data='19/03/2026',
    dia_setmana=4           # 1=Dll, 2=Dm, 3=Dc, 4=Dj, 5=Dv
)
```

### Signatura completa

```python
def executar_ruta(ruta: str, data: str, dia_setmana: int) -> dict
```

### Paràmetres d'entrada

| Paràmetre | Tipus | Exemple | Descripció |
|---|---|---|---|
| `ruta` | `str` | `'DR0006'` | Identificador de ruta (camp `Ruta` a l'Excel / `ruta` a la DB) |
| `data` | `str` | `'19/03/2026'` | Data en format `DD/MM/YYYY` (ha de coincidir exactament amb la DB) |
| `dia_setmana` | `int` | `4` | Dia per filtrar horaris: 1=Dll, 2=Dm, 3=Dc, 4=Dj, 5=Dv |

### Diccionari retornat

```python
{
    "ruta":             "DR0006",
    "data":             "19/03/2026",
    "parades_ruta":     [ ... ],    # llista de dicts (veure sota)
    "clients_visitats": 28,
    "clients_saltats":  2,          # clients amb time window impossible
    "temps_total_min":  290
}
```

En cas d'error d'OR-Tools (sense solució):
```python
{
    "ruta":  "DR0006",
    "data":  "19/03/2026",
    "error": "OR-Tools no ha trobat solució"
}
```

### Estructura d'una parada (element de `parades_ruta`)

Cada element representa **un client individual**, fins i tot si comparteix parada física amb altres. El dipòsit apareix com a primer i últim element.

```json
{
  "ordre": 1,
  "nom": "CASA MAURA",
  "zona": "MOLLET CAN BORRELL",
  "lat": 41.5397151,
  "lon": 2.2137043,
  "hora_s": 1705,
  "hora": "06:28h",
  "temps_descarrega": 16,
  "parada_compartida": 1,
  "clients_grup": [
    "CASA MAURA",
    "PA I CAFETERIA DE L'AVIA",
    "CUENCA BAR"
  ],
  "geometria": [
    [41.5396, 2.2100],
    [41.5397, 2.2105],
    ...
  ]
}
```

| Camp | Tipus | Descripció |
|---|---|---|
| `ordre` | `int` | Posició a la ruta (0 = dipòsit sortida, N+1 = dipòsit retorn) |
| `nom` | `str` | Nom comercial del client |
| `zona` | `str` | Zona de transport |
| `lat`, `lon` | `float` | Coordenades GPS del client |
| `hora_s` | `int` | Segons des de l'inici de la jornada (06:00h = 0s) |
| `hora` | `str` | Hora d'arribada en format `HH:MMh` |
| `temps_descarrega` | `int` | Minuts de descàrrega calculats per volum real |
| `parada_compartida` | `int \| null` | ID del grup si el client comparteix parada física; `null` si és únic |
| `clients_grup` | `list[str]` | Noms dels clients del mateix grup; llista buida si no comparteix |
| `geometria` | `list[[lat, lon]]` | Coordenades del tram que porta fins aquest client (buit si primer o membres que no encapçalen el grup) |

> **Nota sobre `hora_s`:** Convertir a hora real: `hora_real = 06:00 + hora_s / 3600`. Exemple: `hora_s = 1705` → `06:00 + 28.4min` → `06:28h`.

---

## 3. Flux intern pas a pas

```
BD/hackaton.db
      │
      ▼
[BLOC 2] carregar_parades + carregar_horaris    (~0.5s)
      │
      ▼
[BLOC 3] geocodificar_parades (Nominatim)       (~1.1s × N clients)
      │
      ▼
[BLOC 4] agrupar_parades_properes               (~instant)
      │  (clients a <80m → un sol node OR-Tools)
      ▼
[BLOC 5] construir_matriu_temps (OSRM Table)    (~2–5s)
      │  (matriu NxN de temps de viatge en segons)
      ▼
[BLOC 6] preparar_context                       (~instant)
      │
      ▼
[BLOC 7] resoldre_ruta (OR-Tools VRPTW)         (fins a 30s)
      │
      ▼
[BLOC 8] obtenir_geometria_ruta (OSRM Route)    (~1s × N trams)
      │
      ▼
[BLOC 9] exportar_mapa_i_json + guardar_a_db
      │
      ├──► ruta_optima.json
      ├──► ruta_damm.html
      └──► hackaton.db (taules ruta_punts, ruta_resum)
```

### BLOC 2 — Càrrega de dades

**Rep:** `ruta: str`, `data: str`, `dia_setmana: int`

**Fa:**
- Llegeix `detalle_entrega` de la DB filtrant per ruta i data. Agrupa per `entrega` i `destinatario_mc_a_1`.
- Calcula el volum de càrrega per entrega (caixes `CAJ`, barrils `BRL`, unitats `UN`).
- Llegeix `horarios_entrega` filtrant per `dia_semana`, parseig d'hores a segons desde les 06:00.

**Retorna:** dos DataFrames (`parades`, `horaris`)

**Triga:** ~0.5s (lectura SQLite local)

---

### BLOC 3 — Geocodificació (Nominatim)

**Rep:** DataFrame de parades amb `carrer`, `cp`, `poblacio`

**Fa:**
- Per cada parada construeix l'adreça completa: `"Carrer, CP Població, España"`.
- Crida Nominatim (OpenStreetMap) amb *rate limiter* de 1.1s entre peticions (límit de l'API gratuïta).
- Si no troba l'adreça exacta, intenta `"CP Població, España"`.
- Fallback: coordenades del magatzem DDI Mollet.
- Utilitza caché intern per no repetir geocodificacions de la mateixa adreça.

**Retorna:** DataFrame amb columnes `lat` i `lon` afegides

**Triga:** `N_clients × 1.1s` → 20 clients ≈ 22s, 40 clients ≈ 44s

> **Atenció per a producció:** Nominatim té un límit de 1 petició/segon. Per a volums alts, considerar Google Maps Geocoding API o pre-geocodificar i cachear a la DB.

---

### BLOC 4 — Parades compartides

**Rep:** DataFrame de parades geocodificades

**Fa:**
- Calcula distància Haversine entre tots els parells de clients.
- Agrupa els que estan a menys de `DISTANCIA_PARADA_COMPARTIDA_M = 80m`.
- Per a cada grup: centroide de coordenades, suma de temps de descàrrega (amb màxim de 30min), primer client com a representant del node OR-Tools.

**Retorna:** `(nodes_df, grups)`
- `nodes_df`: un DataFrame amb una fila per node OR-Tools (pot ser menys files que clients)
- `grups`: `list[list[int]]` — `grups[i]` conté els índexs dels clients originals del node `i`

**Triga:** O(N²) → instantani fins a 100 clients

---

### BLOC 5 — Matriu de temps (OSRM Table API)

**Rep:** `locations: [(lat,lon)]` — índex 0 = dipòsit, índexos 1..N = nodes

**Fa:**
- Crida `http://router.project-osrm.org/table/v1/driving/{coords}` amb tots els nodes.
- Obté la matriu NxN de temps de conducció reals (en segons).
- Afegeix el temps de descàrrega de cada node a la columna corresponent: `temps_total[i][j] = conducció[i][j] + descàrrega[j]`.
- Fallback si OSRM falla: càlcul Haversine amb velocitat = `VELOCITAT_KMH`.

**Retorna:** matriu `list[list[int]]` de NxN

**Triga:** 1–5s (una sola petició HTTP independentment del nombre de nodes)

---

### BLOC 6 — Context OR-Tools

**Fa:** Uneix parades + horaris, elimina clients tancats (`Cierre Si/No` informat), construeix el diccionari que necessita OR-Tools:

```python
context = {
    'locations':    [(lat, lon), ...],   # índex 0 = dipòsit
    'time_matrix':  [[int, ...], ...],   # NxN, en segons
    'time_windows': [(inici_s, fi_s)],  # una per node
    'node_zones':   {idx: zona},
    'num_vehicles': 1,
    'depot':        0,
    'parades_df':   DataFrame,           # clients individuals originals
    'nodes_df':     DataFrame,           # nodes OR-Tools (agrupats)
    'grups':        [[int], ...],
}
```

---

### BLOC 7 — OR-Tools VRPTW (`resoldre_ruta`)

**Rep:** `context: dict`

**Fa:**
1. Crea `RoutingIndexManager` i `RoutingModel` per 1 vehicle.
2. Registra la funció de cost (`time_callback`) que retorna el temps de viatge entre dos nodes, aplicant el factor de tràfic matinal (`×1.4`) per zones concretes entre les 08:00 i les 09:00.
3. Afegeix la dimensió `Time` (slack màxim d'espera: 1h).
4. Per a cada node client: `SetRange(tw_inici, tw_fi)` + `AddDisjunction([index], penalitzacio, 1)` — la penalització controla si OR-Tools prefereix saltar el client o no.
5. Aplica els arcs prohibits configurats a `ARCS_PROHIBITS`.
6. Executa `PATH_CHEAPEST_ARC` + `GUIDED_LOCAL_SEARCH` amb límit de 30s.

**Retorna:** `(ruta_indices, solution, routing, manager, time_dimension)`
- `ruta_indices`: llista d'índexs de nodes en l'ordre òptim (comença i acaba amb 0 = dipòsit)

**Triga:** fins a 30s (temps configurable a `search_params.time_limit.seconds`)

> **Qualitat de la solució:** OR-Tools pot trobar la solució òptima en pocs segons per a rutes petites (<20 nodes). Per a rutes grans (>40 nodes), la qualitat depèn del temps assignat.

---

### BLOC 8 — Geometria real dels trams (OSRM Route API)

**Rep:** `ruta_indices`, objectes de solució OR-Tools, `context`

**Fa:**
- Per cada tram consecutiu de la ruta (node `i` → node `i+1`), crida `http://router.project-osrm.org/route/v1/driving/{lon_i},{lat_i};{lon_j},{lat_j}?geometries=geojson&overview=full`.
- Extreu la polilínia de carrers reals.
- Expandeix cada node OR-Tools als seus clients individuals (parades compartides → múltiples files al resultat, compartint la mateixa `hora_s` i `ordre`).

**Retorna:** `list[dict]` — una entrada per client individual + dipòsit sortida + dipòsit retorn

**Triga:** ~1s × N_trams (crida HTTP per tram)

---

### BLOC 9 — Exportació

**`exportar_mapa_i_json`** — Genera dos fitxers:
- `ruta_optima.json` — totes les dades de la ruta **sense** el camp `geometria` (redueix la mida)
- `ruta_damm.html` — mapa Folium amb polilínies de carrers reals, marcadors per client i popups

**`guardar_a_db`** — Insereix a `hackaton.db`:
- `ruta_punts` — una fila per client visitat (exclou dipòsit)
- `ruta_resum` — una fila resum per execució

---

## 4. La base de dades (`hackaton.db`)

### Taules de resultats (creades i escrites per `router.py`)

#### `ruta_punts`
Un registre per client visitat en cada execució.

| Camp | Tipus | Descripció |
|---|---|---|
| `id` | `INTEGER PK AUTOINCREMENT` | — |
| `ruta` | `TEXT` | Identificador de ruta (`DR0006`) |
| `data` | `TEXT` | Data en format `DD/MM/YYYY` |
| `ordre` | `INTEGER` | Posició a la ruta calculada per OR-Tools |
| `nom` | `TEXT` | Nom comercial del client |
| `zona` | `TEXT` | Zona de transport |
| `lat`, `lon` | `REAL` | Coordenades GPS |
| `hora` | `TEXT` | Hora d'arribada (`HH:MMh`) |
| `hora_s` | `INTEGER` | Segons des de l'inici de la jornada |
| `temps_descarrega` | `INTEGER` | Minuts de descàrrega |
| `parada_compartida` | `INTEGER \| NULL` | ID del grup si comparteix parada |
| `geometria_json` | `TEXT` | JSON stringificat de la polilínia del tram anterior |

#### `ruta_resum`
Un registre per execució completa.

| Camp | Tipus | Descripció |
|---|---|---|
| `id` | `INTEGER PK AUTOINCREMENT` | — |
| `ruta` | `TEXT` | Identificador de ruta |
| `data` | `TEXT` | Data |
| `total_parades` | `INTEGER` | Total de clients (visitats + saltats) |
| `clients_visitats` | `INTEGER` | Clients efectivament servits |
| `clients_saltats` | `INTEGER` | Clients omesos per time window impossible |
| `temps_total_min` | `INTEGER` | Durada total de la ruta en minuts |
| `creat_a` | `TEXT` | Timestamp de l'execució (`CURRENT_TIMESTAMP`) |

---

### Taula pre-existent (estructura alternativa, actualment buida)

#### `resultado_rutas_ortools`
Estructura preparada per a integració amb Google Maps Routes API. Conté camps per a distàncies acumulades (`distancia_acumulada_m`) i durades (`duracion_acumulada_s`) que el mòdul actual no omple.

---

### Vistes de dades d'entrada

| Vista | Descripció |
|---|---|
| `vw_entregas_enriquecidas` | Entregues enriquides amb adreça completa, material, zona i horaris |
| `vw_ortools_paradas` | Una fila per parada OR-Tools (agrupa entregues del mateix client) |
| `vw_direcciones_cliente` | Adreça canònica per client (deduplicada) |
| `vw_horarios_cliente` | Finestres horàries per client i indicador de prioritat |

---

### Queries útils per a la web

**Última ruta calculada:**
```sql
SELECT ruta, data, clients_visitats, clients_saltats, temps_total_min, creat_a
FROM ruta_resum
ORDER BY creat_a DESC
LIMIT 1;
```

**Punts de la ruta en ordre per mostrar al mapa:**
```sql
SELECT ordre, nom, zona, lat, lon, hora, hora_s, temps_descarrega, parada_compartida
FROM ruta_punts
WHERE ruta = 'DR0006' AND data = '19/03/2026'
ORDER BY ordre ASC;
```

**Clients amb parada compartida (per mostrar-los agrupats):**
```sql
SELECT parada_compartida, GROUP_CONCAT(nom, ', ') AS clients, ordre, hora, lat, lon
FROM ruta_punts
WHERE ruta = 'DR0006' AND data = '19/03/2026'
  AND parada_compartida IS NOT NULL
GROUP BY parada_compartida
ORDER BY ordre;
```

**Resum de totes les execucions d'una ruta:**
```sql
SELECT data, clients_visitats, clients_saltats, temps_total_min, creat_a
FROM ruta_resum
WHERE ruta = 'DR0006'
ORDER BY creat_a DESC;
```

---

## 5. Com integrar el mapa

### Fitxer `ruta_optima.json`

El fitxer es genera automàticament a l'arrel del projecte en cada execució. Estructura exacta:

```json
{
  "ruta": "DR0006",
  "data": "19/03/2026",
  "parades": [
    {
      "ordre": 0,
      "nom": "DDI Mollet (sortida)",
      "zona": "Magatzem",
      "lat": 41.5396,
      "lon": 2.21,
      "hora_s": 0,
      "hora": "06:00h",
      "temps_descarrega": 0,
      "parada_compartida": null,
      "clients_grup": []
    },
    {
      "ordre": 1,
      "nom": "CASA MAURA",
      "zona": "MOLLET CAN BORRELL",
      "lat": 41.5397151,
      "lon": 2.2137043,
      "hora_s": 1705,
      "hora": "06:28h",
      "temps_descarrega": 16,
      "parada_compartida": 1,
      "clients_grup": ["CASA MAURA", "PA I CAFETERIA DE L'AVIA", "CUENCA BAR"]
    },
    {
      "ordre": 15,
      "nom": "DDI Mollet (retorn)",
      "zona": "Magatzem",
      "lat": 41.5396,
      "lon": 2.21,
      "hora_s": 0,
      "hora": "06:00h",
      "temps_descarrega": 0,
      "parada_compartida": null,
      "clients_grup": []
    }
  ]
}
```

> **Nota:** `ruta_optima.json` **no inclou** el camp `geometria` (polilínies de carrers). La geometria només existeix en memòria durant l'execució i es fa servir per generar `ruta_damm.html`. Per consumir la geometria des d'un frontend propi, cal modificar `exportar_mapa_i_json` per incloure-la al JSON.

---

### Exemple mínim amb Leaflet.js

```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
  <style> #mapa { height: 100vh; } </style>
</head>
<body>
  <div id="mapa"></div>
  <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
  <script>
    const mapa = L.map('mapa').setView([41.5396, 2.2100], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(mapa);

    fetch('ruta_optima.json')
      .then(r => r.json())
      .then(data => {
        const parades = data.parades;

        // Dibuixar línia recta entre parades (sense geometria de carrers al JSON)
        const coords = parades.map(p => [p.lat, p.lon]);
        L.polyline(coords, { color: 'royalblue', weight: 3 }).addTo(mapa);

        // Marcadors per cada parada
        parades.forEach(p => {
          if (p.nom.startsWith('DDI Mollet')) return;

          const esCompartida = p.parada_compartida !== null;
          const color = esCompartida ? 'orange' : 'blue';

          const popup = `
            <b>${p.ordre}. ${p.nom}</b><br>
            Zona: ${p.zona}<br>
            Arriba: ${p.hora}<br>
            Descàrrega: ${p.temps_descarrega} min
            ${esCompartida ? `<br><i>Parada compartida #${p.parada_compartida}</i>` : ''}
          `;

          L.circleMarker([p.lat, p.lon], { color, radius: 8 })
            .bindPopup(popup)
            .bindTooltip(`${p.ordre}. ${p.nom}`)
            .addTo(mapa);
        });
      });
  </script>
</body>
</html>
```

### Exemple amb Mapbox GL JS

```javascript
// Carregar dades
const res = await fetch('ruta_optima.json');
const data = await res.json();

// Convertir a GeoJSON per Mapbox
const geojson = {
  type: 'FeatureCollection',
  features: data.parades
    .filter(p => !p.nom.startsWith('DDI Mollet'))
    .map(p => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: {
        ordre: p.ordre,
        nom: p.nom,
        hora: p.hora,
        temps_descarrega: p.temps_descarrega,
        parada_compartida: p.parada_compartida,
      }
    }))
};

map.addSource('parades', { type: 'geojson', data: geojson });
map.addLayer({
  id: 'parades-layer',
  type: 'circle',
  source: 'parades',
  paint: {
    'circle-radius': 8,
    'circle-color': [
      'case',
      ['!=', ['get', 'parada_compartida'], null], '#f59e0b',
      '#3b82f6'
    ]
  }
});
```

---

## 6. Variables configurables (BLOC 1)

Totes es troben al principi de `src/router.py`. Cap requereix reinici de servei — es llegeixen cada execució.

| Constant | Valor per defecte | Tipus | Quan la canviaries |
|---|---|---|---|
| `DEPOT_LAT` / `DEPOT_LON` | `41.5396` / `2.2100` | `float` | Si el magatzem canvia d'ubicació |
| `JORNADA_INICI_H` | `6` | `int` | Si el camió surt a una hora diferent (en hores, p.ex. `7` = 07:00) |
| `JORNADA_FI_H` | `18` | `int` | Si la jornada s'allarga; augmentar si OR-Tools no troba solució |
| `VELOCITAT_KMH` | `35` | `int` | Ajustar si l'àrea de repartiment és diferent (urbà dens → 25, extraurbà → 50) |
| `TEMPS_SERVEI_MIN` | `12` | `int` | Temps de descàrrega per defecte quan no hi ha dades de volum |
| `TEMPS_SERVEI_MINIM_MIN` | `5` | `int` | Mínim garantit de descàrrega (evita valors impossiblement baixos) |
| `TEMPS_SERVEI_MAXIM_MIN` | `30` | `int` | Màxim cap client pot bloquejar el camió |
| `MINUTS_PER_CAIXA` | `0.5` | `float` | Calibrar amb dades reals de cronometratge |
| `MINUTS_PER_BARRIL` | `2.0` | `float` | Els barrils tarden molt més (rodolament, connexions) |
| `MINUTS_PER_UNITAT` | `0.3` | `float` | Unitats soltes — temps mínim |
| `DISTANCIA_PARADA_COMPARTIDA_M` | `80` | `int` | Metres màxims per agrupar clients com a parada conjunta; reduir si hi ha massa agrupaments erronis |
| `PENALITZACIO_ALTA` | `99999` | `int` | Cost d'ometre un client prioritari (pràcticament obligatori visitar-lo) |
| `PENALITZACIO_NORMAL` | `3600` | `int` | Cost d'ometre un client estàndard (equiv. 1h de viatge extra) |
| `PENALITZACIO_OPCIONAL` | `500` | `int` | Cost d'ometre un client de poc volum |
| `PRIORITATS_CLIENT` | `{}` | `dict` | Assignar `PENALITZACIO_ALTA` a clients VIP, `PENALITZACIO_OPCIONAL` a clients flexibles |
| `ARCS_PROHIBITS` | `[]` | `list` | Afegir tuples `(node_orig, node_dest)` per prohibir transicions específiques |
| `ZONES_TRAFIC_MATINAL` | `{'MOLLET RAMBLA NOVA', ...}` | `set` | Zones on s'aplica el factor de tràfic en hora punta |
| `FACTOR_TRAFIC_MATINAL` | `1.4` | `float` | Multiplicador de temps en hora punta (1.4 = 40% més lent) |
| `RUSH_HOUR_INICI_S` | `7200` | `int` | Inici de l'hora punta en segons des de `JORNADA_INICI_H` (7200s = 08:00h) |
| `RUSH_HOUR_FI_S` | `10800` | `int` | Fi de l'hora punta (10800s = 09:00h) |

---

## 7. Errors coneguts i com gestionar-los

| Situació | On passa | Missatge / comportament | Com gestionar |
|---|---|---|---|
| OR-Tools no troba solució | `resoldre_ruta` | Retorna `[]`; `executar_ruta` retorna `{"error": "OR-Tools no ha trobat solució"}` | Augmentar `JORNADA_FI_H`; revisar si alguna time window és posterior a `JORNADA_FI_H` |
| OSRM Table API falla (sense connexió) | `construir_matriu_temps` | Advertència + càlcul Haversine com a fallback | L'execució continua amb distàncies menys precises; els temps poden estar subestimats en zona urbana |
| OSRM Route API falla (un tram) | `_osrm_geometria_tram` | `RuntimeError` — l'execució s'atura | Envolicar la crida en `try/except` per retornar geometria buida i continuar |
| Client sense coordenades (Nominatim no resol) | `geocodificar_parades` | Advertència; assigna `DEPOT_LAT, DEPOT_LON` com a fallback | El client apareix al dipòsit al mapa; la ruta pot ser subòptima; cal pre-geocodificar i cachear |
| Adreça geocodificada erròniament | `geocodificar_parades` | No hi ha avís; Nominatim pot retornar una ubicació incorrecta | En producció: validar les coordenades i mantenir una taula de geocodificació manual a la DB |
| Client sense horari a `Horarios_Entrega` | `carregar_horaris` + `preparar_context` | `tw_inici = 0, tw_fi = jornada_s` (finestra completa) — el client es visita en qualsevol moment | Comportament correcte per defecte |
| Client marcat com a tancat (`Cierre Si/No` informat) | `preparar_context` | S'elimina del problema; s'informa per consola | Si és un error de dades, corregir el camp a la DB |
| Ruta o data no existeix a la DB | `carregar_parades` | Retorna DataFrame buit; OR-Tools rep 0 nodes | Validar l'existència de dades abans de cridar `executar_ruta` |
| OSRM públic amb rate limiting (429) | `construir_matriu_temps` | `requests.raise_for_status()` llança `HTTPError` | Per a producció, desplegar una instància OSRM pròpia amb Docker |
