"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Truck, Loader2 } from "lucide-react"
import { LanguageToggle } from "@/components/language-toggle"
import { useLanguage } from "@/lib/i18n"
import { Button } from "@/components/ui/button"
import { useRoutes } from "@/hooks/use-routes"
import { AUTH_KEY } from "@/hooks/use-auth"

function formatMinutes(min: number): string {
  const h = Math.floor(min / 60)
  const m = min % 60
  return h > 0 ? `${h}h ${m}min` : `${m}min`
}

export function LoginForm() {
  const [selectedRuta, setSelectedRuta] = useState("")
  const [selectedData, setSelectedData] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const { t } = useLanguage()
  const { routes, isLoading: routesLoading, isError } = useRoutes()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedRuta || !selectedData) return
    setIsLoading(true)
    localStorage.setItem(AUTH_KEY, JSON.stringify({ ruta: selectedRuta, data: selectedData }))
    router.push("/dashboard")
  }

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center bg-background">
      <div className="absolute right-6 top-6">
        <LanguageToggle />
      </div>

      <div className="w-full max-w-[460px] rounded-xl border border-border bg-card p-12" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        {/* Icon */}
        <div className="mb-4 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <Truck className="h-9 w-9 text-primary" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-center text-[22px] text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>
          {t.login.title}
        </h1>
        <p className="mt-1 text-center text-[13px] text-muted-foreground" style={{ fontFamily: 'var(--font-ui)' }}>
          {t.login.subtitle}
        </p>

        <div className="my-6 h-px bg-border" />

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>
              Selecciona la teva ruta
            </label>

            {routesLoading ? (
              <div className="flex h-12 items-center justify-center gap-2 rounded-lg border border-border bg-muted text-xs text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Carregant rutes…
              </div>
            ) : isError ? (
              <div className="flex h-12 items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 text-xs text-destructive">
                Error carregant les rutes
              </div>
            ) : routes.length === 0 ? (
              <div className="flex h-12 items-center justify-center rounded-lg border border-border bg-muted text-xs text-muted-foreground">
                No hi ha rutes disponibles
              </div>
            ) : (
              <div className="max-h-[380px] overflow-y-auto rounded-lg border border-border bg-background">
                {routes.map((route) => {
                  const isSelected = selectedRuta === route.ruta && selectedData === route.data
                  return (
                    <button
                      key={`${route.ruta}-${route.data}`}
                      type="button"
                      onClick={() => { setSelectedRuta(route.ruta); setSelectedData(route.data) }}
                      className={`flex flex-col w-full border-b border-border p-4 text-left transition-colors last:border-b-0 ${
                        isSelected
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted text-foreground"
                      }`}
                    >
                      <div className="flex w-full items-center justify-between mb-1.5">
                        <span className="text-[11px] opacity-70" style={{ fontFamily: 'var(--font-data)' }}>
                          {route.data}
                        </span>
                        
                        <div className="flex items-center justify-end gap-3 text-xs opacity-80" style={{ fontFamily: 'var(--font-data)' }}>
                          <span>{route.kms_estimats || 45} Km's</span>
                          <span>{formatMinutes(route.temps_total_min)}</span>
                        </div>
                      </div>

                      <div className="mb-2">
                        <p className="text-[13px] font-medium leading-relaxed opacity-90 line-clamp-1" style={{ fontFamily: 'var(--font-data)' }}>
                          {route.zones?.join(' ➔ ') || 'Sortida ➔ Ruta'}
                        </p>
                      </div>
                      
                      <div className="flex items-center justify-between gap-3 opacity-60 text-xs font-semibold" style={{ fontFamily: 'var(--font-data)' }}>
                        <span className="truncate">{route.ruta}</span>
                        <span className="truncate">{route.repartidor || 'Repartidor'}</span>
                        <span className="whitespace-nowrap">{route.total_parades} parades</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          <Button
            type="submit"
            disabled={isLoading || !selectedRuta}
            className="mt-4 h-11 w-full rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              t.login.enter
            )}
          </Button>
        </form>

        <p className="mt-8 text-center text-[11px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
          {t.login.footer}
        </p>
      </div>
    </div>
  )
}
