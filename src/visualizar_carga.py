"""
Genera carga_visual.html — visualización del plan de carga del camión
parada por parada: cómo llega el camión, qué descarga y qué recoge en cada parada.

Uso:
    python visualizar_carga.py                  # datos reales (ruta DR0016)
    python visualizar_carga.py --hardcoded      # datos de ejemplo con CJ13
"""

import sys
import asyncio
import argparse
import numpy as np
from pathlib import Path

BASE = Path(__file__).parent
for sub in ("db", "alghoritms", "utils"):
    sys.path.insert(0, str(BASE / sub))

from truck_loader import (
    cargar_camion,
    PALET_X, PALET_Y, PALET_Z, CAMION_COLS, CAMION_FILAS, PALET_CAP,
    TIPO_VACIO, TIPO_CAJA, TIPO_BARRIL, TIPO_CJ13,
)

SALIDA = BASE.parent / "carga_visual.html"

# ─── Colores ──────────────────────────────────────────────────────────────────

# Estado normal en camión
COLOR = {
    TIPO_VACIO:  ("#e8e8e8", "#aaa", ""),
    TIPO_CAJA:   ("#4a90d9", "#fff", "C"),
    TIPO_BARRIL: ("#e07b3a", "#fff", "B"),
    TIPO_CJ13:   ("#5cb85c", "#fff", "V"),
}
# Items que se descargan ahora (destacados)
COLOR_DESCARGA = ("#f5c518", "#333", "↓")
# CJ13 que se carga ahora (destacado)
COLOR_CARGA    = ("#1eaa4f", "#fff", "↑")


def _color_celda(tipo: int, stop: int, stop_actual: int):
    """Devuelve (bg, fg, letra) según el estado en esta parada."""
    if tipo == TIPO_VACIO:
        return COLOR[TIPO_VACIO]
    if tipo in (TIPO_CAJA, TIPO_BARRIL) and stop == stop_actual:
        return COLOR_DESCARGA                      # se descarga AHORA
    if tipo == TIPO_CJ13 and stop == stop_actual:
        return COLOR_CARGA                         # se carga AHORA
    return COLOR[tipo]


# ─── Estado simulado del camión en cada parada ───────────────────────────────

def estado_en_parada(t_tipo, t_ids, stop_k: int):
    """
    Estado físico del camión AL LLEGAR a la parada stop_k.

    - Delivery items de paradas anteriores (ids < stop_k): ya descargados → vacío
    - Delivery items de esta parada (ids == stop_k): se descargan ahora → destacado
    - Delivery items de paradas futuras (ids > stop_k): en camión
    - CJ13 de paradas anteriores (ids < stop_k): ya cargados → verde normal
    - CJ13 de esta parada (ids == stop_k): se carga ahora → verde destacado
    - CJ13 de paradas futuras (ids > stop_k): aún no cargado → vacío
    """
    TX, TY, TZ = t_tipo.shape
    estado_tipo = np.zeros_like(t_tipo)
    estado_ids  = np.zeros_like(t_ids)

    for x in range(TX):
        for y in range(TY):
            for z in range(TZ):
                tp = t_tipo[x, y, z]
                sp = t_ids[x, y, z]

                if tp == TIPO_VACIO:
                    pass  # vacío
                elif tp in (TIPO_CAJA, TIPO_BARRIL):
                    if sp >= stop_k:          # aún en camión (incluye "se descarga ahora")
                        estado_tipo[x, y, z] = tp
                        estado_ids[x, y, z]  = sp
                elif tp == TIPO_CJ13:
                    if sp <= stop_k:          # ya cargado (incluye "se carga ahora")
                        estado_tipo[x, y, z] = tp
                        estado_ids[x, y, z]  = sp

    return estado_tipo, estado_ids


# ─── Renderizado de una capa Z ────────────────────────────────────────────────

def _celda_html(tipo: int, stop: int, stop_actual: int) -> str:
    bg, fg, letra = _color_celda(tipo, stop, stop_actual)
    txt   = f"{letra}{stop}" if stop and tipo != TIPO_VACIO else (letra if letra else "")
    title = {
        TIPO_VACIO:  "Vacío",
        TIPO_CAJA:   f"Caja — parada {stop}",
        TIPO_BARRIL: f"Barril — parada {stop}",
        TIPO_CJ13:   f"CJ13 — parada {stop}",
    }.get(tipo, "")
    if tipo in (TIPO_CAJA, TIPO_BARRIL) and stop == stop_actual:
        title = f"⬇ Descarga en parada {stop}"
    if tipo == TIPO_CJ13 and stop == stop_actual:
        title = f"⬆ Recoge en parada {stop}"
    return (
        f'<td title="{title}" style="background:{bg};color:{fg};'
        f'width:36px;height:32px;text-align:center;font-size:10px;'
        f'font-weight:bold;border:1px solid #ccc;border-radius:3px;'
        f'padding:0;cursor:default">{txt}</td>'
    )


