// Every path of the picker, as plain data: no host.
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { LABELS } from '../../hooks/band/labels'
import { changeTold, closedTold, EMPTY, held, INPUT, pickerLine, pickerTold, replacedTold, step } from '../../hooks/band/picker'
import type { Event } from '../../hooks/band/picker'
import { plain, rowsOf, screen, stopsOf } from '../../hooks/band/view'
import type { Picker } from '../../types'
import { FAILED, FRAME_CHECKED, NOTES_CHECKED, NOTES_FRAME, NOTES_SPLIT, OPTIONS_FILE, proposed, read, run, SPLIT_FILE } from './fixtures'

const checked = (raw: { id: string }, examined = FRAME_CHECKED): Event =>
  ({ type: 'checked', id: raw.id, failed: '', proposal: read(raw), examined, shown: `shown-${raw.id}:y`, check: 'on' })
// The notes frame with the session's own question on its second row too: two rows under review, c1 and c2.
const ASKED = { ...NOTES_FRAME, items: NOTES_FRAME.items.map((it, k) => (k === 1 ? { ...it, ask: 'You said numbered; I start at 1. OK?' } : it)) }
const ready = run([proposed(ASKED), checked(ASKED)]).state

test('with the check on, a proposal opens checking: the band checks it, and no row shows until the check is done', () => {
  const { state, effects } = run([proposed(NOTES_FRAME)])
  assert.equal(state.open?.checking, true)
  assert.deepEqual(effects, [{ kind: 'examine', id: '4' }])
  const sc = screen(state.open!, 78, 'notes')
  assert.deepEqual([sc.foot.keys, sc.stops], [[], []])
  assert.equal(plain(sc).some(l => l.includes(LABELS.ok)), false)
  for (const e of [{ type: 'yes' }, { type: 'approve' }, { type: 'move', by: 1 }] as Event[]) assert.deepEqual(step(state, e).state, state)
  const done = run([checked(NOTES_FRAME)], state)
  assert.equal(done.state.open?.cursor, 'c2') // the session's own question: the check's remark on c1 asks nothing plain
  assert.equal(done.state.open?.checking, false)
  assert.deepEqual(done.effects, [{ kind: 'focus' }])
})

test('with the check off the picker opens at once, nothing is checked, and OK is offered', () => {
  const { state, effects } = run([proposed(NOTES_SPLIT, null, 'off')])
  assert.equal(state.open?.checking, false)
  assert.deepEqual(effects, [])
  const approve = run([{ type: 'focus', stop: 'ok' }, { type: 'press' }], state)
  assert.deepEqual(approve.effects, [{ kind: 'approve', id: '3', args: ['3', '--ticked', '0,1', '--shown', 'shown-3:x'] }])
})

test('with the switch turned on, the same proposal shown again is checked before its rows show', () => {
  const off = run([proposed(NOTES_FRAME, null, 'off')]).state
  const again = run([{ type: 'reshown', id: '4', proposal: read(NOTES_FRAME), examined: null,
    shown: 'shown-4:x', check: 'on', at: 200 }], off)
  assert.deepEqual([again.state.open?.checking, again.state.open?.began, again.effects], [true, 200, [{ kind: 'examine', id: '4' }]])
})

test('the arrows move between his sentence, each row with its note, and OK; a path line or a note is never a stop', () => {
  const s = run([proposed(NOTES_SPLIT), checked(NOTES_SPLIT, NOTES_CHECKED)]).state
  assert.deepEqual(stopsOf(s.open!), ['said', 'c2', 'c3', 'c4', 'c5', 'k0', 'ok'])
  assert.equal(s.open?.cursor, 'c5')
  assert.equal(run([{ type: 'move', by: 1 }], s).state.open?.cursor, 'k0')
  assert.equal(run([{ type: 'move', by: -1 }], s).state.open?.cursor, 'c4')
  assert.equal(run([{ type: 'move', by: 1 }, { type: 'move', by: 1 }, { type: 'move', by: 1 }], s).state.open?.cursor, 'said') // round again
})

test('y answers the row under the cursor and goes to the next under review; after the last it lands on OK', () => {
  const one = run([{ type: 'yes' }], ready).state
  assert.deepEqual([one.open?.answered, one.open?.cursor], [['c1'], 'c2'])
  const both = run([{ type: 'yes' }], one).state
  assert.deepEqual([both.open?.answered, both.open?.cursor], [['c1', 'c2'], 'ok'])
  assert.deepEqual(run([{ type: 'focus', stop: 'c0' }, { type: 'yes' }], ready).state.open?.answered, []) // a clear row needs none
})

