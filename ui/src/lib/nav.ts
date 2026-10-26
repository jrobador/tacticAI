export const go = (path: string) => {
  location.hash = path
}

/** Filter the Matches grid opens with (set before go('/matches'), cleared once read). */
export const matchesPreset: { value: string | null } = { value: null }
