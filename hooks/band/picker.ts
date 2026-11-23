// The picker as plain data: (state, event) -> (state, effects). One proposal is open at a time; one
// stored while it is open waits its turn and never takes its place, unless it is a re-proposal for the
// same place and kind, or the session's answer to the person's change, which takes the older one's place. With the
// check on, a proposal opens checking: the band runs the examination and the rows show only once it is done. The
// picker closes three ways only: OK, a change of the person's, and esc, which leaves the proposal waiting with its
// answers until /frame-loop. A change closes it only while the session answers: after its turn the picker is open
// again, on the new proposal or on the same one. Effects are data the shell carries out: check a proposal, run the
// writer, read a waiting proposal back, submit the approval's sentence, bring the pane's ring to the cursor or its
// open line, or tell the session one proposal took another's place. Enter on a row, or on their sentence, opens one
// line under it with the keyboard in it.
import type { Examined, Open, Picker, Proposal } from '../../types'
import { approveArgs } from './frameloop'
import { LABELS } from './labels'
import { answerKey, carried, failedOf, firstCursor, INPUT, isOffered, rowsOf, stopsOf } from './view'

type Shown = { id: string; proposal: Proposal; examined: Examined | null; foreign?: boolean; shown: string; check: 'on' | 'off' }
export type Event =
  | ({ type: 'proposed'; said?: string; at?: number } & Shown) // stored, read back
  | { type: 'lost'; id: string } // a waiting proposal that could not be read back
  | ({ type: 'reshown'; at?: number } & Shown) // changed under it
  | ({ type: 'checked'; failed: string } & Shown) // the band's own check ended: '' where it ran, else why it could not
  | { type: 'move'; by: 1 | -1 } // the cursor on to the next stop, or back, the ring with it
  | { type: 'go'; stop: string } // the cursor to a stop a page away, the ring with it
  | { type: 'focus'; stop: string } // the ring is on a stop of its own
  | { type: 'yes' } // y: the row under the cursor answered yes
  | { type: 'press'; stop?: string } // enter on a row or their sentence: its line opens with the keyboard in it
  | { type: 'back' } // esc in the line, or the ring moved off it: back to the stop, nothing sent
  | { type: 'typed'; text: string } // their words in the line as they type them, as the host tells each change
  | { type: 'submit'; text: string } // enter in the line: empty confirms or closes; words are their change
  | { type: 'changed'; text: string } // a line they sent at the host's prompt while the picker was open: their change
  | { type: 'reopen' } // the session's turn after their change ended with no new proposal, or their line never entered
  | { type: 'withdrawn' } // the session withdrew it, at their word
  | { type: 'turned' } // a main turn ended
  | { type: 'details' }
  | { type: 'help' }
  | { type: 'approve' } // o, or enter on OK
  | { type: 'retry'; at?: number }
  | { type: 'aside' } // the pane gone: closed for now, the proposal waiting with its answers
  | { type: 'closed' } // the person's close of the pane, by esc, its mark or its key
  | { type: 'resume' } // /frame-loop: the picker again
  | { type: 'written'; id: string; said: string; closing: string }
  | { type: 'unwritten'; id: string; text: string }
  | { type: 'prompted' } // the person sent a prompt of their own with no picker open
  | { type: 'told' } // the session was told what the picker kept for it

export type Effect =
  | { kind: 'examine'; id: string }
  | { kind: 'approve'; id: string; args: string[] }
  | { kind: 'load'; id: string }
  | { kind: 'submit'; text: string }
  | { kind: 'focus'; key?: string } // the pane's ring onto the cursor's stop, or onto the element keyed `key`
  | { kind: 'regain' } // the pane opened again over its close, so it takes the keys back
  | { kind: 'replaced'; id: string; by: string }

export const EMPTY: Picker = { open: null, waiting: [], told: [], ever: false, closing: '' }
// The key of the line under the stop they chose.
export { INPUT }

type Step = { state: Picker; effects: Effect[] }

// A closed proposal, as the session is told at its next prompt.
export const closedTold = (id: string) => `${LABELS.proposal} ${id} ${LABELS.closedUnwritten}`
// The one a re-proposal took the place of, as the tool's answer and the session's next prompt say it.
export const replacedTold = (id: string) => `${LABELS.replaced} ${id}${LABELS.replacedTail}`

