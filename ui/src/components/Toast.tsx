import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { Check } from 'lucide-react'

const ToastContext = createContext<(text: string) => void>(() => {})

/** `const toast = useToast(); toast('Ready in Matches')` shows a message for 3 s. */
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [text, setText] = useState<string | null>(null)
  const timer = useRef<number>(0)
  const show = useCallback((t: string) => {
    setText(t)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setText(null), 3000)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      {text && (
        <div role="status" className="rise fixed bottom-6 left-1/2 z-[90] flex -translate-x-1/2 items-center gap-2 rounded-[10px] bg-foreground px-4 py-2.5 text-[13px] font-semibold text-background shadow-[0_10px_30px_rgba(0,0,0,.35)]">
          <span className="grid size-4 place-items-center rounded-full bg-background text-primary"><Check className="size-2.5" strokeWidth={3} /></span>
          {text}
        </div>
      )}
    </ToastContext.Provider>
  )
}
