export interface Stop {
  id: number
  name: string
  address: string
  timeWindow: string
  lat: number
  lng: number
  returnables?: {
    type: "barrels" | "boxes"
    count: number
  }
  products: {
    references: number
    barrels: number
    boxes: number
  }
  loadZone: {
    redBoxes: number
    blueBoxes: number
  }
}

export interface RouteData {
  routeId: string
  driver: {
    name: string
    initials: string
    id: string
  }
  date: string
  estimatedTime: string
  estimatedKm: number
  totalStops: number
  totalReferences: number
  totalReturnables: number
  truckCapacity: {
    total: number
    used: number
    returnablesReserved: number
  }
  warehouse: {
    name: string
    lat: number
    lng: number
  }
  stops: Stop[]
}

export const routeData: RouteData = {
  routeId: "DR0006",
  driver: {
    name: "Jose Velez",
    initials: "JV",
    id: "DA0216",
  },
  date: "30/01/2026",
  estimatedTime: "4h 20min",
  estimatedKm: 34,
  totalStops: 8,
  totalReferences: 57,
  totalReturnables: 12,
  truckCapacity: {
    total: 11.2,
    used: 8.2,
    returnablesReserved: 2.1,
  },
  warehouse: {
    name: "MAGATZEM DDI MOLLET",
    lat: 41.5388,
    lng: 2.2118,
  },
  stops: [
    {
      id: 1,
      name: "CASA MAURA",
      address: "C/Ferrer i Guàrdia 21",
      timeWindow: "08:30–11:00",
      lat: 41.5401,
      lng: 2.2134,
      returnables: { type: "barrels", count: 2 },
      products: { references: 8, barrels: 2, boxes: 3 },
      loadZone: { redBoxes: 2, blueBoxes: 1 },
    },
    {
      id: 2,
      name: "CAFETERIA ESCLAT",
      address: "Nicaragua S/N",
      timeWindow: "08:00–11:00",
      lat: 41.5378,
      lng: 2.2098,
      returnables: { type: "boxes", count: 3 },
      products: { references: 6, barrels: 1, boxes: 4 },
      loadZone: { redBoxes: 3, blueBoxes: 1 },
    },
    {
      id: 3,
      name: "BAR ESPERANZA",
      address: "Av. Burgos 12",
      timeWindow: "09:00–13:00",
      lat: 41.5412,
      lng: 2.2167,
      products: { references: 5, barrels: 0, boxes: 2 },
      loadZone: { redBoxes: 2, blueBoxes: 0 },
    },
    {
      id: 4,
      name: "BAR NIKOL",
      address: "C/Barcelona 45",
      timeWindow: "11:00–15:00",
      lat: 41.5365,
      lng: 2.2089,
      returnables: { type: "barrels", count: 4 },
      products: { references: 12, barrels: 4, boxes: 6 },
      loadZone: { redBoxes: 4, blueBoxes: 2 },
    },
    {
      id: 5,
      name: "CAN TORRAS",
      address: "Pl. Major 3",
      timeWindow: "09:00–12:00",
      lat: 41.5429,
      lng: 2.2201,
      products: { references: 4, barrels: 1, boxes: 2 },
      loadZone: { redBoxes: 1, blueBoxes: 1 },
    },
    {
      id: 6,
      name: "LA GIRALDA",
      address: "C/Martorelles 8",
      timeWindow: "10:00–14:00",
      lat: 41.5502,
      lng: 2.2334,
      returnables: { type: "boxes", count: 3 },
      products: { references: 9, barrels: 2, boxes: 5 },
      loadZone: { redBoxes: 3, blueBoxes: 1 },
    },
    {
      id: 7,
      name: "RESTAURANT MAS",
      address: "Av. Catalunya 22",
      timeWindow: "11:00–15:00",
      lat: 41.5478,
      lng: 2.2289,
      products: { references: 7, barrels: 1, boxes: 3 },
      loadZone: { redBoxes: 2, blueBoxes: 0 },
    },
  ],
}
