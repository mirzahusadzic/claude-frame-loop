// What the picker shows in its pane, as plain data: (open proposal, width) -> screen. The shell draws each line as one
// row, each stop's lines as one Button of the host's, which its ring walks; where the whole is taller than the pane's
// body, `fit` keeps the header and the last line and windows the rest around the cursor. Every state is told by words
// and glyphs alone; a tone only repeats them (`plain` is the screen with every tone taken away).
import type { Examined, Hold, Item, Open, Proposal, Step } from '../../types'
import { LABELS } from './labels'

// A text from a file, made harmless: one row whatever it holds. A line break is shown as a mark in
// the row, never as a row of its own, and a control or direction character as a replacement mark,
// so no proposal can draw a line that looks like the band's.
export const shown = (x: string) =>
  x
    .replace(/\r\n|[\n\r\u0085\u2028\u2029]/g, ' ⏎ ')
    .replace(/\t/g, ' ')
    .replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]/g, '\ufffd')

// How long a thing has run, as frameloop/words.py's `duration` tells it: under a minute in seconds, as 42 s; from a
// minute in minutes and the seconds left, as 1 m 40 s, and a whole minute as 2 m.
export const duration = (seconds: number): string => {
  const whole = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0
  if (whole < 60) return `${whole} ${LABELS.seconds}`
  const minutes = Math.floor(whole / 60), left = whole % 60
  return left ? `${minutes} ${LABELS.minutes} ${left} ${LABELS.seconds}` : `${minutes} ${LABELS.minutes}`
}

// accent: what needs the person (the cursor, a row under review, what is left to review); dim: a shade quieter.
export type Tone = 'accent' | 'dim' | 'bold'
export type Seg = { text: string; tone?: Tone; cursor?: true }
export type LineKind =
  | 'head' | 'unapproved' | 'path' | 'said' | 'reason' | 'blank' | 'table' | 'group' | 'row' | 'note' | 'detail'
  | 'input' | 'ok' | 'fail' | 'retry' | 'writer' | 'more'
// A key of the last line: those with a hotkey the shell draws as the host's Buttons, the rest as text.
export type Key = { key: string; means: string; hotkey?: string }

// One row of the list, under the path of its group: its words, its status at the right edge, its notes, each a
// question (or why it could not be checked), whether it can only be changed, and its details.
export type Status = '' | 'Clear' | 'Review' | 'Yes'
export type RowView = { id: string; text: string; status: Status; notes: string[]; noStep: boolean; details: string[] }
// `checked` the holds a command checks, drawn under a heading line of their own after the group's other rows.
export type Group = { path: string; rows: RowView[]; checked: RowView[] }

// The step the readers will be asked for a claim, as the writer writes it: the one its examination kept for the
// item's own words, where there is one, else the item's own; an options proposal keeps its own, since the words
// picked are not the item's.
export const askedOf = (p: Proposal, x: Examined | null, i: number, it: Item): Step =>
  (p.kind !== 'options' ? x?.steps?.[String(i)] : undefined) ?? { lines: it.step, reversal: p.kind === 'options' ? null : it.reversal }

// Every claim of a proposal in the one order an examination numbers them: its items, then each part's own in turn.
export const numbered = (p: Proposal): { item: Item; n: number; part: string }[] => {
  const found = p.items.map((item, n) => ({ item, n, part: '' }))
  for (const part of p.split?.parts ?? []) part.items.forEach(item => found.push({ item, n: found.length, part: part.place }))
  return found
}

const BLOCKING = new Set(['unread', 'unmade', 'secret']) // marks of a claim the check could not check at all
// Marks that ask the person nothing they can answer: the check could only be weaker, or a word may lean on another
// row. Each is said under the row's details alone.
const ASIDE = new Set(['unreversed', 'alone', 'alone-unsettled'])
const isOn = (o: Open) => o.check === 'on'
// The check failed as a whole, with the check on: the examination said so, or the band's run of it could not run.
export const failedOf = (o: Open): string => (o.checking || !isOn(o) ? '' : o.checkFailed || shown(o.examined?.failed ?? ''))

