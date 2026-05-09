import argparse
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "hackaton.db"


def conectar_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def comprobar_sql_preparado(conn: sqlite3.Connection) -> None:
    """Comprueba que existe la vista creada en script.sql."""
    existe = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'view'
          AND name = 'vw_ortools_paradas'
        """
    ).fetchone()

    if not existe:
        raise RuntimeError(
            "No existe vw_ortools_paradas. Ejecuta primero: "
            "sqlite3 hackaton.db < script.sql"
        )


def obtener_ruta_por_defecto(conn: sqlite3.Connection) -> str:
    """Elige una ruta con muchas paradas para simular el algoritmo."""
    row = conn.execute(
        """
        SELECT id_ruta_algoritmo
        FROM vw_ortools_paradas
        GROUP BY id_ruta_algoritmo
        ORDER BY COUNT(*) DESC
        LIMIT 1
        """
    ).fetchone()

    if row is None:
        raise RuntimeError("No hay rutas disponibles en vw_ortools_paradas.")

    return row["id_ruta_algoritmo"]


def cargar_variables_algoritmo(
    conn: sqlite3.Connection,
    id_ruta_algoritmo: str,
) -> dict:
    """
    Carga el input de una ruta y lo separa en variables que luego usaria:
      - Google Maps: direcciones -> latitud/longitud
      - OR-Tools: puntos, prioridades, cantidades, retornables, ventanas
    """
    paradas = pd.read_sql_query(
        """
        SELECT *
        FROM vw_ortools_paradas
        WHERE id_ruta_algoritmo = ?
        ORDER BY id_parada_inicial
        """,
        conn,
        params=(id_ruta_algoritmo,),
    )

    if paradas.empty:
        raise RuntimeError(f"No hay paradas para la ruta: {id_ruta_algoritmo}")

    # IDs generales de la ruta.
    id_transporte = paradas["id_transporte"].iloc[0]
    id_ruta = paradas["id_ruta"].iloc[0]
    id_repartidor = paradas["id_repartidor"].iloc[0]
    fecha = paradas["fecha"].iloc[0]

    # Variables por parada.
    ids_parada = paradas["id_parada_inicial"].astype(int).tolist()
    ids_destinatario = paradas["id_destinatario_mercancia"].astype(str).tolist()
    nombres_destinatario = paradas["nombre_destinatario"].fillna("").tolist()
    direcciones = paradas["direccion_completa"].fillna("").tolist()
    ids_entrega = paradas["ids_entrega"].fillna("").tolist()
    ids_zona_transporte = paradas["id_zona_transporte"].fillna("").tolist()
    nombres_zona_transporte = paradas["nombre_zona_transporte"].fillna("").tolist()
    ventanas_horarias = paradas["ventanas_horarias"].fillna("").tolist()

    # Variables numericas para restricciones/costes.
    cantidades = paradas["cantidad_total"].fillna(0).astype(float).tolist()
    cantidades_retornables = (
        paradas["cantidad_retornable"].fillna(0).astype(float).tolist()
    )
    tiene_material_retornable = (
        paradas["tiene_material_retornable"].fillna(0).astype(int).tolist()
    )
    tiene_prioridad_horaria = (
        paradas["tiene_prioridad_horaria"].fillna(0).astype(int).tolist()
    )

    # Estas variables las rellenaria Google Maps Geocoding API.
    latitudes = [None] * len(direcciones)
    longitudes = [None] * len(direcciones)

    # Esta matriz la rellenaria Google Distance Matrix API / Routes API.
    matriz_distancias = None
    matriz_duraciones = None

    return {
        "paradas_df": paradas,
        "id_ruta_algoritmo": id_ruta_algoritmo,
        "fecha": fecha,
        "id_transporte": id_transporte,
        "id_ruta": id_ruta,
        "id_repartidor": id_repartidor,
        "ids_parada": ids_parada,
        "ids_destinatario": ids_destinatario,
        "nombres_destinatario": nombres_destinatario,
        "direcciones": direcciones,
        "ids_entrega": ids_entrega,
        "ids_zona_transporte": ids_zona_transporte,
        "nombres_zona_transporte": nombres_zona_transporte,
        "ventanas_horarias": ventanas_horarias,
        "cantidades": cantidades,
        "cantidades_retornables": cantidades_retornables,
        "tiene_material_retornable": tiene_material_retornable,
        "tiene_prioridad_horaria": tiene_prioridad_horaria,
        "latitudes": latitudes,
        "longitudes": longitudes,
        "matriz_distancias": matriz_distancias,
        "matriz_duraciones": matriz_duraciones,
    }


def simular_ortools(variables: dict) -> list[int]:
    """
    Simula el output de OR-Tools.

    De momento no calcula distancias reales porque faltan coordenadas/matriz.
    Ordena poniendo primero paradas con prioridad horaria y despues mantiene
    el orden inicial de la vista.
    """
    indices = list(range(len(variables["direcciones"])))
    return sorted(
        indices,
        key=lambda i: (
            -variables["tiene_prioridad_horaria"][i],
            variables["ids_zona_transporte"][i],
            variables["direcciones"][i],
        ),
    )


def guardar_resultado_simulado(conn: sqlite3.Connection, variables: dict, orden: list[int]) -> None:
    conn.execute(
        "DELETE FROM resultado_rutas_ortools WHERE id_ruta_algoritmo = ?",
        (variables["id_ruta_algoritmo"],),
    )

    filas = []
    for orden_parada, idx in enumerate(orden, start=1):
        filas.append(
            (
                variables["id_ruta_algoritmo"],
                variables["fecha"],
                variables["id_transporte"],
                variables["id_ruta"],
                variables["id_repartidor"],
                orden_parada,
                variables["ids_destinatario"][idx],
                variables["ids_entrega"][idx],
                variables["direcciones"][idx],
                variables["latitudes"][idx],
                variables["longitudes"][idx],
                None,
                None,
                None,
                None,
            )
        )

    conn.executemany(
        """
        INSERT INTO resultado_rutas_ortools (
            id_ruta_algoritmo,
            fecha,
            id_transporte,
            id_ruta,
            id_repartidor,
            orden_parada,
            id_destinatario_mercancia,
            ids_entrega,
            direccion_completa,
            latitud,
            longitud,
            distancia_desde_anterior_m,
            duracion_desde_anterior_s,
            distancia_acumulada_m,
            duracion_acumulada_s
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        filas,
    )
    conn.commit()


