import { NextResponse } from "next/server"
import { getDb } from "@/lib/mongodb"

// =================================================================
// API ROUTE: GET /api/truck-data?ruta=19/03/2026|11588007|DR0016
// 
// Connects to MongoDB Atlas collection "resultados"
// Returns the 3D matrices and stats for truck visualization
// =================================================================

export interface TruckDataResponse {
  success: boolean
  data: {
    id: string
    occupancy: number[][][]      // camion_binario - 3D matrix (1=box, 0=empty)
    clients: number[][][]        // camion_ids - 3D matrix (client ID per cell)
    paletsOccupancy: number[][][] // palets_binario
    paletsClients: number[][][]   // palets_ids
    stats: {
      n_paradas: number
      n_palets_usados: number
      total_cajas: number
      ocupacion_pct: number
    }
    dimensions: {
      x: number
      y: number
      z: number
    }
  } | null
  error?: string
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const rutaId = searchParams.get("ruta") // e.g. "19/03/2026|11588007|DR0016"

  try {
    const db = await getDb()
    
    if (!db) {
      return NextResponse.json<TruckDataResponse>(
        {
          success: false,
          data: null,
          error: "MongoDB not configured - please add MONGODB_URI environment variable",
        },
        { status: 503 }
      )
    }
    
    const collection = db.collection("resultados")

    // Find document by id_ruta_algoritmo or get the first one as fallback
    const doc = rutaId
      ? await collection.findOne({ id_ruta_algoritmo: rutaId })
      : await collection.findOne({})

    if (!doc) {
      return NextResponse.json<TruckDataResponse>(
        {
          success: false,
          data: null,
          error: rutaId ? `No data found for route: ${rutaId}` : "No documents in collection",
        },
        { status: 404 }
      )
    }

    // Calculate dimensions from the matrix
    const occupancy = doc.camion_binario as number[][][]
    const dimensions = {
      x: occupancy?.length ?? 0,
      y: occupancy?.[0]?.length ?? 0,
      z: occupancy?.[0]?.[0]?.length ?? 0,
    }

    return NextResponse.json<TruckDataResponse>({
      success: true,
      data: {
        id: doc.id_ruta_algoritmo,
        occupancy: doc.camion_binario,
        clients: doc.camion_ids,
        paletsOccupancy: doc.palets_binario,
        paletsClients: doc.palets_ids,
        stats: {
          n_paradas: doc.n_paradas,
          n_palets_usados: doc.n_palets_usados,
          total_cajas: doc.total_cajas,
          ocupacion_pct: doc.ocupacion_pct,
        },
        dimensions,
      },
    })
  } catch (error) {
    console.error("[API] MongoDB error:", error)
    return NextResponse.json<TruckDataResponse>(
      {
        success: false,
        data: null,
        error: "Database connection error",
      },
      { status: 500 }
    )
  }
}
