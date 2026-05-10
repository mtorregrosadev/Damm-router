"use client"

import { createContext, useContext, useState, type ReactNode } from "react"

type Language = "ca" | "en"

interface Translations {
  // Login
  login: {
    title: string
    subtitle: string
    username: string
    password: string
    enter: string
    footer: string
  }
  // Dashboard
  dashboard: {
    truck: string
    lookInside: string
    estimatedTime: string
    estimatedKm: string
    stops: string
    backToMap: string
    occupation: string
    reserved: string
    references: string
    returnables: string
    barrels: string
    pallets: string
    legend: string
    dragToRotate: string
    scrollToZoom: string
    rightClickToMove: string
    timeWindow: string
    products: string
    warehouse: string
  }
  // Stops
  stops: {
    return: string
    outOfWindow: string
    sharedStop: string
    unloadTime: string
    skipped: string
    loadingRoute: string
    noData: string
  }
}

const translations: Record<Language, Translations> = {
  ca: {
    login: {
      title: "DDI Smart Truck",
      subtitle: "Sistema d'Optimització de Rutes i Càrrega",
      username: "Usuari",
      password: "Contrasenya",
      enter: "Entrar",
      footer: "Damm · Distribució Directa Integral",
    },
    dashboard: {
      truck: "Camió",
      lookInside: "Veure càrrega",
      estimatedTime: "Temps estimat",
      estimatedKm: "Km estimats",
      stops: "parades",
      backToMap: "Tornar al mapa",
      occupation: "Ocupació",
      reserved: "reservats",
      references: "referències",
      returnables: "retornables",
      barrels: "Barrils",
      pallets: "Palets",
      legend: "Llegenda",
      dragToRotate: "Arrossega per rotar",
      scrollToZoom: "Scroll per zoom",
      rightClickToMove: "Clic dret per moure",
      timeWindow: "Finestra horària",
      products: "productes",
      warehouse: "MAGATZEM DDI MOLLET",
    },
    stops: {
      return: "Retorn al magatzem",
      outOfWindow: "Fora de franja",
      sharedStop: "Parada compartida",
      unloadTime: "min descàrrega",
      skipped: "saltats",
      loadingRoute: "Carregant ruta…",
      noData: "Cap ruta calculada",
    },
  },
  en: {
    login: {
      title: "DDI Smart Truck",
      subtitle: "Route and Load Optimization System",
      username: "Username",
      password: "Password",
      enter: "Sign in",
      footer: "Damm · Direct Integral Distribution",
    },
    dashboard: {
      truck: "Truck",
      lookInside: "Look inside",
      estimatedTime: "Est. time",
      estimatedKm: "Est. km",
      stops: "stops",
      backToMap: "Back to map",
      occupation: "Occupation",
      reserved: "reserved",
      references: "references",
      returnables: "returnables",
      barrels: "Barrels",
      pallets: "Pallets",
      legend: "Legend",
      dragToRotate: "Drag to rotate",
      scrollToZoom: "Scroll to zoom",
      rightClickToMove: "Right click to move",
      timeWindow: "Time window",
      products: "products",
      warehouse: "DDI MOLLET WAREHOUSE",
    },
    stops: {
      return: "Return to warehouse",
      outOfWindow: "Out of window",
      sharedStop: "Shared stop",
      unloadTime: "min unload",
      skipped: "skipped",
      loadingRoute: "Loading route…",
      noData: "No route computed",
    },
  },
}

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: Translations
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("ca")

  return (
    <LanguageContext.Provider
      value={{
        language,
        setLanguage,
        t: translations[language],
      }}
    >
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider")
  }
  return context
}
