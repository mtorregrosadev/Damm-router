"use client"

import { LanguageToggle } from "@/components/language-toggle"
import { routeData } from "@/lib/mock-data"

export function Topbar() {
  return (
    <header className="flex h-[52px] items-center justify-between border-b border-[#1E2A45] bg-[#10162A] px-4">
      {/* Left side */}
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#C8102E] text-xs font-semibold text-white">
          {routeData.driver.initials}
        </div>
        
        {/* Driver name */}
        <span className="text-[13px] text-white">{routeData.driver.name}</span>
        
        {/* Route ID badge */}
        <div className="rounded-full border border-[#2A3A5C] bg-[#1A2340] px-3 py-1 text-xs text-[#7A90C0]">
          {routeData.routeId}
        </div>
        
        {/* Date badge */}
        <div className="rounded-full border border-[#2A3A5C] bg-[#1A2340] px-3 py-1 text-xs text-[#7A90C0]">
          {routeData.date}
        </div>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        <LanguageToggle />
        
        {/* Damm logo text */}
        <div className="flex items-center gap-1">
          <span className="text-lg font-bold text-[#C8102E]">DAMM</span>
          <span className="text-[#C8102E]">*</span>
        </div>
      </div>
    </header>
  )
}