def _tabla_capa(t_tipo, t_ids, z: int, stop_actual: int) -> str:
    TX = t_tipo.shape[0]
    filas = []
    for fila in range(CAMION_FILAS):
        y0 = fila * PALET_Y
        filas.append(
            f'<tr><td colspan="{TX+1}" style="font-size:10px;color:#888;'
            f'padding:3px 0 1px 0"><b>Fila {fila}</b></td></tr>'
        )
        for y in range(PALET_Y):
            iy = y0 + y
            izq = "".join(
                _celda_html(t_tipo[x, iy, z], t_ids[x, iy, z], stop_actual)
                for x in range(PALET_X)
            )
            sep = '<td style="width:10px"></td>'
            der = "".join(
                _celda_html(t_tipo[x, iy, z], t_ids[x, iy, z], stop_actual)
                for x in range(PALET_X, TX)
            )
            filas.append(f"<tr>{izq}{sep}{der}</tr>")
    return "\n".join(filas)


def _html_camion_en_parada(t_tipo, t_ids, stop_actual: int, id_parada_info: dict) -> str:
    """HTML de las matrices del camión en el momento de una parada."""
    capas = []
    for z in range(PALET_Z - 1, -1, -1):
        etq = (
            f"TECHO Z={PALET_Z-1}" if z == PALET_Z-1
            else f"SUELO Z=0" if z == 0
            else f"Z={z}"
        )
        tabla = _tabla_capa(t_tipo, t_ids, z, stop_actual)
        capas.append(
            f'<div style="margin-right:14px">'
            f'<div style="font-size:10px;font-weight:bold;color:#555;'
            f'margin-bottom:4px;text-align:center">{etq}</div>'
            f'<table style="border-collapse:separate;border-spacing:2px">'
            f'{tabla}</table></div>'
        )

    n_descarga = int(np.sum(
        (t_tipo == TIPO_CAJA) & (t_ids == stop_actual)
    ) + np.sum(
        (t_tipo == TIPO_BARRIL) & (t_ids == stop_actual)
    ))
    n_cj13 = int(np.sum(
        (t_tipo == TIPO_CJ13) & (t_ids == stop_actual)
    ))
    n_en_camion = int(np.sum(t_tipo != TIPO_VACIO))

    ocupacion = round(100 * n_en_camion / (CAMION_COLS * CAMION_FILAS * PALET_CAP), 1)

    badges = []
    if n_descarga:
        badges.append(
            f'<span style="background:#f5c518;color:#333;padding:3px 8px;'
            f'border-radius:4px;font-size:12px;margin-right:6px">'
            f'⬇ Descarga: {n_descarga} uds</span>'
        )
    if n_cj13:
        badges.append(
            f'<span style="background:#1eaa4f;color:#fff;padding:3px 8px;'
            f'border-radius:4px;font-size:12px;margin-right:6px">'
            f'⬆ Recoge CJ13: {n_cj13} uds</span>'
        )
    badges.append(
        f'<span style="background:#e0e0e0;color:#444;padding:3px 8px;'
        f'border-radius:4px;font-size:12px">'
        f'En camión: {n_en_camion} uds ({ocupacion}%)</span>'
    )

    return f"""
    <div style="margin-bottom:6px">
      <div style="margin-bottom:8px">{"".join(badges)}</div>
      <div style="display:flex;flex-wrap:nowrap;overflow-x:auto;gap:0">
        {"".join(capas)}
      </div>
    </div>"""


# ─── Bloque completo de un camión ────────────────────────────────────────────