test('o approves the whole, offered only when nothing is left to review; enter on OK approves too', () => {
  assert.deepEqual(run([{ type: 'approve' }], ready).effects, []) // two rows still under review
  const all = run([{ type: 'yes' }, { type: 'yes' }], ready).state
  const args = ['4', '--ticked', '0,1,2', '--shown', 'shown-4:y']
  assert.deepEqual(run([{ type: 'approve' }], all).effects, [{ kind: 'approve', id: '4', args }])
  assert.deepEqual(run([{ type: 'press' }], all).effects, [{ kind: 'approve', id: '4', args }])
  const writing = run([{ type: 'approve' }, { type: 'move', by: 1 }, { type: 'approve' }], all)
  assert.equal(writing.effects.length, 1) // nothing changes under the writer
})

test('a check that could not run offers retry, which checks again; never OK', () => {
  const s = run([proposed(NOTES_FRAME), checked(NOTES_FRAME, FAILED)]).state
  assert.equal(s.open?.cursor, 'retry')
  assert.deepEqual(run([{ type: 'approve' }], s).effects, [])
  const again = run([{ type: 'retry', at: 200 }], s)
  assert.deepEqual([again.state.open?.checking, again.state.open?.began, again.effects], [true, 200, [{ kind: 'examine', id: '4' }]])
  assert.deepEqual(run([{ type: 'press' }], s).effects, [{ kind: 'examine', id: '4' }])
})

test('a proposal changed under the open picker shows as it now stands, checked again, its answers gone', () => {
  const answered = run([{ type: 'yes' }], ready).state
  const p = read(ASKED)
  const reworded = { ...p, items: p.items.map((it, i) => (i === 0 ? { ...it, words: 'add keeps the note' } : it)) }
  const again = run([{ type: 'reshown', id: '4', proposal: reworded, examined: null, shown: 'other:none', check: 'on', at: 300 }], answered)
  assert.deepEqual([again.state.open?.checking, again.state.open?.answered, again.effects], [true, [], [{ kind: 'examine', id: '4' }]])
  const exam = run([{ type: 'reshown', id: '4', proposal: p, examined: FRAME_CHECKED, shown: 'shown-4:z', check: 'on' }], answered)
  assert.deepEqual([exam.state.open?.checking, exam.effects], [false, []]) // its examination alone: not checked again
})

test('the writer done: the picker is gone, one closing line kept, its sentence the next prompt, the next one opened', () => {
  const all = run([{ type: 'yes' }, { type: 'yes' }, { type: 'approve' }, proposed(SPLIT_FILE, null, 'off')], ready).state
  const done = run([{ type: 'written', id: '4', said: 'I approved 4 rows.', closing: 'frame-loop · approved 4 rows in notes' }], all)
  assert.equal(done.state.closing, 'frame-loop · approved 4 rows in notes')
  assert.deepEqual(done.effects, [{ kind: 'load', id: 'p2' }, { kind: 'submit', text: 'I approved 4 rows.' }])
  assert.equal(run([{ type: 'prompted' }], done.state).state.closing, '')
  const failed = run([{ type: 'unwritten', id: '4', text: 'disk full' }], all).state
  assert.deepEqual([failed.open?.writing, failed.open?.failed], [false, 'disk full'])
})

test('options: y picks the row under the cursor, and OK is offered once one is picked', () => {
  const s = run([proposed(OPTIONS_FILE, null, 'off')]).state
  assert.deepEqual(run([{ type: 'approve' }], s).effects, [])
  const picked = run([{ type: 'move', by: 1 }, { type: 'yes' }, { type: 'approve' }], s)
  assert.deepEqual(picked.effects.at(-1), { kind: 'approve', id: 'p4', args: ['p4', '--ticked', '', '--pick', '1', '--shown', 'shown-p4:x'] })
  assert.equal(picked.state.open?.cursor, 'ok') // the ring went to OK with the pick
})

