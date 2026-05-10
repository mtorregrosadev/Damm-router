import { NextResponse } from "next/server"
import { getDb } from "@/lib/mongodb"
import type { RouteDataResponse, RouteStop, RouteSummary } from "@/lib/types/route-data"

const JORNADA_INICI_H = 6

function getDayOfWeek(data: string): number {
  const [day, month, year] = data.split('/').map(Number)
  const date = new Date(year, month - 1, day)
  const dow = date.getDay()
  return dow === 0 ? 7 : dow
}

function parseHoraToSeconds(valor: unknown): number | null {
  if (valor == null || valor === '') return null
  let hores: number
  if (typeof valor === 'string') {
    if (valor.includes('day')) {
      const parts = valor.split(',').pop()!.trim().split(':')
      hores = 24 + parseInt(parts[0]) + parseInt(parts[1]) / 60
    } else {
      const parts = valor.split(':')
      hores = parseInt(parts[0]) + parseInt(parts[1]) / 60
    }
  } else if (typeof valor === 'number') {
    hores = valor * 24
  } else {
    return null
  }
  return Math.round((hores - JORNADA_INICI_H) * 3600)
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const rutaParam = searchParams.get('ruta')
  const dataParam = searchParams.get('data')

  try {
    const db = await getDb()
    if (!db) {
      return NextResponse.json<RouteDataResponse>(
        { success: false, summary: null, stops: [], error: "MongoDB not configured" },
        { status: 503 }
      )
    }

    const collPunts   = process.env.MONGODB_COLLECTION_RUTA_PUNTS  || 'ruta_punts'
    const collResum   = process.env.MONGODB_COLLECTION_RUTA_RESUM   || 'ruta_resum'
    const collDetalle = process.env.MONGODB_COLLECTION_DETALLE       || 'detalle_entrega'
    const collHoraris = process.env.MONGODB_COLLECTION_HORARIOS      || 'horarios_entrega'

    // Obtain summary: filtered or latest
    let rawSummary
    if (rutaParam && dataParam) {
      rawSummary = await db.collection(collResum).findOne({ ruta: rutaParam, data: dataParam })
    } else {
      rawSummary = await db.collection(collResum).findOne({}, { sort: { _id: -1 } })
    }

    if (!rawSummary) {
      return NextResponse.json<RouteDataResponse>(
        { success: false, summary: null, stops: [], error: "No route data found in MongoDB" },
        { status: 404 }
      )
    }

    const summary: RouteSummary = {
      ruta:             rawSummary.ruta,
      data:             rawSummary.data,
      total_parades:    rawSummary.total_parades,
      clients_visitats: rawSummary.clients_visitats,
      clients_saltats:  rawSummary.clients_saltats,
      temps_total_min:  rawSummary.temps_total_min,
    }

    // Get individual stops ordered by ordre
    const stopDocs = await db.collection(collPunts)
      .find({ ruta: summary.ruta, data: summary.data })
      .sort({ ordre: 1 })
      .toArray()

    // Build deudor lookup: client name → deudor ID (from detalle_entrega)
    const nameToDeudor: Record<string, string> = {}
    try {
      const entries = await db.collection(collDetalle)
        .find(
          { ruta: summary.ruta, fecha: summary.data },
          { projection: { nombre_1: 1, destinatario_mc_a_1: 1 } }
        )
        .toArray()
      for (const e of entries) {
        if (e.nombre_1 && e.destinatario_mc_a_1) {
          nameToDeudor[String(e.nombre_1)] = String(e.destinatario_mc_a_1)
        }
      }
    } catch (_) { /* fora_franja will default to false */ }

    // Build time window lookup: deudor ID → { inici_s, fi_s }
    const deudorWindows: Record<string, { inici: number; fi: number }> = {}
    try {
      const dayOfWeek = getDayOfWeek(summary.data)
      const deudorIds = [...new Set(Object.values(nameToDeudor))]
      if (deudorIds.length > 0) {
        const horaris = await db.collection(collHoraris)
          .find({ deudor: { $in: deudorIds }, d_a_semana: String(dayOfWeek) })
          .toArray()
        for (const h of horaris) {
          const inici = parseHoraToSeconds(h.horario_inicia_a)
          const fi    = parseHoraToSeconds(h.horario_termina_a)
          if (inici != null && fi != null) {
            deudorWindows[String(h.deudor)] = { inici, fi }
          }
        }
      }
    } catch (_) { /* fora_franja will default to false */ }

    // Build final stops list
    const stops: RouteStop[] = stopDocs.map(doc => {
      const deudorId = nameToDeudor[doc.nom]
      const win      = deudorId ? deudorWindows[deudorId] : null
      const fora_franja = win
        ? doc.hora_s < win.inici || doc.hora_s > win.fi
        : false

      // Parse geometry: stored as JSON string in MongoDB
      let geometria: [number, number][] = []
      if (doc.geometria_json) {
        try {
          geometria = JSON.parse(doc.geometria_json) as [number, number][]
        } catch (_) { /* leave empty */ }
      }

      return {
        ordre:             doc.ordre,
        nom:               doc.nom,
        zona:              doc.zona,
        lat:               doc.lat,
        lon:               doc.lon,
        hora:              doc.hora,
        hora_s:            doc.hora_s,
        temps_descarrega:  doc.temps_descarrega,
        parada_compartida: doc.parada_compartida ?? null,
        fora_franja,
        geometria,
      }
    })

    return NextResponse.json<RouteDataResponse>({ success: true, summary, stops })
  } catch (error) {
    console.error("[API] route-data error:", error)
    return NextResponse.json<RouteDataResponse>(
      { success: false, summary: null, stops: [], error: "Database error" },
      { status: 500 }
    )
  }
}