// The notes of one claim, by its number: its one question, the session's own `ask` where it put one, else a
// reframe's old words as a question, else the check's first plain question; why it could not be checked, where the
// check is on and the maker made it no step; and every other remark, for the details alone.
type Notes = { question: string[]; why: string[]; others: string[]; noStep: boolean }
const claimNotes = (o: Open, n: number, it: Item): Notes => {
  const x = o.examined
  const marks = (x?.marks ?? []).filter(m => m.item === n)
  const noStep = isOn(o) && o.proposal.kind !== 'options' && !x?.steps?.[String(n)]
  const blocked = marks.filter(m => BLOCKING.has(m.kind)).map(m => shown(m.words))
  const asked = marks.filter(m => !BLOCKING.has(m.kind) && !ASIDE.has(m.kind)).map(m => shown(m.words))
  const aside = marks.filter(m => ASIDE.has(m.kind)).map(m => shown(m.words))
  const all = [...(it.ask ? [shown(it.ask)] : []), ...(it.old ? [`${LABELS.replaces}${shown(it.old)}${LABELS.replacesTail}`] : []), ...asked]
  const why = noStep ? (blocked.length ? blocked : [o.foreign ? LABELS.notOurs : LABELS.unchecked]) : []
  return { question: all.slice(0, 1), why, others: [...all.slice(1), ...aside], noStep }
}
const stepDetails = (o: Open, n: number, it: Item, others: string[]): string[] => {
  const step = askedOf(o.proposal, o.examined, n, it)
  return [
    step.lines.length ? `${LABELS.detailStep}${step.lines.map(shown).join(' ')}` : LABELS.detailNoStep,
    ...(step.reversal ? [`${LABELS.detailTurned}${step.reversal.lines.map(shown).join(' ')}`] : []),
    ...others.map(note => `${LABELS.note}${note}`),
  ]
}
const statusOf = (o: Open, id: string, notes: string[], judged: boolean): Status =>
  notes.length ? (o.answered.includes(id) ? 'Yes' : 'Review') : judged && isOn(o) && o.examined ? 'Clear' : ''

