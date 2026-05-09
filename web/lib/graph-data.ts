export interface GraphNode {
  id: string
  lat: number
  lng: number
  type: "warehouse" | "stop" | "intersection"
  stopId?: number
  label?: string
}

export interface GraphEdge {
  from: string
  to: string
  isReturn?: boolean
}

export const graphNodes: GraphNode[] = [
  { id: "wh", lat: 41.5388, lng: 2.2118, type: "warehouse" },
  
  // warehouse → stop_1 (go east first, then north)
  { id: "i1a", lat: 41.5388, lng: 2.2134, type: "intersection" },
  { id: "i1b", lat: 41.5401, lng: 2.2134, type: "intersection" },
  { id: "s1", lat: 41.5401, lng: 2.2134, type: "stop", stopId: 1, label: "Casa Maura" },

  // stop_1 → stop_2 (go west then south)
  { id: "i2a", lat: 41.5401, lng: 2.2098, type: "intersection" },
  { id: "i2b", lat: 41.5378, lng: 2.2098, type: "intersection" },
  { id: "s2", lat: 41.5378, lng: 2.2098, type: "stop", stopId: 2, label: "Cafeteria Esclat" },

  // stop_2 → stop_3
  { id: "i3a", lat: 41.5378, lng: 2.2167, type: "intersection" },
  { id: "i3b", lat: 41.5412, lng: 2.2167, type: "intersection" },
  { id: "s3", lat: 41.5412, lng: 2.2167, type: "stop", stopId: 3, label: "Bar Esperanza" },

  // stop_3 → stop_4
  { id: "i4a", lat: 41.5412, lng: 2.2089, type: "intersection" },
  { id: "i4b", lat: 41.5365, lng: 2.2089, type: "intersection" },
  { id: "s4", lat: 41.5365, lng: 2.2089, type: "stop", stopId: 4, label: "Bar Nikol" },

  // stop_4 → stop_5
  { id: "i5a", lat: 41.5365, lng: 2.2201, type: "intersection" },
  { id: "i5b", lat: 41.5429, lng: 2.2201, type: "intersection" },
  { id: "s5", lat: 41.5429, lng: 2.2201, type: "stop", stopId: 5, label: "Can Torras" },

  // stop_5 → stop_6 (Martorelles, further north)
  { id: "i6a", lat: 41.5429, lng: 2.2334, type: "intersection" },
  { id: "i6b", lat: 41.5502, lng: 2.2334, type: "intersection" },
  { id: "s6", lat: 41.5502, lng: 2.2334, type: "stop", stopId: 6, label: "La Giralda" },

  // stop_6 → stop_7
  { id: "i7a", lat: 41.5502, lng: 2.2289, type: "intersection" },
  { id: "i7b", lat: 41.5478, lng: 2.2289, type: "intersection" },
  { id: "s7", lat: 41.5478, lng: 2.2289, type: "stop", stopId: 7, label: "Restaurant Mas" },

  // stop_7 → warehouse return (dashed)
  { id: "r1", lat: 41.5478, lng: 2.2118, type: "intersection" },
  { id: "r2", lat: 41.5388, lng: 2.2118, type: "intersection" },
]

// Route traversal order (array of node ids in sequence)
export const routePath: string[] = [
  "wh",
  "i1a", "i1b", "s1",
  "i2a", "i2b", "s2",
  "i3a", "i3b", "s3",
  "i4a", "i4b", "s4",
  "i5a", "i5b", "s5",
  "i6a", "i6b", "s6",
  "i7a", "i7b", "s7",
  "r1", "r2", "wh"  // return path
]

// Edges (pairs of node ids)
export const graphEdges: GraphEdge[] = [
  { from: "wh", to: "i1a" },
  { from: "i1a", to: "i1b" },
  { from: "i1b", to: "s1" },
  { from: "s1", to: "i2a" },
  { from: "i2a", to: "i2b" },
  { from: "i2b", to: "s2" },
  { from: "s2", to: "i3a" },
  { from: "i3a", to: "i3b" },
  { from: "i3b", to: "s3" },
  { from: "s3", to: "i4a" },
  { from: "i4a", to: "i4b" },
  { from: "i4b", to: "s4" },
  { from: "s4", to: "i5a" },
  { from: "i5a", to: "i5b" },
  { from: "i5b", to: "s5" },
  { from: "s5", to: "i6a" },
  { from: "i6a", to: "i6b" },
  { from: "i6b", to: "s6" },
  { from: "s6", to: "i7a" },
  { from: "i7a", to: "i7b" },
  { from: "i7b", to: "s7" },
  { from: "s7", to: "r1", isReturn: true },
  { from: "r1", to: "r2", isReturn: true },
  { from: "r2", to: "wh", isReturn: true },
]

// Get node by id
export function getNodeById(id: string): GraphNode | undefined {
  return graphNodes.find(n => n.id === id)
}

// Get edge key
export function getEdgeKey(from: string, to: string): string {
  return `${from}-${to}`
}
