"use client"

import { LanguageProvider } from "@/lib/i18n"
import { LoginForm } from "@/components/login-form"

export default function HomePage() {
  return (
    <LanguageProvider>
      <LoginForm />
    </LanguageProvider>
  )
}