test('a re-proposal for the same place and kind takes the open one’s place, checked afresh, and never queues', () => {
  const again = { ...NOTES_FRAME, id: '5', title: 'notes, said again' }
  const { state, effects } = run([proposed(again)], ready)
  assert.deepEqual([state.open?.id, state.open?.checking, state.waiting], ['5', true, []])
  assert.deepEqual(effects, [{ kind: 'replaced', id: '4', by: '5' }, { kind: 'examine', id: '5' }])
  assert.ok(replacedTold('4').includes('4'))
  const behind = run([proposed(SPLIT_FILE), proposed({ ...SPLIT_FILE, id: 'p6' })], ready)
  assert.deepEqual([behind.state.waiting.map(w => w.id), behind.effects], [['p6'], [{ kind: 'replaced', id: 'p2', by: 'p6' }]])
})

test('with no picker open, a key does nothing', () => {
  for (const type of ['approve', 'yes', 'press', 'help', 'details', 'close', 'aside'] as const) assert.deepEqual(step(EMPTY, { type } as Event), { state: EMPTY, effects: [] })
})

test('every move of the cursor brings the pane’s ring with it; the ring landing on a stop moves the cursor alone', () => {
  for (const e of [{ type: 'move', by: 1 }, { type: 'move', by: -1 }, { type: 'go', stop: 'c2' }, { type: 'yes' }] as Event[]) {
    assert.deepEqual(run([e], ready).effects, [{ kind: 'focus' }], e.type)
  }
  assert.equal(run([{ type: 'go', stop: 'ok' }], ready).state.open?.cursor, 'ok') // page down, to a stop a page away
  assert.deepEqual(run([{ type: 'go', stop: 'nowhere' }], ready).state, ready)
  const landed = run([{ type: 'focus', stop: 'c2' }], ready)
  assert.deepEqual([landed.state.open?.cursor, landed.effects], ['c2', []]) // the ring is already there
})

test('esc closes the picker for now, the proposal waiting with its answers; /frame-loop reopens it as he left it', () => {
  const answered = run([{ type: 'yes' }], ready).state
  const aside = run([{ type: 'aside' }], answered).state
  assert.deepEqual([aside.open?.aside, aside.open?.answered], [true, ['c1']])
  assert.equal(pickerLine(aside), `${LABELS.pickerHolds} 4, ${LABELS.pickerAside}`)
  const back = run([{ type: 'resume' }], aside)
  assert.deepEqual([back.state.open?.aside, back.state.open?.answered, back.state.open?.cursor, back.effects], [false, ['c1'], 'c2', [{ kind: 'focus' }]])
})

test('the person’s close: on the list the proposal waits; in his change’s line that line alone closes, the pane taken back', () => {
  const closed = run([{ type: 'closed' }], ready)
  assert.deepEqual([closed.state.open?.aside, closed.effects], [true, []])
  assert.deepEqual(run([{ type: 'closed' }], closed.state).state, closed.state) // closed already: nothing more
  const typing = run([{ type: 'yes' }, { type: 'press' }], ready).state
  const back = run([{ type: 'closed' }], typing)
  assert.deepEqual([back.state.open?.aside, back.state.open?.changing, back.state.open?.answered, back.effects], [false, '', ['c1'], [{ kind: 'regain' }]])
  const changed = run([{ type: 'changed', text: 'x' }], ready).state // the session answers his change: the pane was closed by the band
  assert.deepEqual(run([{ type: 'closed' }], changed).state, changed)
})

test('nothing but OK, a change or esc closes it: no x, and tab and the arrows go round, however often pressed', () => {
  assert.deepEqual(step(ready, { type: 'close' } as unknown as Event), { state: ready, effects: [] }) // there is no x
  let s = ready
  const stops = stopsOf(s.open!)
  for (let k = 0; k < 20; k++) s = run([{ type: 'move', by: 1 }], s).state
  assert.equal(s.open?.cursor, stops[(stops.indexOf('c1') + 20) % stops.length])
  for (let k = 0; k < 20; k++) s = run([{ type: 'move', by: -1 }], s).state
  assert.deepEqual([s.open?.cursor, s.open?.aside], ['c1', false])
  assert.equal(run([{ type: 'prompted' }], s).state.open, s.open) // a prompt with no picker to change leaves it as it is
})