def imprimir_resumen(variables: dict, orden: list[int]) -> None:
    print("INPUT separado para el algoritmo")
    print(f"  id_ruta_algoritmo: {variables['id_ruta_algoritmo']}")
    print(f"  fecha: {variables['fecha']}")
    print(f"  id_transporte: {variables['id_transporte']}")
    print(f"  id_ruta: {variables['id_ruta']}")
    print(f"  id_repartidor: {variables['id_repartidor']}")
    print(f"  num_paradas: {len(variables['direcciones'])}")
    print()

    print("Variables principales:")
    print(f"  ids_destinatario = {variables['ids_destinatario'][:5]}")
    print(f"  ids_entrega = {variables['ids_entrega'][:5]}")
    print(f"  direcciones = {variables['direcciones'][:3]}")
    print(f"  ids_zona_transporte = {variables['ids_zona_transporte'][:5]}")
    print(f"  cantidades = {variables['cantidades'][:5]}")
    print(f"  tiene_material_retornable = {variables['tiene_material_retornable'][:5]}")
    print(f"  tiene_prioridad_horaria = {variables['tiene_prioridad_horaria'][:5]}")
    print(f"  latitudes = {variables['latitudes'][:5]}")
    print(f"  longitudes = {variables['longitudes'][:5]}")
    print()

    print("OUTPUT simulado:")
    for orden_parada, idx in enumerate(orden[:10], start=1):
        print(
            f"  parada {orden_parada}: "
            f"{variables['ids_destinatario'][idx]} -> "
            f"{variables['direcciones'][idx]}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ruta",
        dest="id_ruta_algoritmo",
        help="Ejemplo: '19/03/2026|11588007|DR0016'",
    )
    args = parser.parse_args()

    with conectar_db() as conn:
        comprobar_sql_preparado(conn)
        id_ruta_algoritmo = args.id_ruta_algoritmo or obtener_ruta_por_defecto(conn)
        variables = cargar_variables_algoritmo(conn, id_ruta_algoritmo)
        orden = simular_ortools(variables)
        guardar_resultado_simulado(conn, variables, orden)
        imprimir_resumen(variables, orden)


if __name__ == "__main__":
    main()