def html_camion(n_camion: int, cam: dict, paradas_info: list) -> str:
    t_tipo_list = cam["camion_tipo"]
    t_ids_list  = cam["camion_ids"]

    t_tipo = np.array(t_tipo_list, dtype=np.int32)
    t_ids  = np.array(t_ids_list,  dtype=np.int32)

    # IDs locales de parada en este camión (1..N)
    stops_locales = sorted(
        int(v) for v in np.unique(t_ids[t_ids > 0])
    )

    secciones = []
    for stop_k in stops_locales:
        et_tipo, et_ids = estado_en_parada(t_tipo, t_ids, stop_k)

        # Info de la parada
        info = next((p for p in paradas_info if p["orden_local"] == stop_k), {})
        orden_global = info.get("orden", stop_k)
        id_dest      = info.get("id_destinatario", "—")
        cajas_p      = info.get("cajas", 0)
        barriles_p   = info.get("barriles", 0)
        cj13_p       = info.get("cj13", 0)

        titulo = (
            f"Parada {orden_global}"
            f'<span style="font-size:12px;font-weight:normal;color:#888;'
            f'margin-left:10px">{id_dest}</span>'
            f'<span style="font-size:12px;font-weight:normal;color:#4a90d9;'
            f'margin-left:10px">CAJ={cajas_p}</span>'
            f'<span style="font-size:12px;font-weight:normal;color:#e07b3a;'
            f'margin-left:6px">BRL={barriles_p}</span>'
        )
        if cj13_p:
            titulo += (
                f'<span style="font-size:12px;font-weight:normal;color:#1eaa4f;'
                f'margin-left:6px">CJ13={cj13_p}</span>'
            )

        contenido = _html_camion_en_parada(et_tipo, et_ids, stop_k, info)

        uid = f"cam{n_camion}_stop{stop_k}"
        secciones.append(f"""
        <div style="border:1px solid #ddd;border-radius:8px;
                    margin-bottom:10px;overflow:hidden">
          <div onclick="toggle('{uid}')"
               style="background:#f0f4f8;padding:12px 16px;cursor:pointer;
                      display:flex;align-items:center;justify-content:space-between">
            <span style="font-size:14px;font-weight:bold;color:#333">{titulo}</span>
            <span id="{uid}_ico" style="color:#888;font-size:16px">▶</span>
          </div>
          <div id="{uid}" style="display:none;padding:16px;overflow-x:auto">
            {contenido}
          </div>
        </div>""")

    total_uds = int(np.sum(t_tipo != TIPO_VACIO))
    return f"""
    <div style="border:2px solid #aaa;border-radius:12px;padding:20px;
                margin-bottom:32px;background:#fafafa">
      <h2 style="margin:0 0 6px 0;color:#222">
        Camión {n_camion}
        <span style="font-size:14px;font-weight:normal;color:#666;margin-left:12px">
          {cam['n_cajas']} uds entrega · {cam['n_palets_usados']}/6 palets ·
          {cam['ocupacion_pct']}% ocupación inicial
        </span>
      </h2>
      <div style="margin-bottom:16px;font-size:12px;display:flex;gap:10px;
                  flex-wrap:wrap">
        <span style="background:#4a90d9;color:#fff;padding:3px 8px;border-radius:4px">C Caja</span>
        <span style="background:#e07b3a;color:#fff;padding:3px 8px;border-radius:4px">B Barril</span>
        <span style="background:#5cb85c;color:#fff;padding:3px 8px;border-radius:4px">V CJ13</span>
        <span style="background:#f5c518;color:#333;padding:3px 8px;border-radius:4px">⬇ Se descarga</span>
        <span style="background:#1eaa4f;color:#fff;padding:3px 8px;border-radius:4px">⬆ Se recoge</span>
        <span style="background:#e8e8e8;color:#888;padding:3px 8px;border-radius:4px">· Vacío</span>
      </div>
      <div style="font-size:12px;color:#888;margin-bottom:12px">
        Haz clic en cada parada para ver el estado del camión al llegar.
        Los <b style="color:#f5c518">amarillos</b> se descargan ahora.
        Los <b style="color:#1eaa4f">verdes oscuros</b> son CJ13 que se recogen ahora.
      </div>
      {"".join(secciones)}
    </div>"""


# ─── HTML completo ────────────────────────────────────────────────────────────

