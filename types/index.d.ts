export type Live = {
  session: string
  at: number
  state: 'reading' | 'done'
  what?: string
  why?: string | null
  step_started?: number | null
  answers?: number
  tokens?: number // what the reader has spent on this reading
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
  wake?: boolean // this reading starts a turn for Claude, once the session is free
}

// One item of a decomposition, as the picker shows it.
export type Item = { text: string; detail?: string; isChecked: boolean }

// What the picker holds until its round closes. `node` is the frame's place in the tree: a
// node's id, or none for frame 0.
export type Proposal = { title: string; node?: string; items: Item[]; leftOut: string[] }

declare module 'claude-code' {
  interface PluginState {
    'frame-loop': {
      live: Live | null
      frame: number
      dismissedAt: number
      openedAt: number
      off: boolean
      proposal: Proposal | null
      woken: number
    }
  }
}
