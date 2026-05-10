import { NextResponse } from "next/server"
import { getDb } from "@/lib/mongodb"
import type { RoutesListResponse, RouteListItem } from "@/lib/types/routes"

// Force dynamic so it doesn't cache empty results
export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const db = await getDb()
    if (!db) {
      return NextResponse.json<RoutesListResponse>(
        { success: false, routes: [], error: "MongoDB not configured" },
        { status: 503 }
      )
    }

    const coll = db.collection(process.env.MONGODB_COLLECTION_RUTA_RESUM || 'ruta_resum')
    const docs = await coll.find({}).sort({ _id: -1 }).toArray()

    // Enrich with zone names and driver names
    const routes: RouteListItem[] = await Promise.all(docs.map(async (doc) => {
      // 1. Get zones from ruta_punts in order
      const punts = await db.collection('ruta_punts')
        .find({ ruta: doc.ruta, data: doc.data })
        .sort({ ordre: 1 })
        .toArray()
      
      const zones = punts.map(p => p.zona).filter(Boolean)
      // Deduplicate consecutive zones but keep order flow
      const flowZones = zones.reduce((acc: string[], val) => {
        if (acc.length === 0 || acc[acc.length - 1] !== val) {
          acc.push(val)
        }
        return acc
      }, [])

      // 2. Get driver from detalle_entrega
      const detalle = await db.collection('detalle_entrega')
        .findOne({ ruta: doc.ruta, fecha: doc.data })

      return {
        ruta:             doc.ruta,
        data:             doc.data,
        total_parades:    doc.total_parades    ?? 0,
        clients_visitats: doc.clients_visitats ?? 0,
        clients_saltats:  doc.clients_saltats  ?? 0,
        temps_total_min:  doc.temps_total_min  ?? 0,
        zones:            flowZones.length > 0 ? flowZones : ['Sortida'],
        repartidor:       detalle?.repartidor ?? 'Repartidor Desconegut',
        kms_estimats:     Math.round((doc.temps_total_min ?? 0) * 0.4) // mock KMs as a factor of time
      } as any
    }))

    return NextResponse.json({ success: true, routes } as any)
  } catch (error) {
    console.error("[API] routes error:", error)
    return NextResponse.json(
      { success: false, routes: [], error: "Database error" } as any,
      { status: 500 }
    )
  }
}
