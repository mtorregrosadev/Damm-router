# Damm-router

Hackathon
Optimitzador de rutes i sistema de càrrega per a camions (prototip Hackathon).

Aquest repositori conté eines per calcular l'ordre òptim de visita d'un camió
de repartiment (VRPTW via OR-Tools), obtenir traçats reals (OSRM / OSM), i
generar el pla de càrrega dels camions (matrius 3D). També inclou una interfície
web (Next.js) per visualitzar i gestionar els resultats.

## Característiques principals

- Optimització de rutes amb OR-Tools (VRP amb time-windows).
- Geocodificació de clients amb Nominatim (geopy) i rutes/taules amb OSRM.
- Exportació de resultats a JSON i mapa Folium (`ruta_optima.json`, `ruta_damm.html`).
- Generació de matrius de càrrega per camions (algorisme de paletització).
- Backend + petits scripts Python per carregar dades i executar el flux complet.
- Frontend Next.js dins de la carpeta `web/` per visualització i dashboards.

# Damm-router

Optimizador de rutas y sistema de carga para camiones (prototipo Hackathon).

Este repositorio contiene herramientas para calcular el orden óptimo de visita
de un camión de reparto (VRPTW vía OR-Tools), obtener trazados reales (OSRM /
OSM) y generar el plan de carga de los camiones (matrices 3D). También incluye
una interfaz web (Next.js) para visualizar y gestionar los resultados.

## Características principales

- Optimización de rutas con OR-Tools (VRP con time-windows).
- Geocodificación de clientes con Nominatim (geopy) y tablas/rutas con OSRM.
- Exportación de resultados a JSON y mapa Folium (`ruta_optima.json`,
  `ruta_damm.html`).
- Generación de matrices de carga para camiones (algoritmo de paletización).
- Backend y pequeños scripts Python para cargar datos y ejecutar el flujo
  completo.
- Frontend Next.js en la carpeta `web/` para visualización y dashboards.

## Estructura del repositorio (resumen)

- `main.py`            — punto de entrada para orquestar el flujo completo.
- `ARQUITECTURA.md`   — documento técnico con el diseño del módulo
  `src/alghoritms/router.py`.
- `src/`              — código Python principal:
  - `alghoritms/router.py`      — optimizador de ruta (API pública:
    `executar_ruta`)
  - `alghoritms/truck_loader.py`— generador de palets y ensamblaje del camión
  - `utils/carga_async.py`      — API async para generar la carga y guardar en MongoDB
  - `db/`                       — conectores y scripts de carga (excel_to_sql, mongo)
  - `test_carga.py`, `test_truck_loader.py` — ejemplos / tests de uso
- `BD/`               — ficheros de entrada (Excel) usados durante el hackathon
- `web/`              — frontend Next.js (React + Leaflet / dashboards)

## Requisitos

- Sistema: macOS / Linux / Windows
- Python 3.10+
- MongoDB (para datos de entrada y resultados). Algunas partes del código
  también pueden usar SQLite para prototipado (ver `src/db/excel_to_sql.py`).
- Recomendado para ejecutar rutas completas: conexión a OSRM y uso responsable
  de Nominatim (rate limits).

Dependencias Python principales:

- ortools
- pandas, numpy
- geopy
- folium
- certifi, requests, pymongo

Frontend:

- Node.js (compatible con la versión indicada en `web/package.json`) y pnpm/npm.

Nota: no hay `requirements.txt` en la rama; puede instalar las dependencias de
prueba con el pip line que se muestra más abajo.

## Instalación rápida (Python)

Recomendado: crear un entorno virtual e instalar paquetes.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install ortools pandas numpy geopy folium certifi requests pymongo
```

Para el frontend, desde la carpeta `web/`:

```bash
# dentro de /web
npm install
# o si usas pnpm: pnpm install
npm run dev
```

## Cómo ejecutar las partes principales

- Ejecutar el flujo completo (cargar datos + optimizar + generar carga):

  ```bash
  python main.py
  ```

  Esta rutina invocará la carga del Excel a la base de datos y procesará todas
  las rutas encontradas. Requiere la configuración de acceso a MongoDB (ver
  `src/db/mongo.py`).
- Ejecutar el optimizador para una sola ruta (modo script):

  ```bash
  python src/alghoritms/router.py --ruta DR0006 --data 19/03/2026 --dia 4 --html
  ```

  O importar la función desde Python:

  ```python
  from src.alghoritms.router import executar_ruta
  executar_ruta('DR0006', '19/03/2026', 4, exportar_html=True)
  ```
- Generar la carga del camión (ejemplo):

  ```bash
  python src/test_carga.py
  ```

  O llamar `await generar_carga(id_ruta, ids_parada)` desde un programa async
  (ver `src/utils/carga_async.py`).

## Entradas y resultados

- Datos de entrada principales: colecciones MongoDB `detalle_entrega` y
  `horarios_entrega`. Hay scripts para convertir Excel a BD en `src/db/`.
- Resultados generados:
  - `ruta_optima.json` — JSON con los datos de la ruta calculada
  - `ruta_damm.html`  — mapa interactivo (Folium)
  - MongoDB: colecciones `ruta_punts`, `ruta_resum`, `resultado_carga_camion`

## Notas operativas y limitaciones

- La API pública de OSRM (router.project-osrm.org) puede tener límites. Si
  se trabaja con volúmenes altos, considerar desplegar un OSRM propio o usar
  otros servicios de routing.
- OR-Tools: se recomienda instalar una versión 9.x o superior (pip: ortools).
- El código contiene constantes y heurísticas (distancias, factor de
  tráfico, duración de jornada) dentro de `src/alghoritms/router.py` que se
  pueden ajustar según necesidad.

## Contribuir

- Issues y PRs son bienvenidos. Si quieres reproducir datos del hackathon,
  empieza cargando los Excel a la BD con los scripts en `src/db/`.

## Licencia

Ver `LICENSE`.

---
Pequeño resumen: el repositorio ofrece un prototipo completo para optimizar
rutas y preparar la carga del camión, con salida en JSON y mapa. Revisa
`ARQUITECTURA.md` para detalles técnicos y ajusta las conexiones a MongoDB /
OSRM según tu entorno.