// The rows of the open proposal in their groups: for a crossing each part with its own claims and holds, each
// contract with its sides, then what must hold at the place split; else the items and holds alone. A crossing's
// claims above are no rows: each note of one goes under the first part row that narrows it, in a part that carries it
// where the check named one, its question there only where that row has none of its own.
export const groupsOf = (o: Open, base = ''): Group[] => {
  const p = o.proposal
  const every = numbered(p)
  if (p.kind === 'options') {
    return [{ path: '', checked: [], rows: (p.options ?? []).map((op, i) => ({
      id: `o${i}`, text: shown(op.cost ? `${op.words} · ${LABELS.costs} ${op.cost}` : op.words),
      status: o.pick === i ? 'Yes' : '', notes: [], noStep: false, details: [] }) as RowView) }]
  }
  const made = new Map<number, Notes>(every.map(({ item, n }) => [n, claimNotes(o, n, item)]))
  if (p.split) {
    p.items.forEach((above, n) => {
      const carry = o.examined?.above?.[String(n)]?.carry ?? []
      const narrowing = every.filter(e => e.part && e.item.narrows === above.words)
      const target = narrowing.find(e => carry.includes(e.part)) ?? narrowing[0]
      const held = made.get(n)
      if (!target || !held) return
      const into = made.get(target.n)!
      const question = into.question.length ? into.question : held.question
      const others = [...into.others, ...(into.question.length ? held.question : []), ...held.others]
      made.set(target.n, { question, why: [...into.why, ...held.why], others, noStep: into.noStep || held.noStep })
    })
  }
  const claimRow = (item: Item, n: number): RowView => {
    const { question, why, others, noStep } = made.get(n)!
    const id = `c${n}`
    const notes = [...question, ...why]
    return { id, text: shown(item.words), status: noStep ? 'Review' : statusOf(o, id, notes, true), notes, noStep, details: stepDetails(o, n, item, others) }
  }
  const holdRow = (h: Hold, id: string): RowView =>
    ({ id, text: shown(h.detail ? `${h.words} · ${h.detail}` : h.words), status: '', notes: [], noStep: false, details: [`${LABELS.detailCommand}${shown(h.detail)}`] })
  // a place's holds: those of paths among its rows, as before; those a command checks under their own heading
  const holdsOf = (holds: Hold[], id: (k: number) => string) => ({
    paths: holds.flatMap((h, k) => (h.byCommand ? [] : [holdRow(h, id(k))])),
    checked: holds.flatMap((h, k) => (h.byCommand ? [holdRow(h, id(k))] : [])),
  })
  if (!p.split) {
    const held = holdsOf(p.holds, k => `h${k}`)
    return [{ path: '', rows: [...p.items.map((it, n) => claimRow(it, n)), ...held.paths], checked: held.checked }]
  }
  const under = (place: string) => (p.place && place.startsWith(`${p.place}/`) ? place.slice(p.place.length + 1) : place)
  const groups: Group[] = p.split.parts.map((part, j) => {
    const held = holdsOf(part.holds, k => `p${j}h${k}`)
    return { path: `${base}${LABELS.down}${shown(under(part.place))}`,
      rows: [...every.filter(e => e.part === part.place).map(e => claimRow(e.item, e.n)), ...held.paths], checked: held.checked }
  })
  p.split.contracts.forEach((c, k) => {
    const n = every.length + k
    const id = `k${k}`
    const marks = (o.examined?.marks ?? []).filter(m => m.item === n).map(m => shown(m.words))
    const kept = o.examined?.contracts?.[String(k)]
    const sides = [c.provides, ...c.depends].map(under).map(shown)
    const named = sides.length > 1 ? `${sides.slice(0, -1).join(', ')} ${LABELS.and} ${sides.at(-1)}` : sides.join('')
    const all = [...marks, ...(c.command ? [] : [LABELS.noCheckYet]),
      ...(isOn(o) && o.examined && kept !== true && !marks.length ? [`${LABELS.contractUnsure[0]}${named}${LABELS.contractUnsure[1]}`] : [])]
    const notes = all.slice(0, 1)
    groups.push({
      path: `${base}${LABELS.down}${sides.join(LABELS.shared)}`, checked: [],
      rows: [{ id, text: shown(c.words), status: statusOf(o, id, notes, true), notes, noStep: false,
        details: [`${shown(c.id)}`, c.command ? `${LABELS.detailCommand}${shown(c.command)}` : LABELS.noCheckYet,
          ...all.slice(1).map(note => `${LABELS.note}${note}`)] }],
    })
  })
  if (p.holds.length) {
    const held = holdsOf(p.holds, k => `h${k}`)
    groups.push({ path: base || LABELS.down.trim(), rows: held.paths, checked: held.checked })
  }
  return groups
}
export const rowsOf = (o: Open): RowView[] => groupsOf(o).flatMap(g => [...g.rows, ...g.checked])
// A row as an answer is kept by: its words and its one question, so a yes stands where both stand unchanged.
export const answerKey = (r: RowView) => `${r.text}\n${r.notes[0] ?? ''}`
// The rows under review this proposal answers yes by what a proposal it took the place of answered.
export const carried = (o: Open): string[] =>
  rowsOf({ ...o, answered: [] }).filter(r => r.status === 'Review' && !r.noStep && o.kept.includes(answerKey(r))).map(r => r.id)

// The host's wrapper of a pasted text, as it puts a paste into the prompt it hands on: tags of the host's, no words
// of his. A line that holds nothing but such tags is the wrapper's alone.
const PASTE = /<\/?pasted_content(?:\s[^>]*)?>/g
const PASTE_ONLY = /^\s*(?:<\/?pasted_content(?:\s[^>]*)?>\s*)+$/
// His prompt as he typed it, line by line: the host's paste tags taken out, and every line that holds nothing but
// space; every word of the rest kept, each line made safe to draw.
export const saidLines = (x: string): string[] =>
  x.split(/\r\n|[\n\r\u0085\u2028\u2029]/).filter(l => !PASTE_ONLY.test(l)).map(l => l.replace(PASTE, '')).filter(l => l.trim() !== '').map(shown)

// The key of the line enter opens under the stop he chose.
export const INPUT = 'input'
// The stops the cursor moves between, in order: his sentence, each row with its notes as one, then OK; or, where the
// check failed as a whole, Check again alone. None while the check runs.
export const stopsOf = (o: Open): string[] => {
  if (o.checking) return []
  const said = saidLines(o.said).length ? ['said'] : []
  if (failedOf(o)) return [...said, 'retry']
  return [...said, ...rowsOf(o).map(r => r.id), 'ok']
}
export const toReview = (o: Open) => rowsOf(o).filter(r => r.status === 'Review')
// OK is offered once the check is done, nothing is left to review, and for options one is picked.
export const isOffered = (o: Open) =>
  !o.checking && !failedOf(o) && !o.writing && toReview(o).length === 0 && (o.proposal.kind !== 'options' || o.pick !== null)
