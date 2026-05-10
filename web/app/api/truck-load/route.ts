import { NextResponse } from "next/server"
import { getDb } from "@/lib/mongodb"
import type { TruckLoadAPIResponse, TruckLoadData } from "@/lib/types/truck-load"

export const dynamic = 'force-dynamic'

const DEFAULT_PHYSICAL_SIZE = { length: 7.0, width: 2.4, height: 2.5 }

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const routeId = searchParams.get("routeId")

  try {
    const db = await getDb()
    if (!db) {
      return NextResponse.json<TruckLoadAPIResponse>(
        { success: false, data: null, error: "MongoDB not configured" },
        { status: 503 }
      )
    }

    console.log("DB NAME:", db.databaseName)
    // Let's force it to 'resultado_carga_camion' to match the python code
    const coll = db.collection('resultado_carga_camion')
    console.log("COLLECTION NAME:", coll.collectionName)

    // id_ruta_algoritmo format: "{date}|{driver_id}|{route_code}"
    let doc = null
    if (routeId) {
      doc = await coll.findOne({ id_ruta_algoritmo: { $regex: `\\|${routeId}$` } })
      if (!doc) {
        doc = await coll.findOne({ id_ruta_algoritmo: { $regex: routeId } })
      }
    } else {
      doc = await coll.findOne({}, { sort: { _id: -1 } })
    }

    if (!doc) {
      return NextResponse.json<TruckLoadAPIResponse>(
        { success: false, data: null, error: routeId ? `No data for route ${routeId}` : "No documents found" },
        { status: 404 }
      )
    }

    const firstCamion = doc.camiones?.[0] ?? doc
    const clients = (firstCamion.camion_ids ?? []) as number[][][]

    // In Python: X=cols, Y=rows, Z=levels
    // Next.js expects: X=cols, Y=levels, Z=rows
    // So we map: x=X, y=Z, z=Y
    const x = clients.length
    const y = clients[0]?.[0]?.length ?? 0 // levels (Z in Python)
    const z = clients[0]?.length ?? 0 // rows (Y in Python)

    let totalCells = 0
    let usedCells  = 0
    
    // We recreate occupancy and transposed clients
    const occupancy: number[][][] = Array(x).fill(0).map(() => Array(y).fill(0).map(() => Array(z).fill(0)))
    const clientsMapped: number[][][] = Array(x).fill(0).map(() => Array(y).fill(0).map(() => Array(z).fill(0)))

    for (let xi = 0; xi < x; xi++) {
      const py_Y = clients[xi]?.length ?? 0
      for (let yi = 0; yi < py_Y; yi++) {
        const py_Z = clients[xi]?.[yi]?.length ?? 0
        for (let zi = 0; zi < py_Z; zi++) {
          totalCells++
          const val = clients[xi]?.[yi]?.[zi] ?? 0
          if (val > 0) {
            usedCells++
            occupancy[xi][zi][yi] = 1
            clientsMapped[xi][zi][yi] = val
          }
        }
      }
    }

    const data: TruckLoadData = {
      routeId:       doc.id_ruta_algoritmo ?? routeId ?? "",
      truckId:       routeId ? `TRK-${routeId}` : "TRK-UNKNOWN",
      truckPlate:    doc.matricula ?? "",
      loadTimestamp: new Date().toISOString(),
      truck: {
        dimensions:  { x, y, z },
        physicalSize: DEFAULT_PHYSICAL_SIZE,
        occupancy,
        clients: clientsMapped,
      },
      capacity: {
        totalCells,
        usedCells,
        totalWeight: Math.round(totalCells * 35),
        usedWeight:  Math.round(usedCells  * 35),
      },
    }

    return NextResponse.json<TruckLoadAPIResponse>({ success: true, data })
  } catch (error) {
    console.error("[API] truck-load error:", error)
    return NextResponse.json<TruckLoadAPIResponse>(
      { success: false, data: null, error: "Database error" },
      { status: 500 }
    )
  }
}
