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

// Where the work is, as the hooks write it beside the live state (<session>.part.json): the part
// engaged, by its name, where it sits and whether its requirements are all done, or none at
// frame 0; and the name of a part just left when it is done.
export type PartLine = {
  at: number
  part: { name: string; where: string; done: boolean } | null
  finished: string | null
}

// One item of a decomposition, as the picker shows it. `quotes` is the parent's requirement a
// part's line narrows, by its id: never shown, read for the header and the record.
export type Item = { text: string; detail?: string; isChecked: boolean; isRemoval?: boolean; quotes?: string }

// One part of a split: its file's name, its plain name, its lines, the paths it may change, and
// whether its page was seen.
export type Part = { id: string; name: string; items: Item[]; scope: string[]; isSeen: boolean }

// What the picker holds until its round closes. `node` is the frame's place in the tree: a
// node's id, or none for frame 0. A split holds its parts instead of items, the frame it splits
// (`parent`, a node's id, or none for frame 0), and the page shown: one per part, then the
// review, numbered from 0.
export type Proposal = {
  title: string
  node?: string
  items: Item[]
  leftOut: string[]
  parts?: Part[]
  parent?: string
  page?: number
  header?: Header
}

// Where a split sits, read by the band from the tree's files as the picker opens, never from
// Claude's words: the frames from frame 0 down to the one split, by name; that frame's
// requirements by id, each with whether its words are the ones approved; the principles every
// part inherits, each with the frame it comes from; the guide's rules, counted; and what could
// not be read.
export type Header = {
  path: string[]
  requirements: Record<string, { text: string; isApproved: boolean }>
  principles: { text: string; from: string }[]
  guideRules: number
  unread?: string
  // The split's own reading, when the hooks read this split before the picker opened: each
  // requirement split, by id, as covered, not covered or not settled, and each line that was
  // found needed, or one the other lines already cover.
  // and the lines whose detail says which words they narrow and not how.
  // Per part, by its id: the rule its lines may break (or "not settled"), the guide's rules that
  // hold for its files, and what a change there will owe.
  check?: {
    requirements: Record<string, string>
    lines: Record<string, string>
    thin?: string[]
    parts?: Record<string, { breaks: string | null; scoped: string[]; owes: string[] }>
  }
}

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
      part: PartLine | null
    }
  }
}
