export interface RouteListItem {
  ruta: string
  data: string
  total_parades: number
  clients_visitats: number
  clients_saltats: number
  temps_total_min: number
  // Extra fields for rich UI display:
  zones?: string[]
  repartidor?: string
  kms_estimats?: number
}

export interface RoutesListResponse {
  success: boolean
  routes: RouteListItem[]
  error?: string
}