test('enter on a row opens one line under it with the keyboard in it; esc, or the ring off it, goes back, nothing sent', () => {
  const pressed = run([{ type: 'press' }], ready)
  assert.deepEqual([pressed.state.open?.changing, pressed.state.open?.cursor, pressed.state.open?.typed, pressed.effects], ['c1', 'c1', '', [{ kind: 'focus', key: INPUT }]]) // nothing submitted
  assert.deepEqual(stopsOf(pressed.state.open!).slice(0, 4), ['said', 'c0', 'c1', 'c2']) // the line adds no stop of its own
  const back = run([{ type: 'back' }], pressed.state)
  assert.deepEqual([back.state.open?.changing, back.state.open?.cursor, back.effects], ['', 'c1', [{ kind: 'focus' }]]) // the ring back on the row
  const typing = run([{ type: 'typed', text: 'start at 0' }], pressed.state).state
  assert.deepEqual([typing.open?.cursor, typing.open?.changing, typing.open?.typed], ['c1', 'c1', 'start at 0'])
  for (const off of [{ type: 'focus', stop: 'c2' }, { type: 'move', by: -1 }] as Event[]) { // off the line: closed, nothing answered
    const gone = run([off], pressed.state).state.open
    assert.deepEqual([gone?.changing, gone?.answered], ['', []])
  }
  assert.equal(run([{ type: 'move', by: 1 }], typing).state.open?.changing, '') // tab away, the line closes
  const clicked = run([{ type: 'press', stop: 'c2' }], ready).state // a press on another row: that row
  assert.deepEqual([clicked.open?.cursor, clicked.open?.changing], ['c2', 'c2'])
  const said = run([{ type: 'focus', stop: 'said' }, { type: 'press' }], ready).state
  assert.equal(said.open?.changing, 'said')
  assert.deepEqual(changeTold(pressed.state.open!), [`${LABELS.changeRow} 4: “--list prints every note, numbered from 1”.`, LABELS.changeTold])
  assert.deepEqual(changeTold(said.open!), [`${LABELS.changeWhole} 4.`, LABELS.changeTold])
  assert.deepEqual(changeTold(ready.open!), [`${LABELS.changeWhole} 4.`, LABELS.changeTold]) // typed with no row chosen
  assert.deepEqual(changeTold(pressed.state.open!, true), [`${LABELS.changeWhole} 4.`, LABELS.changeTold]) // a line at the host's prompt
  assert.equal(run([{ type: 'typed', text: 'start at 0' }], typing).state.open?.typed, 'start at 0')
  assert.equal(run([{ type: 'typed', text: 'x' }], ready).state.open?.typed, '') // no line open: nothing kept
})

test('enter in the empty line answers a row under review yes, as y does, and closes it; elsewhere it closes it, nothing sent', () => {
  const pressed = run([{ type: 'press' }], ready).state
  const yes = run([{ type: 'submit', text: '' }], pressed)
  assert.deepEqual([yes.state.open?.answered, yes.state.open?.changing, yes.state.open?.cursor], [['c1'], '', 'c2']) // the next under review
  assert.deepEqual(yes.state.open, run([{ type: 'yes' }], ready).state.open) // exactly as y
  const spaces = run([{ type: 'submit', text: '  ' }], pressed).state.open
  assert.deepEqual([spaces?.answered, spaces?.changing], [['c1'], ''])
  const clear = run([{ type: 'press', stop: 'c0' }, { type: 'submit', text: '' }], ready).state.open // a row not under review
  assert.deepEqual([clear?.answered, clear?.changing, clear?.cursor], [[], '', 'c0'])
  const said = run([{ type: 'focus', stop: 'said' }, { type: 'press' }, { type: 'submit', text: '' }], ready).state.open
  assert.deepEqual([said?.answered, said?.changing, said?.cursor], [[], '', 'said'])
  const last = run([{ type: 'yes' }, { type: 'press' }, { type: 'submit', text: '' }], ready).state.open // the last under review
  assert.deepEqual([last?.answered, last?.cursor], [['c1', 'c2'], 'ok']) // one press, one row
  const words = run([{ type: 'submit', text: 'start at 0' }], pressed).state.open
  assert.deepEqual([words?.changed, words?.changing, words?.typed], ['start at 0', '', ''])
})

test('d on his sentence shows it whole, and again hides it; on a row, its details', () => {
  const on = run([{ type: 'focus', stop: 'said' }, { type: 'details' }], ready).state
  assert.equal(on.open?.details, 'said')
  assert.equal(run([{ type: 'details' }], on).state.open?.details, '')
  assert.equal(run([{ type: 'details' }], ready).state.open?.details, 'c1')
})

