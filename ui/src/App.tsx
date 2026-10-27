import { useCallback, useEffect, useRef, useState } from 'react'
import { getCatalog, getLibrary, listMatches } from '@/api/client'
import type { Catalog } from '@/api/types'
import { go } from '@/lib/nav'
import { NewMatch } from '@/screens/NewMatch'
import { Match } from '@/screens/Match'
import { Matches, type MatchesData } from '@/screens/Matches'
import { Architecture } from '@/screens/Architecture'
import { Sidebar } from '@/components/Sidebar'
import { ToastProvider, useToast } from '@/components/Toast'
import { DEFAULT_TEAMS } from '@/lib/format'
import { isRunning, useNewMatch } from '@/lib/useNewMatch'

const parse = () => location.hash.replace(/^#/, '') || '/'

// App state from the spec: current recipe (draft), job in progress (route /jobs/:id), open match (route /matches/:id).
export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  )
}

function Shell() {
  const toast = useToast()
  const [path, setPath] = useState(parse)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [matchesData, setMatchesData] = useState<MatchesData | null>(null)
  const [matchesError, setMatchesError] = useState<string | null>(null)
  const [navMin, setNavMin] = useState(true)

  const [, a, id] = path.split('/')
  const onMatch = a === 'matches' && !!id

  useEffect(() => {
    const on = () => setPath(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])


  // Typing N outside an input starts a new match.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName
      if ((e.key === 'n' || e.key === 'N') && !e.metaKey && !e.ctrlKey && !e.altKey && !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag ?? '')) go('/')
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  }, [])

  const loadCatalog = useCallback(() => {
    setCatalogError(null)
    getCatalog().then(setCatalog).catch((e: Error) => setCatalogError(e.message))
  }, [])
  useEffect(loadCatalog, [loadCatalog])

  // Reload the match lists when the route changes, so a finished job shows up in the count and the grid.
  const reloadMatches = useCallback(() => {
    Promise.all([listMatches(), getLibrary()])
      .then(([matches, lib]) => { setMatchesData({ matches, entries: lib.entries }); setMatchesError(null) })
      .catch((e: Error) => setMatchesError(e.message))
  }, [])
  useEffect(reloadMatches, [reloadMatches, a])

  // New match: chat and job state live here so they survive navigating away.
  const onChat = !a || a === 'jobs'
  const onChatRef = useRef(onChat)
  onChatRef.current = onChat
  const teams = matchesData?.matches[0]?.teams ?? DEFAULT_TEAMS
  const nm = useNewMatch({ catalog, teams, onChat: () => onChatRef.current, toast, reload: reloadMatches })
  const { follow } = nm
  useEffect(() => { if (a === 'jobs' && id) follow(id) }, [a, id, follow])
  const busyLabel = !onChat && isRunning(nm.gen) ? `Making “${nm.gen?.title ?? 'your match'}”` : undefined

  const matchesCount = matchesData ? matchesData.matches.filter((m) => !m.library_id).length + matchesData.entries.length : 0

  let screen
  if (a === 'matches' && !id) {
    screen = <Matches data={matchesData} error={matchesError} catalog={catalog} />
  } else if (a === 'arch') {
    screen = <Architecture />
  } else if (!onMatch) {
    screen = (
      <NewMatch nm={nm} catalog={catalog} catalogError={catalogError} retryCatalog={loadCatalog} teams={teams}
        namedTeams={!!matchesData?.matches.length} entries={matchesData?.entries ?? []} heroMatchId={matchesData?.matches[0]?.match_id ?? null} />
    )
  } else {
    screen = <Match key={id} matchId={id} />
  }

  return (
    <div className="flex min-h-screen" style={{ "--nav-w": `${navMin ? 64 : 232}px` } as React.CSSProperties}>
      <Sidebar route={a ?? ''} min={navMin} onToggle={() => setNavMin((v) => !v)} matchesCount={matchesCount} busyLabel={busyLabel} />
      <main className="flex min-w-0 flex-1 flex-col">{screen}</main>
    </div>
  )
}
