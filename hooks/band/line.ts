// The line above the prompt and the /frame-loop command, as plain functions over the live file's text. The band
// draws only what bears value: at rest the tension of the whole tree with its total and a few counted flags; while a
// run goes on, what runs, its seconds and the counts the hooks know; a run whose hook went silent, said to have ended
// without a word; and an alert the hooks wrote, a failure or another hand's change. A naught is never drawn.
import { LABELS } from './labels'
import { duration, shown } from './view'

// What runs now, as the hooks wrote it: its sentence, when it began and last wrote (seconds since the epoch), when
// its hook's limit ends it, and the counts so far; tokens null where no record gave any.
export type Now = { said: string; began: number; at: number; until: number; writer: number; maker: number; records: number; tokens: number | null }
// Files changed while a proposal waited in the picker and nothing of it was approved: the hooks' sentence for it,
// how many files, and the proposals that waited.
export type Unapproved = { said: string; files: number; proposals: string[] }
// counts: open, fulfilled, rest, refused; `line` the last sentence the hooks wrote, for /frame-loop alone; `spent`
// what the checks of this session spent so far, tokens and model calls
export type Line = {
  line: string; counts: number[]; flags: number[]; alert: string; now: Now | null; spent: { tokens: number; calls: number }
  unapproved: Unapproved | null
}
const KEYS = ['open', 'fulfilled', 'rest', 'refused'] as const
// What needs the person's eye, each counted: rows not read and why, files nobody asked for, contracts with no
// check, and checks that did not hold.
const FLAGS = ['nostep', 'off', 'opened', 'outside', 'unchecked', 'failing'] as const
// A run's hook writes at least every 10 seconds while it lives (frameloop/now.py, BEAT_SECONDS); one silent this
// long is taken as gone.
export const STALE_SECONDS = 45

const n = (x: unknown) => (typeof x === 'number' && Number.isFinite(x) ? Math.max(0, Math.floor(x)) : 0)
const time = (x: unknown) => (typeof x === 'number' && Number.isFinite(x) && x > 0 ? x : null)

export const nowOf = (x: unknown): Now | null => {
  if (x === null || typeof x !== 'object' || Array.isArray(x)) return null
  const v = x as Record<string, unknown>
  const began = time(v.began), at = time(v.at), until = time(v.until)
  if (typeof v.said !== 'string' || began === null || at === null || until === null) return null
  const tokens = typeof v.tokens === 'number' && Number.isFinite(v.tokens) ? n(v.tokens) : null
  return { said: shown(v.said), began, at, until, writer: n(v.writer), maker: n(v.maker), records: n(v.records), tokens }
}

export const unapprovedOf = (x: unknown): Unapproved | null => {
  if (x === null || typeof x !== 'object' || Array.isArray(x)) return null
  const v = x as Record<string, unknown>
  const ids = Array.isArray(v.proposals) ? v.proposals.filter((id): id is string => typeof id === 'string' && isPlain(id)) : []
  return typeof v.said === 'string' && v.said && n(v.files) > 0 && ids.length ? { said: shown(v.said), files: n(v.files), proposals: ids } : null
}

export const lineOf = (text: string): Line => {
  let v: {
    line?: unknown; tension?: Record<string, unknown>; flags?: Record<string, unknown>; alert?: unknown; now?: unknown; spent?: Record<string, unknown>
    unapproved?: unknown
  } = {}
  try {
    v = JSON.parse(text) ?? {}
  } catch {
    // no file, or one in mid-write: nothing to show
  }
  // never the word ready from a file: the band shows it by the counts alone, whatever a line says
  const said = typeof v.line === 'string' ? v.line.split(' · ').filter(piece => !/\bready\b/i.test(piece)).join(' · ') : ''
  const alert = typeof v.alert === 'string' ? shown(v.alert) : ''
  return {
    line: shown(said), counts: KEYS.map(k => n(v.tension?.[k])), flags: FLAGS.map(k => n(v.flags?.[k])), alert, now: nowOf(v.now),
    spent: { tokens: n(v.spent?.tokens), calls: n(v.spent?.calls) }, unapproved: unapprovedOf(v.unapproved),
  }
}