// Where the cursor opens: on the first row under review, else on the first row.
export const firstCursor = (o: Open): string => {
  if (failedOf(o)) return 'retry'
  const rows = rowsOf(o)
  return (rows.find(r => r.status === 'Review') ?? rows[0])?.id ?? 'ok'
}

// The picker is never wider than this, at the left of its pane, so a row's status word stays next to its words.
export const MAX_WIDTH = 110
const counted = (k: number, [one, many]: readonly [string, string]) => `${k} ${k === 1 ? one : many}`
// A text in lines of at most `w` cells, and `later` cells after the first, broken at a space where one is, else where
// the line ends; nothing else of it changes, so his own words stay as typed.
const wrap = (x: string, w: number, later = w): string[] => {
  let width = Math.max(1, w)
  const out: string[] = []
  let rest = x
  while (rest.length > width) {
    const at = rest.lastIndexOf(' ', width)
    out.push(at > 0 ? rest.slice(0, at) : rest.slice(0, width))
    rest = at > 0 ? rest.slice(at + 1) : rest.slice(width)
    width = Math.max(1, later)
  }
  return [...out, rest]
}

// Where the cursor rests among the rows, as "row 5 of 12"; nothing while it is on his sentence or on OK.
const whereOf = (o: Open): string => {
  const rows = rowsOf(o)
  const at = rows.findIndex(r => r.id === o.cursor)
  return at < 0 ? '' : ` · ${LABELS.rows[0]} ${at + 1} ${LABELS.of} ${rows.length}`
}
// The header: the state, the rows counted, what is left for the person, which alone takes the accent, and where the
// cursor rests.
const headOf = (o: Open, running: string): Seg[] => {
  if (o.checking) return [{ text: running || `${LABELS.name} · ${LABELS.pick} · ${LABELS.checking}` }]
  if (failedOf(o)) return [{ text: `${LABELS.name} · ${LABELS.pick} · ${LABELS.checkFailed}` }]
  const rows = rowsOf(o)
  const where: Seg[] = whereOf(o) ? [{ text: whereOf(o) }] : []
  if (o.proposal.kind === 'options') {
    const head = `${LABELS.name} · ${LABELS.pick} · ${counted(rows.length, LABELS.options)} · `
    return o.pick === null ? [{ text: head }, { text: LABELS.pickOne, tone: 'accent' }, ...where] : [{ text: `${head}${LABELS.picked}` }, ...where]
  }
  const head = `${LABELS.name} · ${LABELS.pick} · ${isOn(o) ? LABELS.checked : LABELS.checkOff} · ${counted(rows.length, LABELS.rows)}`
  const left = rows.filter(r => r.status === 'Review').length
  if (left) return [{ text: `${head} · ` }, { text: `${left} ${LABELS.toReview}`, tone: 'accent' }, ...where]
  return [{ text: rows.some(r => r.status === 'Yes' && r.notes.length) ? `${head} · ${LABELS.allAnswered}` : head }, ...where]
}

