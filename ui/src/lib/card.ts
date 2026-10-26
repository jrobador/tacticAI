// 9:16 card (1080 x 1920) built in the browser with a canvas: moment title, explanation and the main player's rating.
const NAVY = '#0c172a'
const OFFWHITE = '#f0f0f0'
const LIME = '#c6f432'

export interface CardContent {
  filename: string
  kicker: string // e.g. "Minute 3' · Brackenford Athletic"
  title: string
  text: string
  player: string | null // "#9 Larkspur"
  rating: number | null // goals added; null: no rating line
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const next = line ? `${line} ${word}` : word
    if (line && ctx.measureText(next).width > maxW) { lines.push(line); line = word } else line = next
  }
  if (line) lines.push(line)
  return lines
}

export async function renderCard(c: CardContent): Promise<Blob> {
  try {
    await Promise.all([document.fonts.load('700 80px "Geist Variable"'), document.fonts.load('400 40px "Inter Variable"')])
  } catch { /* the fallback fonts draw instead */ }
  const cv = document.createElement('canvas')
  cv.width = 1080
  cv.height = 1920
  const ctx = cv.getContext('2d')
  if (!ctx) throw new Error('Canvas is not available in this browser')
  ctx.fillStyle = NAVY
  ctx.fillRect(0, 0, 1080, 1920)
  ctx.fillStyle = LIME
  ctx.fillRect(80, 200, 120, 10)
  ctx.textBaseline = 'top'
  ctx.fillStyle = LIME
  ctx.font = '600 40px "Inter Variable", system-ui, sans-serif'
  ctx.fillText(c.kicker.toUpperCase(), 80, 240)
  let y = 340
  ctx.fillStyle = OFFWHITE
  ctx.font = '700 96px "Geist Variable", "Inter Variable", system-ui, sans-serif'
  for (const l of wrap(ctx, c.title, 920)) { ctx.fillText(l, 80, y); y += 112 }
  y += 40
  ctx.fillStyle = 'rgba(240,240,240,0.78)'
  ctx.font = '400 52px "Inter Variable", system-ui, sans-serif'
  for (const l of wrap(ctx, c.text, 920)) { ctx.fillText(l, 80, y); y += 70 }
  if (c.player && c.rating !== null) {
    ctx.fillStyle = LIME
    ctx.font = '700 200px "Geist Variable", "Inter Variable", system-ui, sans-serif'
    ctx.fillText(`${c.rating >= 0 ? '+' : ''}${c.rating.toFixed(2)}`, 80, 1380)
    ctx.fillStyle = OFFWHITE
    ctx.font = '400 44px "Inter Variable", system-ui, sans-serif'
    ctx.fillText(`${c.player} · goals added (engine)`, 80, 1620)
  } else if (c.player) {
    ctx.fillStyle = OFFWHITE
    ctx.font = '400 44px "Inter Variable", system-ui, sans-serif'
    ctx.fillText(c.player, 80, 1620)
  }
  ctx.fillStyle = 'rgba(240,240,240,0.55)'
  ctx.font = '600 36px "Inter Variable", system-ui, sans-serif'
  ctx.fillText('tacticAI', 80, 1780)
  return new Promise((res, rej) => cv.toBlob((b) => (b ? res(b) : rej(new Error('Could not build the image'))), 'image/png'))
}

export async function downloadCard(c: CardContent) {
  const url = URL.createObjectURL(await renderCard(c))
  const a = document.createElement('a')
  a.href = url
  a.download = `${c.filename}.png`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
