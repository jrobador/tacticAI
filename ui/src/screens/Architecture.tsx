const A = ({ children }: { children: string }) => <span className="font-semibold text-primary">{children}</span>

const CARDS = [
  {
    title: 'Source',
    body: <><A>Scenario Agent</A> writes the tactical setup from the request. The engine searches for a run that produces the play, then records video and tracking at 10 frames per second.</>,
    mono: null,
    foot: 'Azure Container Apps runs the engine',
  },
  {
    title: 'Interpret',
    body: <>Code infers events from positions, trained models score them, and code proposes tactical notes and phases. <A>Tactical Analyst</A> picks the phases and notes that matter and ranks them. Code detects the moments.</>,
    mono: ['xg_v1 · xpass_v1 · vaep_v1', 'match_context · tactical_evidence · team_shape · pressing_profile · compare_metrics · possession_analysis · player_profile'],
    foot: 'Microsoft Foundry hosts the agent models',
  },
  {
    title: 'Explain',
    body: <><A>Explainer</A> makes one call per match: it receives every moment with its metrics and writes the fact and the why, with placeholders for the numbers. Code fills them in and checks the text; a rejected text falls back to a template.</>,
    mono: null,
    foot: 'Microsoft Foundry · Agent Framework',
  },
  {
    title: 'Personalize and render',
    body: <><A>Lens</A> rewrites tone and side: 3 audiences × 2 languages × 3 sides, with <A>Translator Agent</A> writing the Spanish. <A>Recap Agent</A> writes a 3–5 sentence recap for each. <A>Director</A> proposes the overlay plan per audience and side; code checks it and falls back to rules. <A>Match Q&A</A> answers questions on demand.</>,
    mono: ['search_moments · search_events · count_events'],
    foot: 'Agent Framework orchestrates · Azure Container Apps serves the app',
  },
]

const ERRORS = [
  ['TAI-SRC-002', 'No play matched. The engine found no run that meets every condition in the setup. The Scenario Agent loosens the strictest condition and offers a new setup.'],
  ['TAI-SRC-409', 'The engine is busy with another match. One match records at a time; the setup is kept. Watch a template meanwhile.'],
  ['TAI-QA-001', 'No moments matched. Ask about an event type or name a player.'],
]

export function Architecture() {
  return (
    <section className="flex w-full max-w-[1280px] flex-col gap-8 px-7 pb-14 pt-8">
      <div className="rise flex max-w-[820px] flex-col gap-2.5">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[.08em] text-primary">Architecture</span>
        <h1 className="text-balance text-[32px] font-semibold leading-[1.1] tracking-[-0.025em]">You do two things: create a match and watch it. Everything in between runs on its own.</h1>
        <p className="text-pretty text-[15px] leading-[1.6] text-muted-foreground">Competition rules allow only synthetic data, so tacticAI ships with its own 3D football engine. It produces the same tracking format a real feed would: positions of the 22 players and the ball, frame by frame. In production only the source changes; interpretation, explanations and delivery stay the same.</p>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
        {CARDS.map((c, i) => (
          <div key={c.title} style={{ animationDelay: `${(i + 1) * 60}ms` }} className="rise flex flex-col gap-3 rounded-[14px] border border-foreground/10 bg-panel p-[18px]">
            <span className="font-heading text-lg font-semibold">{c.title}</span>
            <span className="text-[13px] leading-normal text-muted-foreground">{c.body}</span>
            {c.mono && <span className="font-mono text-[11.5px] leading-[1.65]">{c.mono.map((l, j) => <span key={j}>{j > 0 && <br />}{l}</span>)}</span>}
            <span className="mt-auto border-t border-foreground/10 pt-2.5 text-[12.5px] font-medium">{c.foot}</span>
          </div>
        ))}
      </div>
      <div className="rise flex max-w-[820px] flex-col gap-2">
        <h2 className="text-[17px] font-semibold">Error codes</h2>
        {ERRORS.map(([code, text]) => (
          <div key={code} className="grid grid-cols-[130px_minmax(0,1fr)] gap-2.5 border-t border-foreground/10 py-2.5">
            <span className="font-mono text-[12.5px] font-semibold">{code}</span>
            <span className="text-[13.5px] leading-normal text-muted-foreground">{text}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
