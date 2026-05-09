"use client"

import { LanguageProvider } from "@/web/lib/i18n"
import { LoginForm } from "@/web/components/login-form"

export default function HomePage() {
  return (
    <LanguageProvider>
      <LoginForm />
    </LanguageProvider>
  )
}
