import { useCallback, useEffect, useState } from 'react'
import { getCatalog, MOCK } from '@/api/client'
import type { Catalog } from '@/api/types'
import type { Draft } from '@/lib/nav'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AlertTriangle } from 'lucide-react'
import { Home } from '@/screens/Home'
import { RecipeScreen } from '@/screens/RecipeScreen'
import { Generating } from '@/screens/Generating'
import { Watch } from '@/screens/Watch'
import { WatchEntry } from '@/screens/WatchEntry'
import { HowItWorks } from '@/screens/HowItWorks'
import { cn } from '@/lib/utils'

const TABS = [
  { label: 'Watch', href: '#/', area: 'watch' },
  { label: 'Three lenses', href: '#/lenses', area: 'lenses' },
  { label: 'Ask for a play', href: '#/ask', area: 'ask' },
  { label: 'How it works', href: '#/how', area: 'how' },
]
// Which tab a route lives under. The recipe and progress screens belong to Ask for a play.
const AREA: Record<string, string> = { '': 'watch', matches: 'watch', lenses: 'lenses', ask: 'ask', recipe: 'ask', jobs: 'ask', how: 'how' }

const parse = () => location.hash.replace(/^#/, '') || '/'

// App state from the spec: current recipe (draft), job in progress (route /jobs/:id), open match (route /matches/:id).
export default function App() {
  const [path, setPath] = useState(parse)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [text, setText] = useState('')
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)

  useEffect(() => {
    const on = () => setPath(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  const loadCatalog = useCallback(() => {
    setCatalogError(null)
    getCatalog().then(setCatalog).catch((e: Error) => setCatalogError(e.message))
  }, [])
  useEffect(loadCatalog, [loadCatalog])

  const [, a, id] = path.split('/')
  const area = AREA[a] ?? 'watch'
  let screen
  if (a === 'recipe' && catalog && draft) {
    screen = <RecipeScreen catalog={catalog} draft={draft} setDraft={setDraft} text={text} setText={setText} />
  } else if (a === 'jobs' && id) {
    screen = <Generating jobId={id} hasRecipe={!!draft} />
  } else if (a === 'matches' && id) {
    screen = <Watch key={id} matchId={id} />
  } else if (area === 'ask') {
    screen = <Home catalog={catalog} text={text} setText={setText} setDraft={setDraft} />
  } else if (a === 'how') {
    screen = <HowItWorks />
  } else {
    screen = <WatchEntry screen={a === 'lenses' ? 'lenses' : 'watch'} />
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-5">
          <a href="#/" aria-label="tacticAI"><img src="/tacticai-logo-dark-bg.png" alt="tacticAI" className="h-9" /></a>
          <nav aria-label="Main" className="flex items-center gap-1">
            {TABS.map((t) => (
              <a
                key={t.area} href={t.href} aria-current={area === t.area ? 'page' : undefined}
                className={cn('rounded-lg px-3 py-1.5 text-sm font-medium transition-colors', area === t.area ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground')}
              >
                {t.label}
              </a>
            ))}
          </nav>
          <div className="w-24 text-right text-xs">
            {MOCK && <span className="rounded-full border border-primary px-2 py-0.5 text-primary">Mock data</span>}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-5 py-5">
        {catalogError && (
          <Alert className="mb-4">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Could not load the catalog</p>
              <p className="text-muted-foreground">{catalogError}</p>
            </div>
            <Button size="sm" variant="outline" onClick={loadCatalog}>Retry</Button>
          </Alert>
        )}
        {screen}
      </main>
    </div>
  )
}