const total = (l: Line) => l.counts.reduce((a, b) => a + b, 0)
// No frame, nothing running, nothing to alert and nothing spent: every count is naught, and the band draws nothing.
export const isQuiet = (l: Line) => total(l) === 0 && l.now === null && !l.alert && !l.spent.tokens && !l.spent.calls
const counted = (k: number, [one, many]: readonly [string, string]) => `${k} ${k === 1 ? one : many}`
// A count of tokens in short, as frameloop/words.py's `tokens` gives it: below a thousand as it is; under a million in
// thousands with one decimal; from a million in millions, its decimal left out where it is naught; each step rounded
// half up in whole numbers, so both sides agree.
export const tokensShort = (k: number): string => {
  if (k < 1000) return String(k)
  let tenths = Math.floor((k + 50) / 100)
  if (tenths < 10000) return `${Math.floor(tenths / 10)}.${tenths % 10}${LABELS.thousands}`
  tenths = Math.floor((k + 50000) / 100000)
  return tenths % 10 === 0 ? `${tenths / 10}${LABELS.millions}` : `${Math.floor(tenths / 10)}.${tenths % 10}${LABELS.millions}`
}
// What a run, or the session's checks, spent: tokens in short where known, else model calls; nothing where naught.
const spentText = (tokens: number | null, calls: number): string[] =>
  tokens ? [`${tokensShort(tokens)} ${LABELS.spend.tokens}`] : calls ? [counted(calls, LABELS.spend.calls)] : []

// The whole tree's tension, its total said once: "1 of 6 fulfilled", then each other state that is not naught, and
// the open ones beside them so the line adds up; with `whole`, every state, naughts too.
export const tensionText = (l: Line, whole = false): string[] => {
  const [open = 0, fulfilled = 0, rest = 0, refused = 0] = l.counts
  const shownToo = whole || rest > 0 || refused > 0
  return [
    `${fulfilled} ${LABELS.of} ${total(l)} ${LABELS.counts.fulfilled}`,
    ...(shownToo ? [`${open} ${LABELS.counts.open}`] : []),
    ...(whole || rest ? [`${rest} ${LABELS.counts.rest}`] : []),
    ...(whole || refused ? [`${refused} ${LABELS.counts.refused}`] : []),
  ]
}
const flagsText = (l: Line): string[] => FLAGS.flatMap((k, i) => (l.flags[i] ? [counted(l.flags[i] ?? 0, LABELS.flags[k])] : []))
// The band at rest: its name, the tree's tension, what needs the person's eye, each counted, and what the checks of
// this session spent where they spent anything; the tail is what the band draws after its name, in bold.
export const restTail = (l: Line) =>
  [...(total(l) ? tensionText(l) : []), ...flagsText(l), ...spentText(l.spent.tokens, l.spent.calls)].map(piece => ` · ${piece}`).join('')
export const restText = (l: Line) => `${LABELS.name}${restTail(l)}`

// A run the band takes as ended: its hook silent past STALE_SECONDS, or its limit passed.
export const isEnded = (now: Now, seconds: number) => seconds - now.at > STALE_SECONDS || seconds > now.until
// While a run goes on: a frame of the spinner, moving each second, how long it has run and what it spent so far, then
// what runs, last, since it may quote a row's words and a cut at the end must take no count.
export const nowText = (now: Now, seconds: number): string => {
  if (isEnded(now, seconds)) return [LABELS.name, now.said, LABELS.ended].join(' · ')
  const frame = LABELS.spinner[Math.floor(seconds) % LABELS.spinner.length]
  const spent = spentText(now.tokens, now.writer + now.maker + now.records)
  return [`${frame} ${LABELS.name}`, duration(seconds - now.began), ...spent, now.said].join(' · ')
}

// /frame-loop: the whole state, every count of the tree with its flags, the alert where there is one, the last
// sentence the hooks wrote, and what runs, where a run goes on.
export const commandText = (l: Line, seconds: number) =>
  [
    [LABELS.name, ...tensionText(l, true), ...flagsText(l)].join(' · '),
    ...(l.alert ? [l.alert] : []),
    ...(l.line && l.line !== l.alert ? [l.line] : []),
    ...(l.now ? [nowText(l.now, seconds)] : []),
  ].join('\n')

// A session id names a file only when it is a plain id.
export const isPlain = (id: string) => /^[A-Za-z0-9_-]{1,128}$/.test(id)

export type Command = { kind: 'show' } | { kind: 'switch'; to: 'on' | 'off' } | { kind: 'say'; text: string }
export const commandOf = (args: string, isPerson: boolean): Command => {
  const a = args.trim().toLowerCase()
  if (a === '') return { kind: 'show' }
  if (a !== 'on' && a !== 'off') return { kind: 'say', text: LABELS.usage }
  return isPerson ? { kind: 'switch', to: a } : { kind: 'say', text: LABELS.personOnly }
}
