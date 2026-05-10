"""
Generación de estados por parada a partir de matrices de carga del camión.

Interfaz principal:
    estados = generar_estados_por_parada(camion_tipo, camion_ids, paradas_globales)

Cada elemento de la lista representa el estado completo en una parada:
  estado_antes         — qué hay físicamente en el camión al llegar
  descarga             — qué se descarga (cajas y barriles)
  estado_post_descarga — estado tras descargar, antes de cargar CJ13
  carga_cj13           — CJ13 cargadas en esta parada (None si no aplica)
  estado_final         — estado tras todas las operaciones de la parada

Tipos de material:
  0 = vacío
  1 = caja
  2 = barril
  3 = CJ13 (caja vacía recogida durante la ruta)

Reglas de simulación:
  tipo {1,2} con ids < k  → ya descargados en paradas anteriores
  tipo {1,2} con ids == k → siendo descargados en esta parada
  tipo {1,2} con ids > k  → aún en el camión, entregas futuras
  tipo 3    con ids < k  → CJ13 cargados en paradas anteriores
  tipo 3    con ids == k → siendo cargados en esta parada
  tipo 3    con ids > k  → aún no cargados (se cargarán más adelante)
"""

import numpy as np
from typing import Any, Dict, List

TIPO_VACIO  = 0
TIPO_CAJA   = 1
TIPO_BARRIL = 2
TIPO_CJ13   = 3


# ─── Utilidades ───────────────────────────────────────────────────────────────

def resumen_tipo(tipo: np.ndarray) -> Dict[str, int]:
    """Cuenta posiciones por tipo de material en la matriz del camión."""
    return {
        "cajas":          int(np.sum(tipo == TIPO_CAJA)),
        "barriles":       int(np.sum(tipo == TIPO_BARRIL)),
        "cj13":           int(np.sum(tipo == TIPO_CJ13)),
        "vacias":         int(np.sum(tipo == TIPO_VACIO)),
        "total_unidades": int(np.sum(tipo > 0)),
    }


def _snapshot(tipo: np.ndarray, ids: np.ndarray) -> Dict[str, Any]:
    """Serializa un par (tipo, ids) con su resumen."""
    return {
        "camion_tipo": tipo.tolist(),
        "camion_ids":  ids.tolist(),
        "resumen":     resumen_tipo(tipo),
    }


# ─── API pública ──────────────────────────────────────────────────────────────

def generar_estados_por_parada(
    camion_tipo: np.ndarray,
    camion_ids:  np.ndarray,
    paradas_globales: List[int],
) -> List[Dict[str, Any]]:
    """
    Genera los estados del camión para cada parada a partir de las matrices iniciales.

    Las matrices representan el estado del camión AL SALIR DEL ALMACÉN.
    La función simula qué hay físicamente en el camión en cada momento
    de la ruta, aplicando las reglas de descarga/carga en orden.

    Args:
        camion_tipo:      array numpy [8][9][5] — tipos iniciales (0-3)
        camion_ids:       array numpy [8][9][5] — órdenes globales de parada
        paradas_globales: lista de órdenes globales de parada de este camión

    Returns:
        Lista de dicts, uno por parada, con todos los estados y operaciones.
    """
    estados: List[Dict[str, Any]] = []

    # Máscaras de tipo calculadas una sola vez (sobre la matriz inicial)
    es_entrega = (camion_tipo > 0) & (camion_tipo < 3)  # cajas y barriles
    es_cj13    = (camion_tipo == TIPO_CJ13)

    for k in paradas_globales:

        # ── Estado ANTES de operar en la parada k ────────────────────────────
        # Físicamente en el camión al llegar:
        #   - entregas para parada k y futuras (incluyendo las que se van a bajar)
        #   - CJ13 cargados en paradas anteriores
        mask_antes = (es_entrega & (camion_ids >= k)) | (es_cj13 & (camion_ids < k))
        t_antes    = np.where(mask_antes, camion_tipo, 0)
        i_antes    = np.where(mask_antes, camion_ids, 0)

        # ── Descarga ──────────────────────────────────────────────────────────
        mask_desc    = es_entrega & (camion_ids == k)
        pos_desc     = np.argwhere(mask_desc).tolist()   # [[x,y,z], ...]
        n_cajas_d    = int(np.sum(mask_desc & (camion_tipo == TIPO_CAJA)))
        n_barriles_d = int(np.sum(mask_desc & (camion_tipo == TIPO_BARRIL)))

        # ── Estado POST-DESCARGA ──────────────────────────────────────────────
        # Se han bajado las entregas de parada k. CJ13 anteriores siguen.
        mask_post = (es_entrega & (camion_ids > k)) | (es_cj13 & (camion_ids < k))
        t_post    = np.where(mask_post, camion_tipo, 0)
        i_post    = np.where(mask_post, camion_ids, 0)

        # ── Carga CJ13 ────────────────────────────────────────────────────────
        # Siempre después de descargar (orden: descarga → carga CJ13)
        mask_cj13 = es_cj13 & (camion_ids == k)
        n_cj13    = int(np.sum(mask_cj13))
        pos_cj13  = np.argwhere(mask_cj13).tolist()

        if n_cj13 > 0:
            mask_con_cj13 = mask_post | mask_cj13
            t_cj13 = np.where(mask_con_cj13, camion_tipo, 0)
            i_cj13 = np.where(mask_con_cj13, camion_ids, 0)
            bloque_cj13: Dict[str, Any] = {
                "tiene_cj13":  True,
                "cantidad":    n_cj13,
                "posiciones":  pos_cj13,
                "camion_tipo": t_cj13.tolist(),
                "camion_ids":  i_cj13.tolist(),
                "resumen":     resumen_tipo(t_cj13),
            }
        else:
            bloque_cj13 = {"tiene_cj13": False}

        # ── Estado FINAL después de la parada k ──────────────────────────────
        # Entregas futuras + CJ13 cargados (incluido parada k)
        mask_final = (es_entrega & (camion_ids > k)) | (es_cj13 & (camion_ids <= k))
        t_final    = np.where(mask_final, camion_tipo, 0)
        i_final    = np.where(mask_final, camion_ids, 0)

        entrega_final = (t_final > 0) & (t_final < 3)
        ordenes_pendientes = sorted(set(int(v) for v in i_final[entrega_final]))

        estado: Dict[str, Any] = {
            "orden": k,
            "estado_antes":        _snapshot(t_antes, i_antes),
            "descarga": {
                "tiene_descarga":       len(pos_desc) > 0,
                "posiciones":           pos_desc,
                "cajas_descargadas":    n_cajas_d,
                "barriles_descargados": n_barriles_d,
                "resumen":              {"cajas": n_cajas_d, "barriles": n_barriles_d},
            },
            "estado_post_descarga":  _snapshot(t_post, i_post),
            "carga_cj13":            bloque_cj13,
            "estado_final": {
                **_snapshot(t_final, i_final),
                "unidades_restantes": int(np.sum(entrega_final)),
                "huecos_libres":      int(np.sum(t_final == TIPO_VACIO)),
                "cj13_acumulados":    int(np.sum(t_final == TIPO_CJ13)),
                "ordenes_pendientes": ordenes_pendientes,
            },
        }
        estados.append(estado)

    return estados
