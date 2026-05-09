"use client"

import { LanguageToggle } from "@/components/language-toggle"
import { routeData } from "@/lib/mock-data"

export function Topbar() {
  return (
    <header className="flex h-[52px] items-center justify-between border-b border-border bg-card px-4">
      {/* Left side */}
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
          {routeData.driver.initials}
        </div>
        
        {/* Driver name */}
        <span className="text-[13px] text-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>{routeData.driver.name}</span>
        
        {/* Route ID badge */}
        <div className="rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
          {routeData.routeId}
        </div>
        
        {/* Date badge */}
        <div className="rounded-full border border-border bg-muted px-3 py-1 text-xs text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
          {routeData.date}
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        <LanguageToggle />
        
        {/* Damm logo text */}
        <div className="flex items-center gap-1">
          <span className="text-lg font-bold text-primary" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>DAMM</span>
          <span className="text-primary">*</span>
        </div>
      </div>
    </header>
  )
}