// The open one is done with: the next that waits is read back; one closed with nothing written is told.
const after = (s: Picker, effects: Effect[], unwritten: boolean): Step => {
  const next = s.waiting[0]
  const told = unwritten && s.open ? [...s.told, closedTold(s.open.id)] : s.told
  return { state: { ...s, open: null, told }, effects: next ? [...effects, { kind: 'load', id: next.id }] : effects }
}
// A re-proposal is known by its kind and its place: it takes the place of the older one.
const same = (a: { kind: string; place: string }, b: { kind: string; place: string }) => a.kind === b.kind && a.place === b.place
// With the check on, a proposal is checked before its rows are shown: where the tool's own examination of it is not
// there yet, or one is there that the tool did not make.
const owed = (e: Shown) => e.check === 'on' && (e.examined === null || e.foreign === true)
const opened = (e: Extract<Event, { type: 'proposed' }>, kept: string[] = []): Open => {
  const o: Open = {
    id: e.id, proposal: e.proposal, examined: e.examined, foreign: e.foreign === true, shown: e.shown, check: e.check,
    checking: owed(e), began: e.at ?? 0, checkFailed: '', said: e.said ?? '', cursor: '', answered: [], kept, changing: '',
    typed: '', changed: '', details: '', help: false, aside: false, pick: null, writing: false, failed: '',
  }
  const answered = o.checking ? [] : carried(o)
  return { ...o, answered, cursor: firstCursor({ ...o, answered }) }
}
// What a proposal that takes another's place keeps of it: each row answered yes, by its words and its question.
const keptOf = (o: Open): string[] => [...o.kept, ...rowsOf(o).filter(r => r.status === 'Yes' && o.answered.includes(r.id)).map(answerKey)]
const checkIf = (o: Open): Effect[] => (o.checking ? [{ kind: 'examine', id: o.id }] : [])

// The line closed, nothing sent: the cursor back on the stop it opened under.
const shut = (o: Open): Partial<Open> => ({ changing: '', typed: '', cursor: o.changing || o.cursor })

