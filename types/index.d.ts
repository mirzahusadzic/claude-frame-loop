// A proposal as the band shows it: the stored file read back and made safe to draw
// (hooks/band/frameloop.ts, proposalOf). Every text is a string, every list a list.
export type Reversal = { words: string; lines: string[] }
// `ask` is the session's own question to the person, where the row says more, less or other than their words.
export type Item = { words: string; of: string; narrows: string; owner: string; step: string[]; reversal: Reversal | null; predicts: string; old: string; ask: string }
// `byCommand` where a command checks it, its detail that command; else its detail the paths a change must not touch.
export type Hold = { words: string; detail: string; byCommand: boolean }
export type Hole = { claim: string; from: string[]; kind: string }
// A contract's command is '' where it has no check yet, as one laid down before anything is built.
export type Contract = { id: string; words: string; provides: string; depends: string[]; command: string }
// A part of a crossing: its place, its own claims, each narrowing a claim above, and what must hold there.
export type Part = { place: string; items: Item[]; holds: Hold[] }
export type Proposal = {
  id: string
  kind: string
  place: string
  title: string
  items: Item[]
  holds: Hold[]
  split: { parts: Part[]; holes: Hole[]; contracts: Contract[] } | null
  options: { words: string; cost: string }[] | null
  reason: { words: string; about: string } | null
}
export type Mark = { item: number; kind: string; words: string }
// A step as the readers will be asked it: the claim's own lines, and the claim reversed with its own, where kept.
export type Step = { lines: string[]; reversal: Reversal | null }
// Whether a crossing's parts carry a claim above (null: not settled), with the parts it does not hold without and
// those it holds without; a claim above with none was not read.
export type Above = { carried: boolean | null; carry: string[]; idle: string[] }
// Steps and marks number every claim of a proposal in one order: its items, then each part's own in turn. `failed`
// is the one plain line of an examination that could not run at all, '' for none.
export type Examined = {
  marks: Mark[]
  carried: boolean | null
  validated: boolean
  steps: Record<string, Step>
  above: Record<string, Above>
  contracts: Record<string, boolean | null>
  failed: string
}

// The one open proposal, as the picker in its pane holds it, and the ids stored while it was open, which wait their
// turn. `shown` is the digests `show` gave of the proposal and its examination as drawn, which the writer is held
// to; `check` the switch as `show` read it; `checking` while the band's own examination of it runs, from `began` in
// seconds; `checkFailed` why that examination could not run, where the process itself said so; `said` the person's
// own prompt the proposal answers, as the prompt hook saw it. `cursor` is the stop under the cursor: `said`, a row
// by its id, `ok`, or `retry`; `answered` the rows under review the person said yes to;
// `kept` the rows a proposal this one took the place of had answered, each by its words and its question, kept where
// they stand unchanged;
// `changing` the stop the person pressed enter on, under which its one line is open in the pane; `typed` his words in
// that line as he types them; `changed` the line he sent as his change, there or at the host's prompt, while the
// session answers it and the picker is
// closed; `details` the row whose details are open, or `said` for his sentence whole; `help` the list of keys; `aside`
// the picker closed by esc, the proposal waiting; `writing` and `failed` the writer's run and its refusal.
export type Open = {
  id: string
  proposal: Proposal
  examined: Examined | null
  foreign: boolean
  shown: string
  check: 'on' | 'off'
  checking: boolean
  began: number
  checkFailed: string
  said: string
  cursor: string
  answered: string[]
  kept: string[]
  changing: string
  typed: string
  changed: string
  details: string
  help: boolean
  aside: boolean
  pick: number | null
  writing: boolean
  failed: string
}
// A proposal stored while another was open, by its id, with the kind and place a re-proposal is known by, and the
// person's prompt it answers.
export type Waiting = { id: string; kind: string; place: string; said: string }
// `told`: each proposal closed with nothing written, as the sentence the session is told at its next prompt;
// `ever`: whether this session's picker ever held a proposal, so each prompt then says how it stands; `closing`:
// the one line that tells what the person approved last, drawn in the band until their next prompt.
export type Picker = { open: Open | null; waiting: Waiting[]; told: string[]; ever: boolean; closing: string }

// What the band, as a second witness, found changed outside the picker: the sentence on its line, and whether the
// session has been told it yet.
export type Witness = { line: string; told: boolean }

// Where the host seated the picker's pane, for the proposal `id`: `shown` drawn with the keyboard given it once at
// least, `unheld` drawn but never given the keyboard, `undrawn` open but waiting undrawn on a terminal too narrow for
// a pane nobody asked for; '' where no pane is open.
export type Seat = { id: string; seat: '' | 'shown' | 'unheld' | 'undrawn' }

declare module 'claude-code' {
  interface PluginState {
    'frame-loop': {
      picker: Shaped<Picker>; live: string; witness: Shaped<Witness>; beat: number; asked: string; drafted: boolean; seat: Shaped<Seat>
    }
  }
}
