export type Live = {
  session: string
  at: number
  state: 'reading' | 'done'
  what?: string
  why?: string | null
  so_far?: string | null
  step_started?: number | null
  answers?: number
  expected?: number | null
  expected_seconds?: number | null
  step?: string
  n?: number
  of?: number
  started?: number | null
  decision?: string
  lines?: string[]
  detail?: string[]
  pid?: number // a background read's process
}

declare module 'claude-code' {
  interface PluginState {
    'frame-loop': { live: Live | null; frame: number; dismissedAt: number; openedAt: number; off: boolean }
  }
}