export const step = (s: Picker, e: Event): Step => {
  const same_: Step = { state: s, effects: [] }
  const o = s.open
  if (e.type === 'proposed') {
    if (o?.id === e.id || (o && s.waiting.some(w => w.id === e.id))) return same_
    if (o && !o.writing && (o.changed || same(o.proposal, e.proposal))) {
      // a re-proposal for the same place and kind, or the session's answer to their change, takes the open one's place,
      // which is dropped unwritten; a row whose words and question stand unchanged keeps their yes
      const next = opened({ ...e, said: e.said || o.said }, keptOf(o))
      const ring: Effect[] = next.checking ? [] : [{ kind: 'focus' }]
      return { state: { ...s, open: next, ever: true, closing: '' }, effects: [{ kind: 'replaced', id: o.id, by: e.id }, ...checkIf(next), ...ring] }
    }
    const waited = s.waiting.find(w => same(w, e.proposal))
    const entry = { id: e.id, kind: e.proposal.kind, place: e.proposal.place, said: e.said ?? '' }
    if (o && waited) {
      const waiting = s.waiting.map(w => (w === waited ? entry : w))
      return { state: { ...s, waiting }, effects: [{ kind: 'replaced', id: waited.id, by: e.id }] }
    }
    if (o) return { state: { ...s, waiting: [...s.waiting, entry] }, effects: [] }
    const said = e.said || s.waiting.find(w => w.id === e.id)?.said || ''
    const next = opened({ ...e, said })
    return { state: { ...s, open: next, waiting: s.waiting.filter(w => w.id !== e.id), ever: true, closing: '' }, effects: checkIf(next) }
  }
  if (e.type === 'told') return { state: { ...s, told: [] }, effects: [] }
  if (e.type === 'prompted') return { state: { ...s, closing: '' }, effects: [] }
  if (e.type === 'turned') return { state: { ...s, closing: '', open: o && (o.changed ? { ...o, changed: '' } : o) }, effects: [] }
  if (e.type === 'lost') {
    const left = { ...s, waiting: s.waiting.filter(w => w.id !== e.id) }
    return o ? { state: left, effects: [] } : after(left, [], false)
  }
  if (!o) return same_
  const set = (change: Partial<Open>, effects: Effect[] = []): Step => ({ state: { ...s, open: { ...o, ...change } }, effects })
  const cursorIn = (x: Open, at: string) => (stopsOf(x).includes(at) ? at : firstCursor(x))
  switch (e.type) {
    case 'reshown': {
      if (e.id !== o.id) return same_
      const changed = e.shown.split(':')[0] !== o.shown.split(':')[0] // the proposal itself, not only its examination
      const next: Open = { ...o, proposal: e.proposal, examined: e.examined, foreign: e.foreign === true, shown: e.shown,
        check: e.check, checking: e.check === 'off' ? false : o.checking }
      if (e.check === 'on' && (changed || (owed(e) && !o.checking))) { // the proposal changed, or the switch came on
        const again = { ...next, checking: true, began: e.at ?? o.began, checkFailed: '', answered: [], changing: '', typed: '', details: '' }
        return { state: { ...s, open: again }, effects: [{ kind: 'examine', id: o.id }] }
      }
      const fresh = e.shown !== o.shown ? { ...next, answered: [] } : next
      const kept = stopsOf(fresh).includes(o.changing) ? fresh : { ...fresh, changing: '', typed: '' }
      return set({ ...kept, cursor: o.checking ? o.cursor : cursorIn(kept, o.cursor) })
    }
    case 'checked': {
      if (e.id !== o.id) return same_
      const done: Open = { ...o, proposal: e.proposal, examined: e.examined, foreign: e.foreign === true, shown: e.shown, check: e.check,
        checking: false, checkFailed: e.failed, answered: [] }
      const answered = carried(done)
      return set({ ...done, answered, cursor: firstCursor({ ...done, answered }) }, o.changing ? [] : [{ kind: 'focus' }])
    }
    case 'written':
      if (e.id !== o.id) return same_
      { // the next that waits opens first, so the sentence submitted carries the picker as it then stands
        const done = after({ ...s, closing: e.closing }, [], false)
        return { state: done.state, effects: [...done.effects, { kind: 'submit', text: e.said }] }
      }
    case 'unwritten':
      return e.id === o.id ? set({ writing: false, failed: e.text }) : same_
    case 'aside':
      return set({ aside: true, changing: '', typed: '' })
    case 'closed': // esc backs out one thing: the line, the details, the key list, then the pane itself
      // esc is the host's close, and it takes the keys with it: the pane the band keeps open takes them back
      if (o.help) return set({ help: false }, [{ kind: 'regain' }])
      if (o.details) return set({ details: '' }, [{ kind: 'regain' }])
      return o.changing ? set(shut(o), [{ kind: 'regain' }]) : o.aside || o.changed ? same_ : set({ aside: true })
    case 'resume':
      return set({ aside: false }, [{ kind: 'focus' }])
    case 'back':
      return o.changing ? set(shut(o), [{ kind: 'focus' }]) : same_
    case 'typed':
      return o.changing ? set({ typed: e.text }) : same_
    case 'submit':
      if (!o.changing) return same_
      if (e.text.trim()) return set({ changed: e.text, changing: '', typed: '', help: false })
      { // an empty line confirms a row under review as y does; elsewhere it closes, nothing sent
        const row = rowsOf(o).find(r => r.id === o.changing)
        if (row?.status === 'Review') return step(s, { type: 'yes' })
        return set(shut(o), [{ kind: 'focus' }])
      }
    case 'changed': // their change, to the row they chose or to the whole: closed while the session answers it
      return o.aside || o.writing ? same_ : set({ changed: e.text, changing: '', typed: '', help: false })
    case 'reopen':
      return o.changed ? set({ changed: '' }) : same_
    case 'withdrawn':
      return o.changed ? after(s, [], true) : same_
  }
  if (o.writing || o.checking || o.changed) return same_ // nothing changes under the writer, the check, or their change
  const stops = stopsOf(o)
  const rows = rowsOf(o)
  const row = rows.find(r => r.id === o.cursor)
  const ring: Effect[] = [{ kind: 'focus' }]
  switch (e.type) {
    case 'move': { // round again at either end, so no move takes the keyboard out of the picker
      const at = Math.max(0, stops.indexOf(o.cursor))
      return set({ cursor: stops[(at + e.by + stops.length) % stops.length] ?? o.cursor, changing: '', typed: '' }, ring)
    }
    case 'go':
      return stops.includes(e.stop) ? set({ cursor: e.stop, changing: '', typed: '' }, ring) : same_
    case 'focus': // the ring moved to a stop of its own; off the line, it closes, nothing sent
      return stops.includes(e.stop) ? set({ cursor: e.stop, changing: '', typed: '' }) : same_
    case 'yes': {
      if (!row) return same_
      if (o.proposal.kind === 'options') return set({ pick: Number(row.id.slice(1)), cursor: 'ok', changing: '', typed: '' }, ring)
      if (row.status !== 'Review' || row.noStep) return same_ // a row the check could not check can only be changed
      const answered = { ...o, answered: [...o.answered, row.id], changing: '', typed: '' }
      const later = stopsOf(answered).slice(stopsOf(answered).indexOf(row.id) + 1)
      const next = rowsOf(answered).find(r => r.status === 'Review' && later.includes(r.id))
      return set({ answered: answered.answered, changing: '', typed: '', cursor: next?.id ?? 'ok', details: '' }, ring)
    }
    case 'press': { // on a row or their sentence: its line opens under it, with the keyboard in it
      const at = e.stop && stops.includes(e.stop) ? e.stop : o.cursor
      if (at === 'ok') return isOffered(o) ? step(s, { type: 'approve' }) : same_
      if (at === 'retry') return step(s, { type: 'retry' })
      if (at !== 'said' && !rows.some(r => r.id === at)) return same_
      return set({ cursor: at, changing: at, typed: '', help: false }, [{ kind: 'focus', key: INPUT }])
    }
    case 'details': // a row's details, or their sentence whole
      return row || o.cursor === 'said' ? set({ details: o.details === o.cursor ? '' : o.cursor }, ring) : same_
    case 'help':
      return set({ help: !o.help }, ring)
    case 'approve':
      return isOffered(o) ? { state: { ...s, open: { ...o, writing: true, failed: '' } }, effects: [{ kind: 'approve', id: o.id, args: approveArgs(o) }] } : same_
    case 'retry':
      return failedOf(o) ? set({ checking: true, began: e.at ?? o.began, checkFailed: '' }, [{ kind: 'examine', id: o.id }]) : same_
  }
  return same_
}