// The keys that apply at the cursor now, as the pane holding the keyboard takes them. `paged` where the list is taller
// than the pane, `cut` where his sentence shows only its first line.
const keysAt = (o: Open, paged: boolean, cut: boolean): Key[] => {
  const close: Key[] = [{ key: LABELS.keys.esc, means: LABELS.keys.close }]
  const page: Key[] = paged ? [{ key: LABELS.keys.page, means: LABELS.keys.pageMeans }] : []
  const tail: Key[] = [{ key: LABELS.keys.tab, means: LABELS.keys.next }, ...page, { key: LABELS.keys.help, means: LABELS.keys.helpMeans, hotkey: LABELS.keys.help }, ...close]
  if (o.writing || o.checking) return close
  if (failedOf(o)) return [{ key: 'r', means: LABELS.keys.r, hotkey: 'r' }, ...close]
  const offered = isOffered(o)
  const build: Key[] = offered ? [{ key: 'o', means: LABELS.keys.build, hotkey: 'o' }] : []
  if (o.cursor === 'ok') return [...(offered ? [{ key: LABELS.keys.enter, means: LABELS.keys.build }] : []), ...tail]
  const enter = (means: string): Key => ({ key: LABELS.keys.enter, means })
  if (o.cursor === 'said') return [...build, enter(LABELS.keys.changeAll), ...(cut || o.details === 'said' ? [{ key: 'd', means: LABELS.keys.whole, hotkey: 'd' }] : []), ...tail]
  const row = rowsOf(o).find(r => r.id === o.cursor)
  const review = !!row && row.status === 'Review' && !row.noStep
  const yes: Key[] = review || (row && o.proposal.kind === 'options' && row.status !== 'Yes')
    ? [{ key: 'y', means: LABELS.keys.y, hotkey: 'y' }] : []
  // enter opens the row's line: only a row under review can be confirmed there, by an empty line, so only it says so
  const change = enter(review ? LABELS.keys.choose : LABELS.keys.change)
  const details: Key[] = row?.details.length ? [{ key: 'd', means: LABELS.keys.d, hotkey: 'd' }] : []
  return [...yes, ...build, change, ...details, ...tail]
}
const MOVES = new Set<string>([LABELS.keys.tab, LABELS.keys.page, LABELS.keys.help, LABELS.keys.esc])
// The last line, in every state: while the check runs, to wait; with his change's line open, what enter and esc do
// there; with the keyboard, the keys that apply now; without it, what a line typed in the host's prompt is and how to
// give the pane the keys, with the keys they will be. `drafted` where the host's prompt holds text.
export type Foot = { lead: string; keys: Key[] }
const footOf = (o: Open, drafted: boolean, focused: boolean, paged: boolean, cut: boolean): Foot => {
  if (o.checking) return { lead: LABELS.pleaseWait, keys: [] }
  if (o.changing) { // in the line every letter is his words; empty enter still confirms or closes
    const means = o.typed.trim() ? LABELS.keys.send : LABELS.keys.confirm
    return { lead: '', keys: [{ key: LABELS.keys.enter, means }, { key: LABELS.keys.esc, means: LABELS.keys.back }] }
  }
  if (focused) return { lead: '', keys: keysAt(o, paged, cut) }
  const hint = drafted ? LABELS.sendsAll : LABELS.hintAll
  if (o.writing) return { lead: hint, keys: [] }
  return { lead: `${hint} · ${LABELS.toAnswer}`, keys: keysAt(o, paged, cut).filter(k => !MOVES.has(k.key)) }
}
// The last line as text: its lead, then each key and its meaning joined by a middle dot.
export const footerText = (f: Foot) => {
  const keys = f.keys.map(k => `${k.key} ${k.means}`).join(' · ')
  return f.lead && keys ? `${f.lead} ${keys}` : f.lead || keys
}

// The heading of the list: what will be built, in how many parts.
const headingOf = (p: Proposal): string => {
  if (p.kind === 'options') return LABELS.pickHead
  const k = p.split?.parts.length ?? 0
  if (!k) return LABELS.build
  return `${LABELS.buildIn} ${LABELS.numbers[k] ?? String(k)} ${k === 1 ? LABELS.parts[0] : LABELS.parts[1]}`
}
// His sentence in one line: its first line, cut to `room` where it does not fit, then how many lines more.
const oneLine = (all: string[], room: number): string => {
  const more = all.length - 1
  const tail = more ? `${LABELS.cutLead}${more} ${more === 1 ? LABELS.lines[0] : LABELS.lines[1]}` : ''
  const first = all[0] ?? ''
  if (first.length + (tail ? tail.length + 1 : 0) <= room) return tail ? `${first} ${tail}` : first
  const end = tail || LABELS.cut
  return `${first.slice(0, Math.max(1, room - end.length)).trimEnd()}${end}`
}

// A line of the screen: its pieces, the stop it belongs to, and whether it is the cursor's block. An `input` line is
// where the line he types his change in is drawn, under the stop he chose.
export type ScreenLine = { kind: LineKind; segs: Seg[]; stop?: string; lit?: true }
// `head` the lines the header takes, which the window always keeps; `foot` and `help` the last line; `stops` the
// stops in order, each drawn as one element of the host's; `cursor` the stop under the cursor, whose lines the window
// keeps wholly in view; `focused` whether the pane holds the keyboard; `width` the picker's. An `input` line is part of
// that stop's block, and the host draws its one text field there.
export type Screen = {
  lines: ScreenLine[]; foot: Foot; help: string[]; stops: string[]; head: number; cursor: string; focused: boolean; width: number
}

