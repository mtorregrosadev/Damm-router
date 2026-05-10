import { NextResponse } from "next/server"
import { getDb } from "@/lib/mongodb"
import type { RoutesListResponse, RouteListItem } from "@/lib/types/routes"

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

    const routes: RouteListItem[] = docs.map(doc => ({
      ruta:             doc.ruta,
      data:             doc.data,
      total_parades:    doc.total_parades    ?? 0,
      clients_visitats: doc.clients_visitats ?? 0,
      clients_saltats:  doc.clients_saltats  ?? 0,
      temps_total_min:  doc.temps_total_min  ?? 0,
    }))

    return NextResponse.json<RoutesListResponse>({ success: true, routes })
  } catch (error) {
    console.error("[API] routes error:", error)
    return NextResponse.json<RoutesListResponse>(
      { success: false, routes: [], error: "Database error" },
      { status: 500 }
    )
  }
}