// The picker as it stands, in one line: the proposal it holds, whether it is checked now or set aside, and those
// waiting behind it.
export const pickerLine = (s: Picker): string => {
  if (!s.open) return LABELS.pickerEmpty
  const behind = s.waiting.length ? `; ${LABELS.pickerWaiting} ${s.waiting.map(w => w.id).join(', ')}` : ''
  const how = s.open.changed ? `, ${LABELS.pickerChanged}` : s.open.checking ? `, ${LABELS.pickerChecking}` : s.open.aside ? `, ${LABELS.pickerAside}` : ''
  return `${LABELS.pickerHolds} ${s.open.id}${how}${behind}`
}
// The proposals the picker holds, open or waiting: none of them is approved.
export const held = (s: Picker): string[] => [...(s.open ? [s.open.id] : []), ...s.waiting.map(w => w.id)]
// What the session is told at its next prompt: each proposal closed with nothing written or dropped since, and how
// the picker stands; while it holds one, that nothing of it is approved, what to build toward it (nothing), and
// what a message of the person's that answers it means. Nothing where this session's picker never held a proposal.
export const pickerTold = (s: Picker): string[] =>
  s.ever ? [...s.told, `${LABELS.pickerNow} ${pickerLine(s)}.`, ...(held(s).length ? [LABELS.unapprovedTold] : [])] : []
// What the session is told beside their change: to the row they chose in the pane or to the whole proposal, and what to do
// with it. A line they send at the host's prompt is a change to the whole, `whole`.
export const changeTold = (o: Open, whole = false): string[] => {
  const row = whole ? undefined : rowsOf(o).find(r => r.id === o.changing)
  return [row ? `${LABELS.changeRow} ${o.id}: “${row.text}”.` : `${LABELS.changeWhole} ${o.id}.`, LABELS.changeTold]
}