// The screen of the open proposal, at most MAX_WIDTH cells wide, in the folder `project`; `running` the line of what
// runs, while the check runs; `alert` a failure the person is to see whatever else is in view, under the header;
// `drafted` where the host's prompt holds text; `focused` where the pane holds the keyboard; `paged` where the whole is
// taller than the pane.
export const screen = (o: Open, width: number, project: string, running = '', alert = '', drafted = false, focused = false, paged = false): Screen => {
  const p = o.proposal
  const w = Math.max(30, Math.min(width, MAX_WIDTH))
  const left = w - 9 // the list's left column: a margin, then the cells up to the rule; then `│ ` and six for the status
  const base = shown(project) + (p.place ? `${LABELS.down}${shown(p.place)}` : '')
  const lines: ScreenLine[] = [{ kind: 'head', segs: [{ text: ' ' }, ...headOf(o, running)] }]
  for (const piece of alert ? wrap(shown(alert), w - 2) : []) lines.push({ kind: 'unapproved', segs: [{ text: ` ${piece}` }] })
  const head = lines.length
  if (base) lines.push({ kind: 'path', segs: [{ text: ` ${base}` }] })
  const lit = (stop: string) => !o.checking && o.cursor === stop
  const gutter = (stop: string): Seg[] => (lit(stop) ? [{ text: LABELS.cursor, tone: 'accent', cursor: true }, { text: ' ' }] : [{ text: '  ' }])
  const on = (stop: string) => (o.checking ? {} : lit(stop) ? { stop, lit: true as const } : { stop })
  // the line right under the stop he chose: dim while empty; his words wrap inside the table, never cut, under where
  // they begin
  const input = (stop: string, cell: (segs: Seg[]) => Seg[] = segs => [{ text: ' ' }, ...segs], room = w - 2) => {
    if (o.changing !== stop) return
    const typed = shown(o.typed)
    const empty = !typed.trim()
    for (const piece of wrap(empty ? LABELS.inputHint : typed, room - 5)) {
      lines.push({ kind: 'input', ...on(stop), segs: cell([{ text: '    ' }, { text: piece, ...(empty ? { tone: 'dim' as const } : {}) }]) })
    }
  }
  // his sentence: its first line, cut to the width, and how many more; whole under d, or while he types his change
  const all = saidLines(o.said)
  const room = w - LABELS.youSaid.length - 3
  const whole = o.details === 'said' || o.changing === 'said'
  const said = whole ? all.flatMap(line => wrap(line, room)) : all.length ? [oneLine(all, room)] : []
  const cut = !whole && said.length > 0 && said[0] !== all[0]
  const indent = ' '.repeat(LABELS.youSaid.length + 3)
  said.forEach((piece, i) => lines.push({ kind: 'said', ...on('said'),
    segs: i ? [{ text: indent + piece }] : [{ text: ' ' }, ...gutter('said'), { text: LABELS.youSaid + piece }] }))
  input('said')
  if (p.reason) lines.push({ kind: 'reason', segs: [{ text: ` ${LABELS.again}${shown(p.reason.words)}` }] })
  const failed = failedOf(o)
  if (!o.checking && failed) {
    for (const piece of wrap(failed, w - 2)) lines.push({ kind: 'fail', segs: [{ text: ` ${piece}` }] })
    lines.push({ kind: 'retry', segs: [{ text: ' ' }, ...gutter('retry'), { text: LABELS.retry }], ...on('retry') })
  } else if (!o.checking) {
    // one line of the table: a margin, the cells padded to the rule, the rule, and the status where there is one
    const cell = (segs: Seg[], status = '', tone?: Tone): Seg[] => {
      const used = segs.reduce((n, x) => n + x.text.length, 0)
      return [{ text: ' ' }, ...segs, { text: ' '.repeat(Math.max(0, left - used)) }, { text: status ? '│ ' : '│' },
        ...(status ? [{ text: status, ...(tone ? { tone } : {}) }] : [])]
    }
    // a text under its lead, wrapped inside the left column with a space before the rule, each line after the first
    // under the lead's width and `more` cells further in
    const wrapped = (lead: Seg[], text: string, tone?: Tone, more = 0): Seg[][] => {
      const width = lead.reduce((n, x) => n + x.text.length, 0)
      return wrap(text, left - width - 1, left - width - more - 1)
        .map((piece, i) => [...(i ? [{ text: ' '.repeat(width + more) }] : lead), { text: piece, ...(tone ? { tone } : {}) }])
    }
    lines.push({ kind: 'table', segs: cell([{ text: headingOf(p) }], LABELS.check) })
    lines.push({ kind: 'table', segs: [{ text: ` ${'─'.repeat(left)}┼${'─'.repeat(7)}`, tone: 'dim' }] })
    for (const g of groupsOf(o, base)) {
      if (g.path) for (const piece of wrapped([], g.path)) lines.push({ kind: 'group', segs: cell(piece) })
      for (const r of [...g.rows, ...g.checked]) {
        if (r === g.checked[0]) lines.push({ kind: 'group', segs: cell([{ text: LABELS.byCommand }]) })
        const review = r.status === 'Review'
        const word = r.status === 'Clear' ? LABELS.clear : r.status === 'Review' ? LABELS.review : r.status === 'Yes' ? LABELS.yes : ''
        const tone = review ? 'accent' : r.status === 'Clear' ? 'dim' : undefined
        wrapped(gutter(r.id), r.text, undefined, 2).forEach((piece, i) =>
          lines.push({ kind: 'row', ...on(r.id), segs: i ? cell(piece) : cell(piece, word, tone) }))
        // its one question, whole, on lines of its own; why it could not be checked after it
        for (const note of r.notes) {
          for (const piece of wrapped([{ text: `    ${LABELS.note}` }], note, r.status === 'Review' ? 'accent' : undefined)) {
            lines.push({ kind: 'note', ...on(r.id), segs: cell(piece) })
          }
        }
        if (o.details === r.id) {
          for (const d of r.details) {
            for (const piece of wrap(d, left - 5)) lines.push({ kind: 'detail', ...on(r.id), segs: cell([{ text: `    ${piece}`, tone: 'dim' }]) })
          }
        }
        input(r.id, cell, left)
      }
    }
    lines.push({ kind: 'ok', segs: [{ text: ' ' }, ...gutter('ok'), { text: o.writing ? LABELS.writing : LABELS.ok }], ...on('ok') })
    if (o.failed) for (const piece of wrap(`${LABELS.writerFailed} ${shown(o.failed)}`, w - 2)) lines.push({ kind: 'writer', segs: [{ text: ` ${piece}` }] })
  }
  lines.push({ kind: 'blank', segs: [{ text: '' }] })
  // every row but the cursor's is a shade quieter
  for (const line of lines) if ((line.kind === 'row' || line.kind === 'note') && !line.lit) line.segs = line.segs.map(x => (x.tone ? x : { ...x, tone: 'dim' }))
  return {
    lines, foot: footOf(o, drafted, focused, paged, cut), help: focused && o.help && !o.changing ? [...LABELS.help] : [], stops: stopsOf(o), head,
    cursor: o.checking ? '' : o.cursor, focused, width: w,
  }
}
// The help list, each line wrapped to the pane with every line beginning under the list's first word.
export const helpLines = (sc: Screen): string[] => sc.help.flatMap(line => wrap(line, sc.width - 1).map(piece => ` ${piece}`))
// The close line under the help list: h is the host's Button, esc the host's own close.
const helpClose = () => ` ${LABELS.keys.help} ${LABELS.keys.listClose} · ${LABELS.keys.esc} ${LABELS.keys.listClose}`
// The last lines as the pane draws them: the help list and its close line, or the keys that apply now.
export const footLines = (sc: Screen): string[] => (sc.help.length ? [...helpLines(sc), helpClose()] : [` ${footerText(sc.foot)}`])
// The last line in the pieces the pane lays out a cell in, each going whole to the next row where the row has no room
// for it: its lead, then each key with the middle dot after it but the last, a hotkey as the host draws it,
// `y: yes, fine`.
export const footPieces = (sc: Screen): string[] => {
  const f = sc.foot
  const keys = f.keys.map((k, i) => `${k.hotkey && sc.focused ? `${k.hotkey}: ${k.means}` : `${k.key} ${k.means}`}${i < f.keys.length - 1 ? ' · ' : ''}`)
  return [...(f.lead ? [`${f.lead}${keys.length ? ' ' : ''}`] : []), ...keys]
}
// The rows a text takes at the picker's width.
const heightAt = (x: string, width: number) => Math.max(1, Math.ceil(x.length / Math.max(1, width)))
// The rows the last line takes: the help list a line each, wrapped; else its pieces laid out in rows, a piece wider
// than a row taking rows of its own.
const footRows = (sc: Screen) => {
  if (sc.help.length) return footLines(sc).reduce((n, l) => n + heightAt(l, sc.width), 0)
  const width = sc.width - 1
  let rows = 0
  let used = width
  for (const x of footPieces(sc)) {
    if (used + x.length <= width) used += x.length
    else {
      rows += heightAt(x, width)
      used = x.length > width ? width : x.length
    }
  }
  return Math.max(1, rows)
}
// The rows the header takes, its lines wrapped where they are wider than the picker.
const headRows = (sc: Screen) => sc.lines.slice(0, sc.head).reduce((n, l) => n + heightAt(l.segs.map(x => x.text).join(''), sc.width), 0)
// The rows the whole screen takes: what the pane asks for while seated inline.
export const heightOf = (sc: Screen) => sc.lines.length - sc.head + headRows(sc) + footRows(sc)
// The screen as the pane draws it in `rows` of its body: with the page keys on the last line where the whole is
// taller than that.
export const paneScreen = (o: Open, width: number, rows: number, project: string, running = '', alert = '', drafted = false, focused = false): Screen => {
  const sc = screen(o, width, project, running, alert, drafted, focused)
  return heightOf(sc) > rows ? screen(o, width, project, running, alert, drafted, focused, true) : sc
}