test('h and d each ask for the ring after the drawing they make; h or esc closes one layer alone', () => {
  const help = run([{ type: 'help' }], ready)
  assert.deepEqual([help.state.open?.help, help.effects], [true, [{ kind: 'focus' }]])
  const shut = run([{ type: 'help' }], help.state)
  assert.deepEqual([shut.state.open?.help, shut.effects], [false, [{ kind: 'focus' }]])
  const details = run([{ type: 'details' }], ready)
  assert.deepEqual([details.state.open?.details, details.effects], ['c1', [{ kind: 'focus' }]])
  const hidden = run([{ type: 'details' }], details.state)
  assert.deepEqual([hidden.state.open?.details, hidden.effects], ['', [{ kind: 'focus' }]])
  for (const done of [run([{ type: 'closed' }], help.state), run([{ type: 'closed' }], details.state)]) {
    assert.equal(done.state.open?.aside, false)
    assert.deepEqual(done.effects, [{ kind: 'focus' }])
  }
  assert.deepEqual([run([{ type: 'closed' }], help.state).state.open?.help, run([{ type: 'closed' }], details.state).state.open?.details],
    [false, ''])
})

test('his change closes the picker while the session answers; with no new proposal it opens again, his answers kept', () => {
  const answered = run([{ type: 'yes' }, { type: 'press' }], ready).state // c2 chosen for change
  const changed = run([{ type: 'changed', text: 'one line, at most 80 characters' }], answered).state
  assert.deepEqual([changed.open?.changed, changed.open?.changing], ['one line, at most 80 characters', ''])
  assert.equal(pickerLine(changed), `${LABELS.pickerHolds} 4, ${LABELS.pickerChanged}`)
  assert.deepEqual(held(changed), ['4']) // still held, none of it approved
  for (const e of [{ type: 'yes' }, { type: 'approve' }, { type: 'press' }] as Event[]) assert.equal(run([e], changed).state.open?.answered.length, 1)
  const turned = run([{ type: 'turned' }], changed).state
  assert.deepEqual([turned.open?.changed, turned.open?.answered, turned.open?.id], ['', ['c1'], '4'])
  assert.equal(run([{ type: 'reopen' }], changed).state.open?.changed, '') // his line never entered: no answer comes
  assert.equal(run([{ type: 'changed', text: 'x' }], run([{ type: 'aside' }], ready).state).state.open?.changed, '') // closed by esc: no change
})

test('the session’s answer to his change takes the place of the one changed, whatever its place and kind', () => {
  const changed = run([{ type: 'changed', text: 'split it in two' }], ready).state
  const again = run([proposed(SPLIT_FILE, null, 'off')], changed)
  assert.deepEqual([again.state.open?.id, again.state.waiting, again.effects], ['p2', [], [{ kind: 'replaced', id: '4', by: 'p2' }, { kind: 'focus' }]])
  const unchanged = run([proposed(SPLIT_FILE, null, 'off')], ready) // with no change of his, it waits behind
  assert.deepEqual([unchanged.state.open?.id, unchanged.state.waiting.map(w => w.id)], ['4', ['p2']])
})

test('the session withdraws the open proposal only while his change to it stands, and so it closes with nothing written', () => {
  assert.deepEqual(step(ready, { type: 'withdrawn' }), { state: ready, effects: [] })
  const waiting = run([proposed(SPLIT_FILE, null, 'off'), { type: 'changed', text: 'drop it' }], ready).state
  const gone = run([{ type: 'withdrawn' }], waiting)
  assert.deepEqual([gone.state.open, gone.state.told, gone.effects], [null, [closedTold('4')], [{ kind: 'load', id: 'p2' }]])
})

