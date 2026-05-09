"use client"

import { useLanguage } from "@/lib/i18n"

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage()

  return (
    <div className="flex items-center rounded-full border border-[#1E2A45] bg-[#1A2340] p-0.5">
      <button
        onClick={() => setLanguage("ca")}
        className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
          language === "ca"
            ? "bg-[#C8102E] text-white"
            : "text-[#7A90C0] hover:text-white"
        }`}
      >
        CA
      </button>
      <button
        onClick={() => setLanguage("en")}
        className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
          language === "en"
            ? "bg-[#C8102E] text-white"
            : "text-[#7A90C0] hover:text-white"
        }`}
      >
        EN
      </button>
    </div>
  )
}