// What the pane draws of a screen taller than its body: the header always, then as many lines of the rest as fit,
// the window moved from `top` only as far as keeps the cursor's block (its row, its question, its details and his
// change's line) wholly in view, or its top where it is taller than the window; then, in place of the blank line, what
// is out of view above and below, counted; then the last line. Gives the lines and the window's top.
export const fit = (sc: Screen, rows: number, top: number): { lines: ScreenLine[]; top: number } => {
  const tail = sc.lines.at(-1)?.kind === 'blank' ? 1 : 0
  const head = sc.lines.slice(0, sc.head)
  const body = sc.lines.slice(sc.head, sc.lines.length - tail)
  const room = rows - headRows(sc) - 1 - footRows(sc)
  if (!(body.length > room)) return { lines: sc.lines, top: 0 }
  const size = Math.max(1, room)
  const most = body.length - size
  const block = body.flatMap((line, i) => (sc.cursor && line.stop === sc.cursor ? [i] : []))
  let at = Math.min(Math.max(0, top), most)
  if (block.length) {
    const first = block[0]!
    const last = block[block.length - 1]!
    if (sc.cursor === sc.stops[0] && last < size) at = 0 // on the first stop, all that stands above it
    else if (last - first + 1 > size || first < at) at = first
    else if (last >= at + size) at = last - size + 1
  }
  at = Math.max(0, Math.min(at, most))
  const below = body.length - at - size
  const told = [...(at ? [`${LABELS.above} ${at} ${LABELS.more}`] : []), ...(below ? [`${LABELS.below} ${below} ${LABELS.more}`] : [])]
  return { lines: [...head, ...body.slice(at, at + size), { kind: 'more', segs: [{ text: ` ${told.join(' · ')}`, tone: 'dim' }] }], top: at }
}
// Where page down or page up takes the cursor: to the furthest stop whose first line is within the window's room for
// the list, at least the next stop, and no further than the first or the last; and how many lines it moved.
export const pageTo = (sc: Screen, rows: number, by: 1 | -1): { stop: string; lines: number } => {
  const room = Math.max(1, rows - headRows(sc) - 1 - footRows(sc))
  const firsts = sc.stops.map(stop => sc.lines.findIndex(l => l.stop === stop))
  const at = sc.stops.indexOf(sc.cursor)
  if (at < 0) return { stop: sc.stops[0] ?? '', lines: 0 }
  const from = firsts[at]!
  const reach = sc.stops.map((stop, i) => ({ stop, i, line: firsts[i]! }))
    .filter(x => (by > 0 ? x.i > at && x.line - from <= room : x.i < at && from - x.line <= room))
  const to = (by > 0 ? reach.at(-1) : reach[0]) ?? { stop: sc.stops[Math.max(0, Math.min(sc.stops.length - 1, at + by))]!, line: firsts[Math.max(0, Math.min(sc.stops.length - 1, at + by))]! }
  return { stop: to.stop, lines: to.line - from }
}

// The screen with every tone and background taken away: what a person who sees no colour reads.
export const plain = (s: Screen): string[] => [...s.lines.map(l => l.segs.map(x => x.text).join('')), ...footLines(s)]