def construir_html(resultado: dict) -> str:
    paradas  = resultado["paradas"]
    camiones = resultado["camiones"]
    ruta     = resultado.get("id_ruta_algoritmo", "")

    bloques = []
    idx = 0
    for cam in camiones:
        tope = cam["n_cajas"]
        acum = 0
        paradas_cam = []
        orden_local = 1
        while idx < len(paradas):
            p = paradas[idx]
            uds = p["cajas"] + p["barriles"]
            if acum + uds > tope and paradas_cam:
                break
            paradas_cam.append({**p, "orden_local": orden_local})
            acum += uds
            orden_local += 1
            idx += 1
        bloques.append(html_camion(cam["n_camion"], cam, paradas_cam))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Plan de Carga por Parada — {ruta}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px;
            background: #f5f7fa; color: #222; }}
    h1   {{ margin: 0 0 4px 0; font-size: 22px; }}
    .sub {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
  </style>
  <script>
    function toggle(id) {{
      var el  = document.getElementById(id);
      var ico = document.getElementById(id + '_ico');
      if (el.style.display === 'none') {{
        el.style.display  = 'block';
        ico.textContent   = '▼';
      }} else {{
        el.style.display  = 'none';
        ico.textContent   = '▶';
      }}
    }}
    function expandAll()  {{ document.querySelectorAll('[id^="cam"]').forEach(function(e){{ if(!e.id.endsWith('_ico')){{ e.style.display='block'; }} }});  document.querySelectorAll('[id$="_ico"]').forEach(function(e){{ e.textContent='▼'; }}); }}
    function collapseAll(){{ document.querySelectorAll('[id^="cam"]').forEach(function(e){{ if(!e.id.endsWith('_ico')){{ e.style.display='none';  }} }});  document.querySelectorAll('[id$="_ico"]').forEach(function(e){{ e.textContent='▶'; }}); }}
  </script>
</head>
<body>
  <h1>Plan de Carga — parada por parada</h1>
  <div class="sub">
    Ruta: <b>{ruta}</b> &nbsp;·&nbsp;
    {resultado['n_paradas']} paradas &nbsp;·&nbsp;
    {resultado['total_cajas']} uds entrega &nbsp;·&nbsp;
    {resultado['n_camiones']} camión{'es' if resultado['n_camiones'] > 1 else ''}
  </div>
  <div style="margin-bottom:20px">
    <button onclick="expandAll()"
      style="padding:6px 14px;margin-right:8px;cursor:pointer;
             border:1px solid #aaa;border-radius:6px;background:#fff">
      Expandir todo</button>
    <button onclick="collapseAll()"
      style="padding:6px 14px;cursor:pointer;
             border:1px solid #aaa;border-radius:6px;background:#fff">
      Colapsar todo</button>
  </div>
  {"".join(bloques)}
</body>
</html>"""


# ─── Fuentes de datos ─────────────────────────────────────────────────────────

async def datos_reales() -> dict:
    from carga_async import generar_carga
    ID_RUTA = "19/03/2026|11588007|DR0016"
    IDS_PARADA = [
        "9100087801","9100559291","9100480482","9100698912","9100521678",
        "9100043893","9100340260","9100043381","9100507921","9100310143",
        "9100044469","9100681218","9100682473","9100550379","9100227012",
        "9100420786","9100253786","9100525754","9100121164","9100743172",
        "9100743868","9100653355","9100752730","9100658144","9100250393",
        "9100626587","9100747591","118135","9100652617",
    ]
    print(f"Consultando MongoDB ({len(IDS_PARADA)} paradas)...")
    resultado = await generar_carga(ID_RUTA, IDS_PARADA)
    resultado["id_ruta_algoritmo"] = ID_RUTA
    return resultado


def datos_hardcodeados() -> dict:
    paradas  = [1, 2, 3, 4, 5]
    cajas    = {1: 20, 2: 40, 3: 40, 4: 30, 5: 20}
    barriles = {1: 20, 2:  5, 3:  5, 4:  5, 5:  5}
    cj13     = {2:  6, 4:  4}

    _, _, t_tipo, t_ids = cargar_camion(paradas, cajas, barriles, cj13)

    n_en = int(np.sum(t_tipo != TIPO_VACIO))
    return {
        "id_ruta_algoritmo": "Ejemplo hardcodeado (con CJ13)",
        "n_paradas": len(paradas),
        "total_cajas": sum(cajas.values()) + sum(barriles.values()),
        "n_camiones": 1,
        "paradas": [
            {
                "orden": i,
                "id_destinatario": f"CLIENTE_{i}",
                "cajas":    cajas.get(i, 0),
                "barriles": barriles.get(i, 0),
                "cj13":     cj13.get(i, 0),
            }
            for i in paradas
        ],
        "camiones": [{
            "n_camion": 1,
            "camion_tipo": t_tipo.tolist(),
            "camion_ids":  t_ids.tolist(),
            "n_cajas":     sum(cajas.values()) + sum(barriles.values()),
            "n_palets_usados": int(
                np.any(
                    t_tipo.reshape(CAMION_COLS * CAMION_FILAS, -1) != 0,
                    axis=1
                ).sum()
            ),
            "ocupacion_pct": round(100 * n_en / (360), 1),
        }],
    }


async def main(hardcoded: bool):
    if hardcoded:
        resultado = datos_hardcodeados()
    else:
        try:
            resultado = await datos_reales()
        except Exception as e:
            print(f"[WARN] MongoDB no disponible ({e}). Usando datos hardcodeados.")
            resultado = datos_hardcodeados()

    html = construir_html(resultado)
    SALIDA.write_text(html, encoding="utf-8")
    print(f"Visualización guardada en: {SALIDA}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hardcoded", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.hardcoded))
