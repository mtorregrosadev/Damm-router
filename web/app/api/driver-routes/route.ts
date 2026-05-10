import { NextResponse } from "next/server"
import { getDb } from "@/lib/mongodb"
import type { DriverRoutesResponse, DriverRoute } from "@/lib/types/truck-load"

export async function GET() {
  try {
    const db = await getDb()
    if (!db) {
      return NextResponse.json<DriverRoutesResponse>(
        { success: false, driverId: "", driverName: "", routes: [], error: "MongoDB not configured" },
        { status: 503 }
      )
    }

    const coll = db.collection(process.env.MONGODB_COLLECTION_RUTA_RESUM || 'ruta_resum')
    const docs = await coll.find({}).sort({ _id: -1 }).toArray()

    const routes: DriverRoute[] = docs.map(doc => ({
      routeId:      doc.ruta,
      date:         doc.data,
      status:       "completed" as const,
      truckPlate:   "",
      truckId:      `TRK-${doc.ruta}`,
      stopCount:    doc.total_parades ?? 0,
      estimatedKm:  0,
      matrixConfig: { cols: 0, levels: 0, rows: 0 },
      dimensions:   { length: 7.0, height: 2.5, width: 2.4 },
    }))

    return NextResponse.json<DriverRoutesResponse>({
      success:    true,
      driverId:   "all",
      driverName: "Totes les rutes",
      routes,
    })
  } catch (error) {
    console.error("[API] driver-routes error:", error)
    return NextResponse.json<DriverRoutesResponse>(
      { success: false, driverId: "", driverName: "", routes: [], error: "Database error" },
      { status: 500 }
    )
  }
}
