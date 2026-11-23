// The Python side as the band speaks to it: the command line of each verb, and what its answers
// and stored files mean. Plain functions; the shell runs the commands and reads the files.
import type { Above, Examined, Hold, Item, Open, Part, Proposal, Reversal, Step } from '../../types'
import { LABELS } from './labels'
import type { Event } from './picker'

export type Ran = { exitCode: number; stdout: string; stderr: string }

// Every verb through the plugin's one launcher for the person's own hand: Python isolated, the plugin's root put on
// its path by hand, so a project's own frameloop/ or json.py never stands in for the writer.
export const argvOf = (root: string, verb: string, args: readonly string[] = []) => [`${root}/hooks/hand.sh`, verb, ...args]

// approve <id> --ticked 0,1,2: the proposal approved whole, every item; for options its one item with --pick <index>.
export const approveArgs = (o: Open): string[] => {
  const choice = o.proposal.kind !== 'options' ? [] : o.pick === null ? [] : ['--pick', String(o.pick)]
  const every = o.proposal.kind === 'options' ? '' : o.proposal.items.map((_, i) => String(i)).join(',')
  return [o.id, '--ticked', every, ...choice, '--shown', o.shown]
}

// A proposal as `show` answers it, with its examination, the digests both were shown by, and the switch of the
// check as it read it; null where it was not.
export type Shown = { proposal: Proposal; examined: Examined | null; foreign: boolean; shown: string; check: 'on' | 'off' }
export const shownOf = (ran: Ran, id: string): Shown | null => {
  const out = parsed(ran)
  const proposal = ran.exitCode === 0 ? proposalOf(out?.proposal, id) : null
  return proposal && typeof out?.shown === 'string'
    ? { proposal, examined: examinedOf(out.examined), foreign: out.foreign === true, shown: out.shown, check: out.check === 'on' ? 'on' : 'off' }
    : null
}
// What `examine` answered: '' where it ran, its sentence kept beside the proposal; else why it could not run.
export const examineFailure = (ran: Ran): string => (ran.exitCode === 0 && parsed(ran) ? '' : failure(ran))
// The digests a proposal and its examination would be shown by now, from their text: the band reads both each second
// and asks `show` again only where these are not the ones it showed.
const sha256 = async (text: string) =>
  [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))].map(b => b.toString(16).padStart(2, '0')).join('')
export const shownNow = async (proposal: string, examined: string | null) =>
  `${await sha256(proposal)}:${examined === null ? 'none' : await sha256(examined)}`

const parsed = (ran: Ran): Record<string, unknown> | null => {
  try {
    const v: unknown = JSON.parse(ran.stdout)
    return v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null
  } catch {
    return null
  }
}
// Why a call did not do its work: the sentence it refused with, where it answered one; else what it printed.
export const failure = (ran: Ran) => {
  const said = parsed(ran)?.said
  return typeof said === 'string' && said.trim() ? said : ran.stderr.trim() || ran.stdout.trim() || `${LABELS.exitCode} ${ran.exitCode}`
}

export const whereOf = (ran: Ran): string => {
  const f = parsed(ran)?.folder
  return ran.exitCode === 0 && typeof f === 'string' && f.trim() && !/[\u0000-\u001f]/.test(f) ? f.replace(/\/+$/, '') : ''
}

// `several` where the faults are rows that look like several claims, which the same proposal sent again keeps.
export type Proposed = { kind: 'faults' | 'failed'; text: string; several?: true } | { kind: 'stored'; id: string; said: string }
export const proposedOf = (ran: Ran): Proposed => {
  const out = parsed(ran)
  const faults = Array.isArray(out?.faults) ? out.faults.map(str) : []
  if (out && faults.length) {
    return { kind: 'faults', text: [str(out.said), ...faults].filter(Boolean).join('\n'), ...(out.several === true ? { several: true as const } : {}) }
  }
  if (out && ran.exitCode === 0 && typeof out.id === 'string' && out.id) return { kind: 'stored', id: out.id, said: str(out.said) }
  return { kind: 'failed', text: failure(ran) }
}

