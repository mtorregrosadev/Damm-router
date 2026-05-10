export interface RouteStop {
  ordre: number
  nom: string
  zona: string
  lat: number
  lon: number
  hora: string
  hora_s: number
  temps_descarrega: number
  parada_compartida: number | null
  fora_franja: boolean
  /** Polilínia del tram que porta fins a aquesta parada: array de [lat, lon] */
  geometria: [number, number][]
}

export interface RouteSummary {
  ruta: string
  data: string
  total_parades: number
  clients_visitats: number
  clients_saltats: number
  temps_total_min: number
}

export interface RouteDataResponse {
  success: boolean
  summary: RouteSummary | null
  stops: RouteStop[]
  error?: string
}
