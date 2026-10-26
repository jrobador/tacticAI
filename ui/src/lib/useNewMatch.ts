// State of the New match screen. It lives in App so the chat and the job keep going while the user is on another screen.
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, createJob, draftScenario, issuesOf, watchJob } from '@/api/client'
import type { Catalog, JobStatus, Recipe } from '@/api/types'
import { TERMINAL_STATES } from '@/api/types'
import { go } from './nav'
import { changesNote, chipsOf, titleOf, type Gen, type Msg, type Teams } from './newMatch'

const FIRST_NOTE = 'Here is the tactical setup I wrote from your request. Change any chip, then Generate.'
const isTerminal = (s: JobStatus | null) => !!s && TERMINAL_STATES.includes(s.state)

export const isRunning = (g: Gen | null) => !!g && !isTerminal(g.status)

interface Deps {
  catalog: Catalog | null
  teams: Teams
  /** True while the user is on the New match screen. */
  onChat: () => boolean
  toast: (text: string) => void
  /** Called when a job ends, so the match lists are reloaded. */
  reload: () => void
}

export function useNewMatch(deps: Deps) {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [gen, setGen] = useState<Gen | null>(null)
  const [starting, setStarting] = useState<number | null>(null)
  const msgsRef = useRef<Msg[]>([])
  const genRef = useRef<Gen | null>(null)
  const nid = useRef(1)
  const handled = useRef<string | null>(null)
  const d = useRef(deps)
  d.current = deps

  const putMsgs = (fn: (m: Msg[]) => Msg[]) => { msgsRef.current = fn(msgsRef.current); setMsgs(msgsRef.current) }
  const putGen = (fn: (g: Gen | null) => Gen | null) => { genRef.current = fn(genRef.current); setGen(genRef.current) }
  const add = (m: DistributiveOmit<Msg, 'id'>) => { const id = nid.current++; putMsgs((l) => [...l, { ...m, id } as Msg]); return id }
  const replace = (id: number, m: DistributiveOmit<Msg, 'id'>) => putMsgs((l) => l.map((x) => (x.id === id ? ({ ...m, id } as Msg) : x)))

  const errorOf = (e: unknown): DistributiveOmit<Msg, 'id'> => {
    const issues = issuesOf(e)
    if (issues) return { kind: 'error', code: null, msg: 'The setup is not valid', todo: issues.map((i) => `${i.path}: ${i.message}`).join(' · ') }
    const status = e instanceof ApiError && e.status ? `${e.status} · ` : ''
    return { kind: 'error', code: null, msg: `${status}${e instanceof Error ? e.message : String(e)}`, todo: 'Your text and setup are kept. Try again.' }
  }

  /** Asks the Scenario Agent with the latest setup as the base. `user` false: the text is ours (the loosen call), no bubble. */
  async function draft(text: string, user: boolean) {
    const base = [...msgsRef.current].reverse().find((m) => m.kind === 'setup')
    const before: Recipe | null = base && base.kind === 'setup' ? base.recipe : null
    if (user) add({ kind: 'user', text })
    const wid = add({ kind: 'writing' })
    try {
      const r = await draftScenario(text, before)
      const { catalog, teams } = d.current
      const changes = before && catalog ? changesNote(before, r.recipe, catalog, teams) : []
      const note = !before ? FIRST_NOTE
        : changes.length ? `Updated: ${changes.join(' · ')}.`
        : user ? 'Nothing in that changes the setup. Change a chip, or describe it another way.'
        : 'Nothing could be loosened. Change a chip, then Generate.'
      replace(wid, { kind: 'setup', recipe: r.recipe, note, issues: r.errors ?? [] })
    } catch (e) {
      replace(wid, errorOf(e))
    }
  }

  const send = (text: string) => {
    const t = text.trim()
    if (t && !msgsRef.current.some((m) => m.kind === 'writing')) void draft(t, true)
  }

  const setChip = (msgId: number, key: string, val: string) => {
    const cat = d.current.catalog
    if (!cat) return
    putMsgs((l) => l.map((m) => {
      if (m.id !== msgId || m.kind !== 'setup') return m
      const chip = chipsOf(m.recipe, cat, d.current.teams).find((c) => c.key === key)
      if (!chip) return m
      const next = structuredClone(m.recipe)
      chip.set(next, val)
      return { ...m, recipe: next, issues: [] }
    }))
  }

  async function generate(msgId: number) {
    const m = msgsRef.current.find((x) => x.id === msgId)
    if (!m || m.kind !== 'setup' || m.used || starting !== null) return
    setStarting(msgId)
    try {
      const r = await createJob({ recipe: m.recipe })
      if (r.kind === 'existing') { go(`/matches/${r.match_id}`); return }
      putMsgs((l) => l.map((x) => (x.id === msgId && x.kind === 'setup' ? { ...x, used: true } : x)))
      add({ kind: 'gen', jobId: r.job_id })
      putGen(() => ({ jobId: r.job_id, title: titleOf(m.recipe, d.current.teams), recipe: m.recipe, status: null, error: null }))
      go(`/jobs/${r.job_id}`)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        add({ kind: 'error', code: 'TAI-SRC-409', msg: 'The engine is busy with another match', todo: 'One match records at a time. This setup is kept; Generate again when the current match is done.', toMatches: true })
      } else add(errorOf(e))
    } finally {
      setStarting(null)
    }
  }

  /** Route #/jobs/:id: follow that job. Does nothing when it is already the one on screen. */
  const follow = useCallback((jobId: string) => {
    if (genRef.current?.jobId === jobId) return
    genRef.current = { jobId, title: null, recipe: null, status: null, error: null }
    setGen(genRef.current)
    msgsRef.current = [{ id: nid.current++, kind: 'gen', jobId }]
    setMsgs(msgsRef.current)
  }, [])

  const reset = () => {
    if (isRunning(genRef.current)) return
    msgsRef.current = []
    genRef.current = null
    setMsgs([])
    setGen(null)
    if (location.hash.startsWith('#/jobs/')) go('/')
  }

  // Job end: open the match, or tell the user where it is. Runs once per job.
  function finish(jobId: string, st: JobStatus) {
    const g = genRef.current
    d.current.reload()
    if (st.state === 'done' && st.match_id) {
      const id = st.match_id
      setTimeout(() => {
        if (d.current.onChat()) go(`/matches/${id}`)
        else d.current.toast(`${g?.title ?? 'Your match'} is ready in Matches`)
      }, 650)
    } else if (st.state === 'no_winner') {
      add({
        kind: 'error', code: 'TAI-SRC-002', msg: 'No play matched',
        todo: `${st.message ?? 'None of the engine runs matched.'}${g?.recipe ? ' The Scenario Agent is loosening the strictest condition below.' : ''}`,
      })
      if (g?.recipe) void draft(`No run matched: ${st.message ?? ''}. Loosen the strictest condition.`, false)
    } else if (st.state === 'failed') {
      add({ kind: 'error', code: null, msg: 'Generation failed', todo: st.message ?? 'The job failed.' })
    }
    void jobId
  }
  const finishRef = useRef(finish)
  finishRef.current = finish

  const jobId = gen?.jobId
  useEffect(() => {
    if (!jobId) return
    return watchJob(
      jobId,
      (st) => {
        if (genRef.current?.jobId !== jobId) return
        putGen((g) => (g && g.jobId === jobId ? { ...g, status: st, error: null } : g))
        if (isTerminal(st) && handled.current !== jobId) { handled.current = jobId; finishRef.current(jobId, st) }
      },
      (e) => putGen((g) => (g && g.jobId === jobId ? { ...g, error: e.message } : g)),
    )
  }, [jobId])

  return { msgs, gen, starting, send, setChip, generate, follow, reset }
}

type DistributiveOmit<T, K extends keyof never> = T extends unknown ? Omit<T, K> : never
export type NewMatchState = ReturnType<typeof useNewMatch>