// A proposal's fields as one text whatever the order of their keys, so the same proposal sent again is known.
export const fieldsText = (x: unknown): string => JSON.stringify(x, (_, v) =>
  v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map(k => [k, v[k]])) : v)

export const writtenOf = (id: string, ran: Ran): Event => {
  const said = parsed(ran)?.said
  return ran.exitCode === 0 && typeof said === 'string' ? { type: 'written', id, said, closing: '' } : { type: 'unwritten', id, text: failure(ran) }
}
// The person's word: approved.json's text and the switch's as the band's own writes left them, each or null. The band
// keeps it in the host's store, written only at the person's press or command, and sends it with each look; the
// files on the machine are copies the hooks read, and the look puts back what the word does not hold.
export type Word = { 'approved.json': string | null; switch: string | null }
export const NOTHING: Word = { 'approved.json': null, switch: null }
const textOrNull = (x: unknown) => x === null || typeof x === 'string'
export const isWord = (x: unknown): x is Word =>
  x !== null && typeof x === 'object' && !Array.isArray(x) && Object.keys(x).sort().join() === 'approved.json,switch' &&
  textOrNull((x as Word)['approved.json']) && textOrNull((x as Word).switch)
// the word a write of the person's own hand answers, or the copies a look with nothing sent reads back
export const wordOf = (ran: Ran, key: 'word' | 'copies' = 'word'): Word | null => {
  const w = parsed(ran)?.[key]
  return ran.exitCode === 0 && isWord(w) ? w : null
}
// What a look put back, as the sentence it said; '' where nothing was put back. A look that could not run says why.
export const restoredOf = (ran: Ran): string => {
  const out = parsed(ran)
  if (ran.exitCode === 0 && Array.isArray(out?.restored)) return out.restored.length ? str(out.said) : ''
  return `${LABELS.cannotLook} ${failure(ran)}`
}
// The digests a look with nothing sent answers, held to those the band's first witness kept, which it read once to
// take its word from the copies its own writes left.
export type Digests = Record<string, string | null>
export const digestsOf = (ran: Ran): Digests | null => {
  const d = parsed(ran)?.digests
  if (ran.exitCode !== 0 || d === null || typeof d !== 'object' || Array.isArray(d)) return null
  const held = Object.entries(d as Record<string, unknown>)
  return held.every(([, v]) => v === null || typeof v === 'string') ? (Object.fromEntries(held) as Digests) : null
}
export const sameDigests = (a: unknown, b: Digests) =>
  a !== null && typeof a === 'object' && !Array.isArray(a) &&
  JSON.stringify(Object.entries(a as Record<string, unknown>).sort()) === JSON.stringify(Object.entries(b).sort())

// The line `line` answers, as the text the band draws from: the hooks' sentence, tension, flags, alert, what runs
// now, and work done while a proposal waited, where the watch recorded their write; and nothing where it did not.
export const lineOfRan = (ran: Ran): string => {
  const out = parsed(ran)
  return ran.exitCode === 0 && typeof out?.line === 'string' && out.tension !== null && typeof out?.tension === 'object'
    ? JSON.stringify({ line: out.line, tension: out.tension, flags: out.flags ?? {}, alert: out.alert ?? null, now: out.now ?? null, spent: out.spent ?? {},
      unapproved: out.unapproved ?? null })
    : ''
}

// the switch's sentence, or the one it refused with: either way it ran
export const switchedOf = (ran: Ran): string => {
  const said = parsed(ran)?.said
  return typeof said === 'string' && said.trim() ? said : `${LABELS.cannotRun} ${failure(ran)}`
}

// A stored file read back: whatever its shape, every text a string and every list a list.
const str = (x: unknown): string =>
  typeof x === 'string' ? x : typeof x === 'number' || typeof x === 'boolean' ? String(x) : x == null ? '' : JSON.stringify(x)
