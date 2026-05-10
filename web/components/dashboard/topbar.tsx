"use client"

import { useState, useRef, useEffect } from "react"
import { LogOut, ChevronDown, Loader2 } from "lucide-react"
import { LanguageToggle } from "@/components/language-toggle"
import { useRoutes } from "@/hooks/use-routes"
import type { RouteSummary } from "@/lib/types/route-data"

interface TopbarProps {
  summary:        RouteSummary | null
  onLogout:       () => void
  onRouteChange:  (ruta: string, data: string) => void
}

function formatMinutes(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return h > 0 ? `${h}h ${m}min` : `${m}min`
}

export function Topbar({ summary, onLogout, onRouteChange }: TopbarProps) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { routes, isLoading } = useRoutes()

  const routeId   = summary?.ruta  ?? "—"
  const routeDate = summary?.data  ?? "—"

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  return (
    <header className="flex h-[52px] items-center justify-between border-b border-border bg-card px-4">
      {/* Left side */}
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
          DD
        </div>

        {/* Brand */}
        <span className="text-[13px] text-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>
          DDI Mollet
        </span>

        {/* Route selector */}
        <div ref={dropdownRef} className="relative">
          <button
            onClick={() => setOpen(v => !v)}
            className="flex items-center gap-1 rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
            style={{ fontFamily: 'var(--font-data)' }}
          >
            {routeId}
            <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>

          {open && (
            <div className="absolute left-0 top-full z-50 mt-1 w-72 overflow-hidden rounded-lg border border-border bg-card shadow-lg">
              <div className="border-b border-border px-3 py-2">
                <p className="text-[10px] font-medium uppercase text-muted-foreground" style={{ fontFamily: 'var(--font-ui)' }}>
                  Canvia de ruta
                </p>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {isLoading ? (
                  <div className="flex items-center justify-center gap-2 py-4 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Carregant…
                  </div>
                ) : routes.length === 0 ? (
                  <div className="py-4 text-center text-xs text-muted-foreground">
                    No hi ha rutes
                  </div>
                ) : (
                  routes.map((route) => {
                    const isCurrent = route.ruta === summary?.ruta && route.data === summary?.data
                    return (
                      <button
                        key={`${route.ruta}-${route.data}`}
                        onClick={() => { onRouteChange(route.ruta, route.data); setOpen(false) }}
                        className={`flex w-full items-center justify-between border-b border-border/50 px-3 py-2 text-left text-xs transition-colors last:border-b-0 ${
                          isCurrent
                            ? "bg-primary/10 text-primary"
                            : "text-foreground hover:bg-muted"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {isCurrent && <div className="h-1.5 w-1.5 rounded-full bg-primary" />}
                          <span className="font-semibold" style={{ fontFamily: 'var(--font-data)' }}>
                            {route.ruta}
                          </span>
                          <span className="text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
                            {route.data}
                          </span>
                        </div>
                        <div className="flex gap-2 text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
                          <span>{route.total_parades} par.</span>
                          <span>{formatMinutes(route.temps_total_min)}</span>
                        </div>
                      </button>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Date badge */}
        <div className="rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
          {routeDate}
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        <LanguageToggle />

        <div className="flex items-center gap-1">
          <span className="text-lg font-bold text-primary" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>DAMM</span>
          <span className="text-primary">*</span>
        </div>

        {/* Logout */}
        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Tancar sessió"
        >
          <LogOut className="h-3.5 w-3.5" />
          <span style={{ fontFamily: 'var(--font-ui)' }}>Sortir</span>
        </button>
      </div>
    </header>
  )
}