test('answers survive a new proposal: a row whose words and question stand unchanged keeps his yes', () => {
  const answered = run([{ type: 'yes' }, { type: 'yes' }], ready).state // c1 and c2 answered
  const p = read(ASKED)
  const items = p.items.map((it, k) => (k === 2 ? { ...it, ask: 'You did not say one line; I would keep it to 80 characters. OK?' } : it))
  const next = { id: '5', proposal: { ...p, id: '5', items }, examined: FRAME_CHECKED, shown: 'shown-5:y', check: 'on' as const }
  const changed = run([{ type: 'changed', text: 'at most 80 characters' }, { type: 'proposed', ...next, examined: null, at: 1 }], answered).state
  assert.deepEqual([changed.open?.id, changed.open?.checking, changed.open?.answered], ['5', true, []])
  const done = run([{ type: 'checked', failed: '', ...next }], changed).state
  assert.deepEqual(done.open?.answered, ['c1']) // c2's question changed: asked again
  assert.equal(done.open?.cursor, 'c2')
  assert.deepEqual(rowsOf(done.open!).map(r => r.status), ['Clear', 'Yes', 'Review', ''])
})

test('a main turn ended: the line that told what he approved gives way to the band at rest', () => {
  const s = { ...EMPTY, ever: true, closing: 'frame-loop · approved 4 rows in notes' }
  assert.equal(run([{ type: 'turned' }], s).state.closing, '')
  assert.equal(run([{ type: 'prompted' }], s).state.closing, '')
})

test('a second proposal waits, never takes the open one’s place, and opens when it closes, his sentence kept with it', () => {
  const waiting = run([proposed(SPLIT_FILE, null, 'off', 'split the api'), proposed(OPTIONS_FILE, null, 'off')], ready)
  assert.deepEqual([waiting.state.open?.id, waiting.state.waiting.map(w => w.id), waiting.effects], ['4', ['p2', 'p4'], []])
  const closed = run([{ type: 'changed', text: 'drop it' }, { type: 'withdrawn' }], waiting.state)
  assert.deepEqual(closed.effects, [{ kind: 'load', id: 'p2' }])
  const next = run([{ ...proposed(SPLIT_FILE, null, 'off'), said: undefined } as Event], closed.state)
  assert.deepEqual([next.state.open?.id, next.state.open?.said, next.state.waiting.map(w => w.id)], ['p2', 'split the api', ['p4']])
  const lost = run([{ type: 'lost', id: 'p2' }], closed.state)
  assert.deepEqual([lost.state.waiting.map(w => w.id), lost.effects], [['p4'], [{ kind: 'load', id: 'p4' }]])
})

test('the session is told at its next prompt how the picker stands, and each proposal closed with nothing written', () => {
  assert.deepEqual(pickerTold(EMPTY), []) // a session that never proposed is told nothing
  const checking = run([proposed(NOTES_FRAME)]).state
  assert.equal(pickerLine(checking), `${LABELS.pickerHolds} 4, ${LABELS.pickerChecking}`)
  const waiting: Picker = run([proposed(SPLIT_FILE), proposed(OPTIONS_FILE)], ready).state
  assert.equal(pickerLine(waiting), `${LABELS.pickerHolds} 4; ${LABELS.pickerWaiting} p2, p4`)
  const closed = run([{ type: 'changed', text: 'drop it' }, { type: 'withdrawn' }, { ...proposed(SPLIT_FILE, null, 'off') }], waiting).state
  assert.deepEqual(pickerTold(closed), [closedTold('4'), `${LABELS.pickerNow} ${LABELS.pickerHolds} p2; ${LABELS.pickerWaiting} p4.`,
    LABELS.unapprovedTold]) // while it holds one: nothing of it approved, build nothing, an answer means propose again
  assert.deepEqual(held(closed), ['p2', 'p4'])
  const empty = run([{ type: 'changed', text: 'no' }, { type: 'withdrawn' }], run([proposed(NOTES_FRAME, null, 'off')]).state).state
  assert.deepEqual(pickerTold(empty), [closedTold('4'), `${LABELS.pickerNow} ${LABELS.pickerEmpty}.`]) // none held: no such line
  assert.deepEqual(run([{ type: 'told' }], closed).state.told, [])
})

test('a re-proposal in the open one’s place puts the ring on its cursor, once its rows show', () => {
  const off = run([proposed(NOTES_FRAME, null, 'off')]).state
  assert.deepEqual(run([proposed({ ...ASKED, id: '5' }, null, 'off')], off).effects, [{ kind: 'replaced', id: '4', by: '5' }, { kind: 'focus' }])
  assert.deepEqual(run([proposed({ ...ASKED, id: '5' })], ready).effects, [{ kind: 'replaced', id: '4', by: '5' }, { kind: 'examine', id: '5' }]) // checked first
})