const list = (x: unknown): unknown[] => (Array.isArray(x) ? x : [])
const obj = (x: unknown): Record<string, unknown> => (x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as Record<string, unknown>) : {})
// a quoted claim or a part may come as its words, or as an object that holds them
const said = (x: unknown): string => (typeof x === 'object' && x !== null && !Array.isArray(x) ? str(obj(x).words ?? obj(x).place ?? obj(x).id) : Array.isArray(x) ? x.map(str).join(' · ') : str(x))
const lines = (x: unknown): string[] => (typeof x === 'string' ? [x] : Array.isArray(x) ? x.map(str) : list(obj(x).lines).map(str))
// the claim reversed, kept with a step: its words and its own lines; none where no reversal is kept
const reversalOf = (x: unknown): Reversal | null =>
  x !== null && typeof x === 'object' && !Array.isArray(x) ? { words: str(obj(x).words), lines: lines(obj(x).lines) } : null
const stepOf = (x: unknown): Step => ({ lines: lines(obj(x).lines), reversal: reversalOf(obj(x).reversal) })

const itemOf = (x: unknown): Item => {
  const i = obj(x)
  return {
    words: str(i.words), of: str(i.of), narrows: said(i.narrows), owner: said(i.owner),
    step: lines(i.step), reversal: reversalOf(obj(i.step).reversal), predicts: str(i.predicts), old: str(i.old),
    ask: str(i.ask),
  }
}
const holdOf = (h: unknown): Hold => {
  const command = str(obj(h).command)
  return { words: said(h), detail: command || list(obj(h).untouched).map(str).join(' '), byCommand: command !== '' }
}
// a crossing's part, with its own claims and holds; one named by its place alone holds none
const partOf = (x: unknown): Part =>
  typeof x === 'object' && x !== null && !Array.isArray(x)
    ? { place: str(obj(x).place), items: list(obj(x).items).map(itemOf), holds: list(obj(x).holds).map(holdOf) }
    : { place: said(x), items: [], holds: [] }

export const proposalOf = (raw: unknown, id: string): Proposal | null => {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return null
  const p = obj(raw)
  const items: Item[] = list(p.items).map(itemOf)
  const s = p.split === null || typeof p.split !== 'object' ? null : obj(p.split)
  const r = p.reason === null || typeof p.reason !== 'object' ? null : obj(p.reason)
  return {
    id, kind: str(p.kind), place: str(p.place), title: str(p.title), items,
    holds: list(p.holds).map(holdOf),
    split: s && {
      parts: list(s.parts).map(partOf),
      holes: list(s.holes).map(obj).map(h => ({
        claim: said(h.claim),
        from: list(h.from).map(said), kind: str(h.kind),
      })),
      contracts: list(s.contracts).map(obj).map(c => ({ id: str(c.id), words: str(c.words), provides: said(c.provides), depends: list(c.depends).map(said), command: str(c.command) })),
    },
    options: Array.isArray(p.options) ? p.options.map(obj).map(o => ({ words: str(o.words), cost: str(o.cost) })) : null,
    reason: r && { words: str(r.words), about: said(r.about) },
  }
}

// what an examination found of a crossing's claim above, or of a contract: true, false, or null for not settled
const found = (v: unknown): boolean | null => (v === true || v === false ? v : null)
const aboveOf = (x: unknown): Above => ({ carried: found(obj(x).carried), carry: list(obj(x).carry).map(str), idle: list(obj(x).idle).map(str) })
const byIndex = <T>(x: unknown, of: (v: unknown) => T): Record<string, T> =>
  Object.fromEntries(Object.entries(obj(x)).filter(([n]) => /^\d+$/.test(n)).map(([n, v]) => [n, of(v)]))

export const examinedOf = (raw: unknown): Examined | null => {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) return null
  const x = obj(raw)
  return {
    above: byIndex(x.above, aboveOf),
    contracts: byIndex(x.contracts, found),
    marks: list(x.marks).map(obj).map(m => ({ item: typeof m.item === 'number' ? m.item : -1, kind: str(m.kind), words: str(m.words) })),
    carried: typeof x.carried === 'boolean' ? x.carried : null,
    validated: x.validated === true,
    // each item's step as the examination kept it, by the item's index: what the writer writes and the readers ask
    steps: Object.fromEntries(Object.entries(obj(x.steps)).filter(([n]) => /^\d+$/.test(n)).map(([n, s]) => [n, stepOf(s)])),
    failed: typeof x.failed === 'string' ? x.failed : '',
  }
}
