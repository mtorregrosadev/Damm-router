"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"

interface Message {
  role: "assistant" | "user"
  content: string
}

export function AiChat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hola! Sóc el teu assistent logístic de Damm. Com et puc ajudar avui?" }
  ])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isTyping])

  const handleSend = async () => {
    if (!input.trim() || isTyping) return

    const userMsg = input.trim()
    setInput("")
    setMessages(prev => [...prev, { role: "user", content: userMsg }])
    
    setIsTyping(true)

    // Simulate AI response
    setTimeout(() => {
      let response = ""
      if (userMsg.toLowerCase().includes("ruta")) {
        response = "La teva ruta actual té 7 parades i s'estima que acabaràs a les 14:30. Tot va segons el previst."
      } else if (userMsg.toLowerCase().includes("camió") || userMsg.toLowerCase().includes("carrega")) {
        response = "El camió està al 85% de la seva capacitat. Tens 4 palets de cervesa i 2 de producte retornable."
      } else {
        response = "Entès. Estic processant la teva consulta sobre el sistema logístic DDI. Vols que revisi l'ordre de les properes parades?"
      }
      
      setMessages(prev => [...prev, { role: "assistant", content: response }])
      setIsTyping(false)
    }, 1500)
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Bot className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground" style={{ fontFamily: 'var(--font-title)', textTransform: 'uppercase' }}>Assistent Damm</h2>
          <p className="text-[10px] text-green-500 font-medium">En línia</p>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4" viewportRef={scrollRef}>
        <div className="space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`flex max-w-[80%] gap-2 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                  {m.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </div>
                <div className={`rounded-2xl px-4 py-2 text-sm ${m.role === "user" ? "bg-primary text-primary-foreground rounded-tr-none" : "bg-muted text-foreground rounded-tl-none shadow-sm"}`}>
                  {m.content}
                </div>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="flex max-w-[80%] gap-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="flex items-center gap-1 rounded-2xl bg-muted px-4 py-2 text-foreground rounded-tl-none shadow-sm">
                  <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  <span className="text-xs text-muted-foreground italic">L'IA està escrivint...</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t border-border bg-card p-4 pb-8 md:pb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Pregunta qualsevol cosa..."
            className="flex-1 rounded-full border border-border bg-muted px-4 py-2 text-sm focus:border-primary focus:outline-none"
          />
          <Button onClick={handleSend} disabled={isTyping} className="rounded-full h-10 w-10 p-0">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
