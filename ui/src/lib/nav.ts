import type { Recipe } from '@/api/types'

export const go = (path: string) => {
  location.hash = path
}

/** The recipe being edited, plus the agent's summary if it came from /scenario. */
export interface Draft {
  recipe: Recipe
  summary: string | null
}
