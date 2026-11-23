// What the picker shows in its pane, as the settled screen: drawn as plain text, and read with every tone taken away.
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { examinedOf } from '../../hooks/band/frameloop'
import { LABELS } from '../../hooks/band/labels'
import { step } from '../../hooks/band/picker'
import { duration, fit, footerText, footPieces, groupsOf, heightOf, helpLines, isOffered, MAX_WIDTH, pageTo, paneScreen, plain, rowsOf, saidLines, screen, shown, stopsOf } from '../../hooks/band/view'
import type { Screen } from '../../hooks/band/view'
import type { Open } from '../../types'
import {
  ALONE, FAILED, FRAME_CHECKED, FRAME_FILE, GADFLY, IDLE, NOTES_CHECKED, NOTES_FRAME, NOTES_ROADS, NOTES_SPLIT, OPTIONS_FILE, opened, REFRAME_FILE,
  ROADS_CHECKED, run, SAID, SPLIT_FILE, UNSEEN,
} from './fixtures'

const at = (o: Open, ...events: Parameters<typeof step>[1][]) => {
  const s = run(events, { open: o, waiting: [], told: [], ever: true, closing: '' }).state.open
  assert.ok(s)
  return s
}
// The picker as the pane draws it, the pane holding the keyboard unless `focused` is false.
const drawn = (o: Open, width = 78, focused = true) => plain(screen(o, width, 'notes', '', '', false, focused))
const foot = (o: Open, focused = true) => footerText(screen(o, 78, 'notes', '', '', false, focused).foot)
const KEYS_TAIL = `tab next · h help · esc ${LABELS.keys.close}`
const SAID_ONE = '   You said: a small cli app for notes, add saves a note and --list prints th…'

test('how long a run has gone: seconds under a minute, then minutes and the seconds left, as the Python side says it', () => {
  const cases: [number, string][] = [[0, '0 s'], [42, '42 s'], [59, '59 s'], [60, '1 m'], [100, '1 m 40 s'], [120, '2 m'],
    [3599, '59 m 59 s'], [3600, '60 m'], [47.9, '47 s'], [-3, '0 s']] // as frameloop/words.py's duration
  for (const [seconds, said] of cases) assert.equal(duration(seconds), said, String(seconds))
  assert.equal(duration(100), `1 ${LABELS.minutes} 40 ${LABELS.seconds}`)
})

test('the settled sketch in the pane: a crossing in two parts, checked, one row under review, drawn line by line', () => {
  assert.deepEqual(drawn(opened(NOTES_SPLIT, NOTES_CHECKED)), [
    ' frame-loop · pick · checked · 5 rows · 1 to review · row 4 of 5',
    ' notes',
    SAID_ONE,
    ' I\'d build it in two parts                                            │ Check',
    ' ─────────────────────────────────────────────────────────────────────┼───────',
    ' notes → store                                                        │',
    '   keeps each note it is given                                        │ Clear',
    '   gives them back in the order added                                 │ Clear',
    ' notes → cli                                                          │',
    '   add hands its note to the store                                    │ Clear',
    ' ❯ --list prints the notes, numbered from 1                           │ Review',
    `     ↳ ${IDLE}                    │`,
    ' notes → store ↔ cli                                                  │',
    '   one check that runs both sides                                     │ Clear',
    '   OK, build it',
    '',
    ` y yes, fine · enter confirm or change · d details · ${KEYS_TAIL}`,
  ])
})

test('the holds a command checks stand under a heading of their own, a row each with its command; a hold of paths as before', () => {
  const o = opened(NOTES_ROADS, ROADS_CHECKED)
  assert.deepEqual(drawn(o).slice(3, 12), [
    ' I\'d build                                                            │ Check',
    ' ─────────────────────────────────────────────────────────────────────┼───────',
    '   The list option prints each saved note on its own line             │ Clear',
    ' ❯ Notes are kept between runs                                        │ Review',
    `     ↳ ${UNSEEN} │`,
    '   Payments stay untouched · src/pay/**                               │',
    ` ${LABELS.byCommand}                                                 │`,
    '   The store is the tool\'s own code · python3 check_imports.py        │',
    '   The round-trip tests pass · python3 -m unittest test_notes         │',
  ])
  assert.deepEqual(stopsOf(o), ['said', 'c0', 'c1', 'h2', 'h0', 'h1', 'ok']) // the ring walks them as drawn
  const long = { ...NOTES_ROADS, holds: [{ words: 'The vectors pass', command: `python3 -m unittest ${'tests.test_vectors.'.repeat(5)}Published` }] }
  const lines = drawn(opened(long, ROADS_CHECKED))
  const at = lines.findIndex(l => l.includes('The vectors pass'))
  assert.equal(lines[at - 1]?.trim(), `${LABELS.byCommand}                                                 │`.trim())
  assert.ok(lines.slice(at, at + 3).join(' ').replace(/ *│ */g, ' ').includes('Published'), lines.join('\n')) // a command is never cut: it wraps
  assert.ok(lines.slice(at, at + 3).every(l => l.endsWith('│')), lines.join('\n')) // inside the table
  const split = drawn(opened(SPLIT_FILE, null, 'off'))
  const head = split.findIndex(l => l.startsWith(` ${LABELS.byCommand}`))
  assert.ok(split[head - 2]?.includes('→ limits') && split[head + 1]?.includes('The limits tests pass'), split.join('\n')) // under its part
})

test('the header says where the cursor rests among the rows, and nothing of it on his sentence or on OK', () => {
  const o = opened(NOTES_SPLIT, NOTES_CHECKED)
  assert.ok(drawn(o)[0]?.endsWith(` · ${LABELS.rows[0]} 4 ${LABELS.of} 5`))
  assert.ok(drawn(at(o, { type: 'move', by: 1 }))[0]?.endsWith(' · row 5 of 5'))
  for (const stop of ['said', 'ok']) assert.ok(!drawn(at(o, { type: 'focus', stop }))[0]?.includes(' of 5'), stop)
  assert.equal(drawn(opened(OPTIONS_FILE, null, 'off'))[0], ` ${LABELS.name} · ${LABELS.pick} · 2 ${LABELS.options[1]} · ${LABELS.pickOne} · row 1 of 2`)
})

test('one question a row: the session’s own where it asked, the check’s other remarks under d alone', () => {
  const both = examinedOf({ marks: [{ item: 2, kind: 'alone', words: ALONE }, { item: 2, kind: 'idle', words: IDLE }], carried: null, validated: true,
    steps: FRAME_CHECKED.steps })!
  const o = at(opened(NOTES_FRAME, both), { type: 'focus', stop: 'c2' })
  const row = rowsOf(o).find(r => r.id === 'c2')!
  assert.deepEqual(row.notes, ['You did not say a note is one line; I would keep it to one. OK?'])
  assert.ok(row.details.includes(`${LABELS.note}${IDLE}`) && row.details.includes(`${LABELS.note}${ALONE}`), row.details.join('\n'))
  const text = drawn(o, 120).join('\n')
  assert.ok(!text.includes(ALONE) && !text.includes(IDLE), text)
  assert.ok(drawn(at(o, { type: 'details' }), 120).join('\n').includes(IDLE)) // under d
  const answered = at(o, { type: 'yes' }) // one y, one question
  assert.equal(rowsOf(answered).find(r => r.id === 'c2')?.status, 'Yes')
})

test('a remark of the check that is no plain question leaves a row with no question of the session’s clear, under d', () => {
  const o = opened(NOTES_FRAME, FRAME_CHECKED) // «the same»-like: the row may lean on another
  const row = rowsOf(o).find(r => r.id === 'c1')!
  assert.deepEqual([row.status, row.notes], ['Clear', []])
  assert.ok(row.details.includes(`${LABELS.note}${ALONE}`))
  assert.equal(o.cursor, 'c2') // the first row under review: the session's own question
  const turned = examinedOf({ marks: [{ item: 1, kind: 'alone-unsettled', words: 'the check could not tell. Is it clear as written?' }], carried: null,
    validated: true, steps: FRAME_CHECKED.steps })!
  assert.equal(rowsOf(opened(NOTES_FRAME, turned)).find(r => r.id === 'c1')?.status, 'Clear')
  const plainly = examinedOf({ marks: [{ item: 1, kind: 'idle', words: IDLE }], carried: null, validated: true, steps: FRAME_CHECKED.steps })!
  assert.deepEqual(rowsOf(opened(NOTES_FRAME, plainly)).find(r => r.id === 'c1')?.notes, [IDLE]) // a plain question stays
})

test('a check that could not run is one plain line with its reason and retry, closed only by esc, and no OK', () => {
  const o = opened(NOTES_FRAME, FAILED)
  assert.deepEqual(drawn(o), [
    ' frame-loop · pick · check failed',
    ' notes',
    SAID_ONE,
    ' The check could not run: Gadfly is not installed, as there is no gadfly',
    ' command.',
    ' ❯ Check again',
    '',
    ` r retry · esc ${LABELS.keys.close}`,
  ])
  assert.equal(isOffered(o), false)
  assert.equal(at(o, { type: 'approve' }).writing, false)
  const crashed = at(opened(NOTES_FRAME, null), { type: 'checked', id: '4', failed: `${LABELS.checkFailedLead} the band timed out`,
    proposal: o.proposal, examined: null, shown: 'x:none', check: 'on' })
  assert.ok(drawn(crashed).includes(` ${LABELS.checkFailedLead} the band timed out`))
  assert.equal(isOffered(crashed), false)
})

test('with the check off the picker opens at once, says so, judges no row, and offers OK', () => {
  const o = opened(NOTES_FRAME, null, 'off')
  assert.equal(o.checking, false)
  const lines = drawn(o)
  assert.equal(lines[0], ` ${LABELS.name} · ${LABELS.pick} · ${LABELS.checkOff} · 4 rows · 1 ${LABELS.toReview} · row 3 of 4`) // the session's own ask
  assert.ok(!lines.some(l => /│ (Clear|Review)$/.test(l) && !l.includes('one line of text')), lines.join('\n'))
  assert.equal(isOffered(at(o, { type: 'focus', stop: 'c2' }, { type: 'yes' })), true)
})

test('the last line promises a confirm only on a row under review: elsewhere enter changes the row, or all of it', () => {
  const off = opened(NOTES_FRAME, null, 'off')
  const row = rowsOf(off)[0].id
  assert.match(foot(at(off, { type: 'focus', stop: row })), /^enter change this row · /) // the check off, and no ask on this row: nothing to confirm
  assert.match(foot(at(off, { type: 'focus', stop: 'said' })), /^enter change it all · /)
  const on = at(opened(NOTES_FRAME, FRAME_CHECKED), { type: 'focus', stop: 'c2' })
  assert.equal(rowsOf(on).find(r => r.id === 'c2')?.status, 'Review')
  assert.match(foot(on), /^y yes, fine · enter confirm or change · /) // an empty line there confirms, as y does
})

test('with the check on, a row the maker gave no step is Review with why, and can only be changed', () => {
  const partial = examinedOf({ marks: [{ item: 2, kind: 'unread', words: `could not be checked: ${GADFLY}.` }], carried: null, validated: false,
    steps: { '0': FRAME_CHECKED.steps['0'], '1': FRAME_CHECKED.steps['1'] } })
  const o = at(opened(NOTES_FRAME, partial), { type: 'focus', stop: 'c2' })
  const row = rowsOf(o).find(r => r.id === 'c2')
  assert.deepEqual([row?.status, row?.notes, row?.noStep], ['Review', ['You did not say a note is one line; I would keep it to one. OK?', `could not be checked: ${GADFLY}.`], true])
  assert.equal(foot(o), `enter change this row · d details · ${KEYS_TAIL}`) // no y, and nothing an empty line could confirm
  const after = at(o, { type: 'yes' })
  assert.deepEqual(after.answered, [])
  const still = at(o, { type: 'press' }, { type: 'submit', text: '' })
  assert.deepEqual([still.changing, still.answered], ['c2', []]) // an empty Enter cannot answer a row that can only be changed
  const none = opened(NOTES_FRAME, examinedOf({ marks: [], carried: null, validated: false, steps: {} }))
  assert.deepEqual(rowsOf(none).find(r => r.id === 'c0')?.notes, [LABELS.unchecked])
})

test('the header counts down as he answers, and the cursor goes to the next row under review, then to OK', () => {
  const asked = { ...NOTES_FRAME, items: NOTES_FRAME.items.map((it, k) => (k === 1 ? { ...it, ask: 'You said numbered; I start at 1. OK?' } : it)) }
  const o = opened(asked, FRAME_CHECKED)
  assert.equal(o.cursor, 'c1') // the first row under review
  const one = at(o, { type: 'yes' })
  assert.equal(one.cursor, 'c2')
  assert.equal(drawn(one)[0], ` ${LABELS.name} · ${LABELS.pick} · ${LABELS.checked} · 4 rows · 1 ${LABELS.toReview} · row 3 of 4`)
  assert.ok(drawn(one).includes('   --list prints every note, numbered from 1                          │ Yes'))
  const both = at(one, { type: 'yes' })
  assert.equal(both.cursor, 'ok')
  assert.equal(drawn(both)[0], ` ${LABELS.name} · ${LABELS.pick} · ${LABELS.checked} · 4 rows · ${LABELS.allAnswered}`)
  assert.equal(isOffered(both), true)
  assert.ok(foot(both).startsWith('enter build it'))
  assert.equal(opened(NOTES_SPLIT, examinedOf({ ...NOTES_CHECKED, marks: [] })).cursor, 'c2') // none to review: the first row
})

test('the column rule never breaks: every line of the list carries it at one column, a wrapped row and its question too', () => {
  const long = { ...NOTES_FRAME, items: NOTES_FRAME.items.map((it, k) => (k === 2 ? { ...it,
    words: 'a note is one line of text, and a second line given to add is refused with a short message that names the line' } : it)) }
  for (const o of [opened(NOTES_SPLIT, NOTES_CHECKED), opened(NOTES_FRAME, FRAME_CHECKED), at(opened(NOTES_FRAME, FRAME_CHECKED), { type: 'details' }),
    opened(long, FRAME_CHECKED), at(opened(long, FRAME_CHECKED), { type: 'press' })]) {
    const lines = drawn(o)
    const first = lines.findIndex(l => l.includes('│ Check'))
    const last = lines.findIndex(l => l.includes(LABELS.ok))
    const column = lines[first]!.indexOf('│')
    for (const line of lines.slice(first + 2, last)) assert.equal(line.indexOf('│'), column, line)
    assert.equal(lines[first + 1]!.indexOf('┼'), column)
  }
  const lines = drawn(opened(long, FRAME_CHECKED))
  const row = lines.findIndex(l => l.includes('a note is one line of text, and'))
  assert.ok(lines[row]!.trimEnd().endsWith(LABELS.review), lines[row]) // the status word next to the row's first line
  assert.ok(lines[row + 1]!.startsWith('     ') && lines[row + 1]!.includes('names the line'), lines.join('\n')) // whole, wrapped, no …
  assert.ok(!lines.slice(3).join('\n').includes('…'))
})

test('a row wrapped at any width keeps the rule at one column: its later lines, set further in, wrap shorter', () => {
  const words = 'notes --list prints every saved note on a line of its own, numbered from 1 in the order they were added, and the ' +
    'number may be up to four digits wide so that a store of ten thousand notes still lines up in one straight column of plain text'
  const long = { ...NOTES_FRAME, items: NOTES_FRAME.items.map((it, k) => (k === 1 ? { ...it, words } : it)) }
  for (let width = 40; width <= MAX_WIDTH; width++) {
    const lines = drawn(opened(long, FRAME_CHECKED), width)
    const first = lines.findIndex(l => l.includes('│ Check'))
    const column = lines[first]!.indexOf('│')
    for (const line of lines.slice(first + 2, lines.findIndex(l => l.includes(LABELS.ok)))) assert.equal(line.indexOf('│'), column, `${width}: ${line}`)
  }
})

test('at most MAX_WIDTH wide, at the left of a wide pane, so the status word stays near its row', () => {
  const lines = drawn(opened(NOTES_SPLIT, NOTES_CHECKED), 243)
  assert.equal(MAX_WIDTH, 110)
  for (const line of lines) assert.ok(line.length <= MAX_WIDTH, `${line.length}: ${line}`)
  assert.equal(lines.find(l => l.includes('┼'))?.length, MAX_WIDTH) // the table fills the width it has
  assert.ok(lines.find(l => l.includes('│ Review'))!.indexOf('│') < MAX_WIDTH - 7)
})

test('compact: one blank line in all, before the last line', () => {
  for (const o of [opened(NOTES_SPLIT, NOTES_CHECKED), opened(NOTES_FRAME, FRAME_CHECKED), opened(NOTES_FRAME, FAILED), opened(NOTES_FRAME, null)]) {
    const lines = drawn(o)
    assert.equal(lines.filter(l => l === '').length, 1)
    assert.equal(lines.at(-2), '')
  }
})

test('his sentence stands first, word for word, typos and all, in one line where it fits', () => {
  const typed = 'make teh list cmd print notes numberd'
  assert.equal(drawn(opened(NOTES_FRAME, FRAME_CHECKED, 'on', typed), 120)[2], `   ${LABELS.youSaid}${typed}`)
  assert.equal(drawn(opened(NOTES_FRAME, FRAME_CHECKED), 120)[2], `   ${LABELS.youSaid}${SAID}`)
  assert.equal(drawn(opened(NOTES_FRAME, FRAME_CHECKED, 'on', ''), 120).some(l => l.includes(LABELS.youSaid)), false)
})

test('the path says where in the tree: down into each part, across what two parts share', () => {
  const groups = groupsOf(opened(SPLIT_FILE, null, 'off'), 'notes → src/api')
  assert.deepEqual(groups.map(g => g.path), ['notes → src/api → limits', 'notes → src/api → auth', 'notes → src/api → auth ↔ limits'])
  assert.deepEqual(groupsOf(opened(NOTES_FRAME, null, 'off'), 'notes').map(g => g.path), [''])
})

test('nothing is told by colour alone: with every tone taken away, each state is still told by its words and glyphs', () => {
  const states: [string, Open][] = [
    ['under review', opened(NOTES_FRAME, FRAME_CHECKED)],
    ['answered', at(opened(NOTES_FRAME, FRAME_CHECKED), { type: 'yes' })],
    ['check off', opened(NOTES_FRAME, null, 'off')],
    ['failed', opened(NOTES_FRAME, FAILED)],
    ['checking', opened(NOTES_FRAME, null)],
    ['crossing', opened(NOTES_SPLIT, NOTES_CHECKED)],
    ['choosing', at(opened(NOTES_FRAME, FRAME_CHECKED), { type: 'press' })],
    ['changing', at(opened(NOTES_FRAME, FRAME_CHECKED), { type: 'press' }, { type: 'typed', text: 'keep it to 80' })],
  ]
  for (const [name, o] of states) {
    for (const focused of [true, false]) {
      const sc = screen(o, 78, 'notes', '', '', false, focused)
      const text = plain(sc)
      const head = text[0] ?? ''
      const rows = rowsOf(o)
      if (name === 'checking') assert.ok(head.includes(LABELS.checking) && text.at(-1) === ` ${LABELS.pleaseWait}`, head)
      else if (name === 'failed') assert.ok(text.some(l => l.includes(LABELS.checkFailedLead)) && head.includes(LABELS.checkFailed))
      else {
        const left = rows.filter(r => r.status === 'Review').length
        assert.ok(left ? head.includes(`${left} ${LABELS.toReview}`) : !head.includes(LABELS.toReview), `${name}: ${head}`)
        for (const r of rows) {
          const line = text.find(l => l.includes(r.text.slice(0, 20)))
          const word = { Clear: LABELS.clear, Review: LABELS.review, Yes: LABELS.yes, '': '' }[r.status]
          assert.ok(line && (word ? line.trimEnd().endsWith(word) : !/(Clear|Review|Yes)$/.test(line.trimEnd())), `${name}: ${r.id} ${line}`)
          if (r.status === 'Review' && !r.noStep) assert.ok(r.notes.length === 1 && r.notes[0]!.endsWith('?') && text.some(l => l.includes(`${LABELS.note}${r.notes[0]!.slice(0, 30)}`)), name)
        }
      }
      // the cursor by its glyph, once, wherever there is a stop to point at; colour only on what words already say
      assert.equal(text.join('\n').split(LABELS.cursor).length - 1, name === 'checking' ? 0 : 1, name)
      const asked = rows.filter(r => r.status === 'Review').flatMap(r => r.notes)
      for (const line of sc.lines) {
        for (const seg of line.segs.filter(x => x.tone === 'accent')) {
          assert.ok(seg.text === LABELS.cursor || seg.text === LABELS.review || seg.text.endsWith(LABELS.toReview)
            || asked.some(n => n.includes(seg.text)), `${name}: "${seg.text}"`)
        }
      }
    }
  }
})

test('the rows of every use: options with their cost, a reframe with its old words as a question and its reason', () => {
  const options = opened(OPTIONS_FILE, null, 'off')
  assert.ok(drawn(options).includes('   Per day · costs a clock                                            │'))
  const picked = at(options, { type: 'move', by: 1 }, { type: 'yes' })
  assert.equal(picked.pick, 1)
  assert.equal(drawn(picked)[0], ` ${LABELS.name} · ${LABELS.pick} · 2 ${LABELS.options[1]} · ${LABELS.picked}`)
  assert.equal(isOffered(picked), true)
  const reframe = drawn(opened(REFRAME_FILE, null, 'off'))
  assert.ok(reframe.includes(` ${LABELS.again}A reading found "each day" cannot be met: there is no clock here.`))
  assert.deepEqual(rowsOf(opened(REFRAME_FILE, null, 'off'))[0]?.notes, [`${LABELS.replaces}The counts reset each day.${LABELS.replacesTail}`])
  assert.ok(reframe.some(l => l.includes(`${LABELS.replaces}The counts reset each day.`)), reframe.join('\n'))
})

test('a contract with no check yet asks so, and the details of a row hold its step, its reversal and its notes', () => {
  const none = { ...NOTES_SPLIT, split: { ...NOTES_SPLIT.split, contracts: [{ ...NOTES_SPLIT.split.contracts[0]!, command: null }] } }
  const row = rowsOf(opened(none, NOTES_CHECKED)).find(r => r.id === 'k0')
  assert.deepEqual([row?.status, row?.notes], ['Review', [LABELS.noCheckYet]])
  const open = at(opened(NOTES_SPLIT, NOTES_CHECKED), { type: 'details' })
  assert.ok(drawn(open).some(l => l.includes(`${LABELS.detailStep}1. A note is kept.`)))
  assert.ok(drawn(open).some(l => l.includes(`${LABELS.detailTurned}1. A note is lost.`)))
})

test('h lists every key, wrapped under its first word, and there is no key that closes the picker but esc', () => {
  const o = at(opened(NOTES_FRAME, FRAME_CHECKED), { type: 'help' })
  const sc = screen(o, 36, 'notes', '', '', false, true)
  const lines = drawn(o, 36)
  for (const key of ['↑ ↓,', 'pgup pgdn', 'y', 'enter', 'o', 'd', 'h', 'esc']) assert.ok(LABELS.help.some(h => h.startsWith(`${key} `)), key)
  const help = helpLines(sc)
  assert.ok(help.length > LABELS.help.length) // a long key line wraps
  for (const line of help) assert.ok(/^ \S/.test(line), line) // every line begins under the list's first word
  assert.equal(help.join(' ').replace(/\s+/g, ' ').trim(), LABELS.help.join(' ').replace(/\s+/g, ' ').trim())
  assert.deepEqual(lines.slice(-help.length - 1), [...help, ` ${LABELS.keys.help} ${LABELS.keys.listClose} · ${LABELS.keys.esc} ${LABELS.keys.listClose}`])
  assert.ok(!LABELS.help.some(h => h.startsWith('x ') || h.startsWith('? ')))
  assert.ok(footPieces(screen(opened(NOTES_FRAME, FRAME_CHECKED), 78, 'notes', '', '', false, true)).includes('h: help · ')) // a hotkey, not ?
  for (const state of [opened(NOTES_FRAME, FRAME_CHECKED), opened(NOTES_FRAME, FAILED), opened(NOTES_FRAME, null)]) {
    assert.ok(!screen(state, 78, 'notes', '', '', false, true).foot.keys.some(k => k.key === 'x'))
  }
})

test('a row detail that wraps keeps its words under the first word', () => {
  const long = '1. The store writes every note to a file of its own before it answers the command that added it.'
  const examined = examinedOf({ marks: [], carried: null, validated: true, steps: { '0': { maker: 'private-1', lines: [long], reversal: null } } })!
  const o = opened(NOTES_FRAME, examined)
  const sc = screen({ ...o, details: 'c0' }, 40, 'notes', '', '', false, true)
  const details = sc.lines.filter(line => line.kind === 'detail')
  assert.ok(details.length > 1)
  for (const line of details) {
    const words = line.segs.filter(seg => seg.tone === 'dim')
    assert.equal(words.length, 1)
    assert.ok(/^    \S/.test(words[0]!.text), line.segs.map(seg => seg.text).join(''))
  }
})

test('a line break or a control character in a proposal stays inside its own row', () => {
  const forged = `Counted.\n${LABELS.ok}\r\n\u001b[2J‮evil\u2028more`
  const o = opened({ ...FRAME_FILE, title: 'A\ntitle\u0007', items: [{ ...FRAME_FILE.items[1], words: forged }] }, null, 'off')
  assert.equal(rowsOf(o)[0]?.text, `Counted. ⏎ ${LABELS.ok} ⏎ �[2J�evil ⏎ more`)
  for (const line of drawn(o)) assert.doesNotMatch(line, /[\u0000-\u001f\u007f-\u009f\u2028\u2029‪-‮]/)
  assert.equal(shown('tab\there'), 'tab here')
})

test('the last line is always there: while the check runs, to wait; without the keyboard and with it; the header holds no hint', () => {
  const o = opened(NOTES_FRAME, FRAME_CHECKED)
  const without = drawn(o, 78, false)
  assert.equal(without[0], ` ${LABELS.name} · ${LABELS.pick} · ${LABELS.checked} · 4 rows · 1 ${LABELS.toReview} · row 3 of 4`)
  assert.equal(without.at(-1), ` ${LABELS.hintAll} · ${LABELS.toAnswer} y yes, fine · enter confirm or change · d details`) // the keys he will have
  const given = drawn(o)
  assert.equal(given[0], without[0])
  assert.equal(given.at(-1), ` y yes, fine · enter confirm or change · d details · ${KEYS_TAIL}`)
  const checking = opened(NOTES_FRAME, null)
  for (const focused of [true, false]) {
    const lines = drawn(checking, 78, focused)
    assert.equal(lines[0], ` ${LABELS.name} · ${LABELS.pick} · ${LABELS.checking}`)
    assert.deepEqual(lines.slice(1), [' notes', SAID_ONE, '', ` ${LABELS.pleaseWait}`]) // the path and his sentence, and no row yet
  }
  assert.equal(plain(screen(checking, 78, 'notes', '⠧ frame-loop · checking 2 of 3 · 4 s')).at(0), ' ⠧ frame-loop · checking 2 of 3 · 4 s')
  assert.equal(drawn(opened(NOTES_FRAME, FAILED), 78, false).at(-1), ` ${LABELS.hintAll} · ${LABELS.toAnswer} r retry`)
  assert.ok(plain(screen(o, 78, 'notes', '', '', true)).at(-1)?.startsWith(` ${LABELS.sendsAll} · `)) // he typed in the prompt
})

test('enter on a row opens one line under it and its question, dim while empty; its words wrap inside the table; esc goes back', () => {
  const o = opened(NOTES_FRAME, FRAME_CHECKED)
  assert.equal(foot(o), `y yes, fine · enter ${LABELS.keys.choose} · d details · ${KEYS_TAIL}`) // no hint to write before the line opens
  const pressed = at(o, { type: 'press' })
  assert.deepEqual([pressed.changing, pressed.cursor], ['c2', 'c2'])
  const sc = screen(pressed, 78, 'notes', '', '', false, true)
  const lines = plain(sc)
  const row = lines.findIndex(l => l.includes('a note is one line of text'))
  assert.ok(lines[row]!.trimEnd().endsWith(LABELS.review), lines.join('\n')) // nothing answered or changed yet
  const input = sc.lines.findIndex(l => l.kind === 'input')
  assert.equal(lines[input], `     ${LABELS.inputHint}`.padEnd(70) + '│')
  assert.deepEqual([sc.lines[input - 1]?.kind, sc.lines[input]?.stop], ['note', 'c2']) // under its question, in its block
  assert.equal(sc.lines.filter(l => l.kind === 'input').length, 1) // one line, never two
  assert.equal(sc.lines.length, screen(o, 78, 'notes', '', '', false, true).lines.length + 1)
  assert.equal(lines.at(-1), ` enter ${LABELS.keys.confirm} · esc ${LABELS.keys.back}`)
  assert.ok(!lines.join('\n').toLowerCase().includes('type'), lines.join('\n')) // no letter is a hint before the line opens
  const typing = at(pressed, { type: 'typed', text: 'give it a test of its own' })
  assert.deepEqual([typing.cursor, typing.changing], ['c2', 'c2'])
  const typed = plain(screen(at(typing, { type: 'typed', text: 'give it a test of its own' }), 78, 'notes', '', '', false, true))
  assert.equal(typed[input], `     give it a test of its own`.padEnd(70) + '│')
  assert.ok(typed[row]!.trimEnd().endsWith(LABELS.review))
  assert.equal(typed.at(-1), ` enter ${LABELS.keys.send} · esc ${LABELS.keys.back}`)
  const long = plain(screen(at(typing, { type: 'typed', text: 'every note is one line of at most eighty characters, and a longer one is refused with a message' }),
    78, 'notes', '', '', false, true))
  const wrapped = long.slice(input, long.findIndex(l => l.trimStart().startsWith(LABELS.byCommand)))
  assert.ok(wrapped.join(' ').replace(/[\s│]+/g, ' ').includes('refused with a message'), wrapped.join('\n')) // never cut: they wrap
  assert.ok(wrapped.every(l => l.length === 71 && l.endsWith('│')), wrapped.join('\n')) // inside the table
  const said = at(o, { type: 'focus', stop: 'said' }, { type: 'press' })
  const whole = screen(said, 78, 'notes', '', '', false, true)
  assert.deepEqual(whole.lines.slice(2, 5).map(l => l.kind), ['said', 'said', 'input']) // under his sentence, shown whole
  assert.equal(plain(screen(at(said, { type: 'typed', text: 'give it a test' }), 78, 'notes', '', '', false, true)).at(-1), ` enter ${LABELS.keys.send} · esc ${LABELS.keys.back}`)
  for (const closed of [at(pressed, { type: 'back' }), at(typing, { type: 'back' }), at(pressed, { type: 'move', by: -1 }), at(typing, { type: 'move', by: 1 })]) {
    assert.equal(closed.changing, '')
    assert.ok(!screen(closed, 78, 'notes', '', '', false, true).lines.some(l => l.kind === 'input'))
  }
})

test('the brief’s sketch: the roads, the row under review with its question, and the line under it', () => {
  const o = at(opened({ ...NOTES_ROADS, holds: NOTES_ROADS.holds.slice(0, 2) }, ROADS_CHECKED), { type: 'press' })
  const lines = drawn(o).slice(3, 12).map(l => l.trimEnd())
  assert.deepEqual(lines, [
    ' I\'d build                                                            │ Check',
    ' ─────────────────────────────────────────────────────────────────────┼───────',
    '   The list option prints each saved note on its own line             │ Clear',
    ' ❯ Notes are kept between runs                                        │ Review',
    `     ↳ ${UNSEEN} │`,
    `     ${LABELS.inputHint}`.padEnd(70) + '│',
    ` ${LABELS.byCommand}                                                 │`,
    '   The store is the tool\'s own code · python3 check_imports.py        │',
    '   The round-trip tests pass · python3 -m unittest test_notes         │',
  ])
  const typing = at(o, { type: 'typed', text: 'give it a test of its own' })
  assert.equal(drawn(typing).find(l => l.includes('give it a test of its own')), `     give it a test of its own`.padEnd(70) + '│')
})

// A prompt as the host hands it on: a paste expanded inside its own tags, around lines he wrote.
const PASTED = '\n\n<pasted_content id="0176">\nwrite me a small cli tool for notes\n  jot add <text>  saves one note\n  jot list  prints them\n\n' +
  'keep it in one file, no packages\nand make teh list numbered\nsearch too maybe\nthat is all\n</pasted_content id="0176">\n'

test('his sentence: the host’s paste tags taken out, his empty lines dropped, every other line drawn as a line', () => {
  assert.deepEqual(saidLines(PASTED), ['write me a small cli tool for notes', '  jot add <text>  saves one note', '  jot list  prints them',
    'keep it in one file, no packages', 'and make teh list numbered', 'search too maybe', 'that is all'])
  assert.deepEqual(saidLines('fix this: <pasted_content id="1">x = 1</pasted_content id="1"> please'), ['fix this: x = 1 please'])
  assert.deepEqual(stopsOf(opened(NOTES_FRAME, FRAME_CHECKED, 'on', '\n<pasted_content id="2">\n</pasted_content id="2">\n')).slice(0, 1), ['c0'])
})

test('his sentence takes one line: his first line cut to the width, then how many more; d or his change shows it whole', () => {
  const o = opened(NOTES_FRAME, FRAME_CHECKED, 'on', PASTED)
  const one = drawn(o, 78)
  assert.equal(one.filter(l => l.includes(LABELS.youSaid) || l.startsWith(' '.repeat(13))).length, 1)
  assert.equal(one[2], `   ${LABELS.youSaid}write me a small cli tool for notes ${LABELS.cutLead}6 ${LABELS.lines[1]}`)
  assert.ok(!one.join('\n').includes('pasted_content') && !one.join('\n').includes('⏎'))
  assert.equal(drawn(opened(NOTES_FRAME, FRAME_CHECKED), 60)[2], `   ${LABELS.youSaid}a small cli app for notes, add saves a note an${LABELS.cut}`)
  const on = at(o, { type: 'focus', stop: 'said' })
  assert.ok(foot(on).includes(`d ${LABELS.keys.whole}`))
  for (const whole of [at(on, { type: 'details' }), at(on, { type: 'press' })]) {
    assert.deepEqual(drawn(whole, 78).slice(2, 9), [` ${LABELS.cursor} ${LABELS.youSaid}write me a small cli tool for notes`,
      '               jot add <text>  saves one note', '               jot list  prints them', '             keep it in one file, no packages',
      '             and make teh list numbered', '             search too maybe', '             that is all'])
  }
  assert.ok(!foot(at(opened(NOTES_FRAME, FRAME_CHECKED, 'on', 'short'), { type: 'focus', stop: 'said' })).includes('d '))
})

test('a contract the check did not settle names its two sides in its question', () => {
  const unsettled = examinedOf({ ...NOTES_CHECKED, contracts: {} })!
  const row = rowsOf(opened(NOTES_SPLIT, unsettled)).find(r => r.id === 'k0')
  assert.deepEqual(row?.notes, [`${LABELS.contractUnsure[0]}store ${LABELS.and} cli${LABELS.contractUnsure[1]}`])
})

// Twelve rows and a hold, eight under review, each with the session's question: taller than a pane of a short terminal.
const MANY = { ...NOTES_FRAME, items: [...Array(12).keys()].map(k => ({ ...NOTES_FRAME.items[0]!, words: `row number ${k} of the list`, ...(k % 3 ? { ask: `Shall I keep row ${k}? OK?` } : {}) })) }
const MANY_STEPS = examinedOf({ marks: [], carried: null, validated: true, steps: Object.fromEntries([...Array(12).keys()].map(k => [String(k), FRAME_CHECKED.steps['0']!])) })!
const shownIn = (sc: Screen, rows: number, top = 0) => {
  const win = fit(sc, rows, top)
  return { lines: plain({ ...sc, lines: win.lines }), top: win.top }
}

test('the whole stands in the pane where it fits, nothing cut and nothing windowed', () => {
  const sc = paneScreen(opened(MANY, MANY_STEPS), 78, 60, 'notes', '', '', false, true)
  assert.deepEqual(fit(sc, 60, 0).lines, sc.lines)
  assert.ok(!footerText(sc.foot).includes(LABELS.keys.page)) // no page to move by
})

test('taller than the pane: the header and the last line stay, the rest is windowed around the cursor, what is out of view counted', () => {
  const rows = 14
  let o = opened(MANY, MANY_STEPS)
  const sc = paneScreen(o, 78, rows, 'notes', '', '', false, true)
  assert.ok(footerText(sc.foot).includes(`${LABELS.keys.page} ${LABELS.keys.pageMeans}`)) // the page keys, where there is a page to move by
  const first = shownIn(sc, rows)
  assert.ok(first.lines.length <= rows, first.lines.join('\n'))
  assert.equal(first.lines[0], ` ${LABELS.name} · ${LABELS.pick} · ${LABELS.checked} · 13 rows · 8 ${LABELS.toReview} · row 2 of 13`)
  assert.deepEqual(first.lines.slice(1, 3), [' notes', '   You said: a small cli app for notes, add saves a note and --list prints th…']) // all above the first under review
  assert.ok(first.lines.some(l => l.startsWith(` ${LABELS.cursor} row number 1 of the list`)))
  assert.ok(new RegExp(`^ ${LABELS.below} \\d+ ${LABELS.more}$`).test(first.lines.at(-2) ?? ''), first.lines.at(-2) ?? '')
  assert.equal(first.lines.at(-1), ` ${footerText(sc.foot)}`)
  for (let k = 0; k < 9; k++) o = at(o, { type: 'move', by: 1 }) // down the list: the window follows, the header stays
  const later = shownIn(paneScreen(o, 78, rows, 'notes', '', '', false, true), rows, first.top)
  assert.ok(later.lines[0]?.endsWith('row 11 of 13'), later.lines[0])
  assert.ok(later.lines.some(l => l.startsWith(` ${LABELS.cursor} row number 10 of the list`)) && later.lines.some(l => l.includes('Shall I keep row 10?')))
  assert.ok(new RegExp(`^ ${LABELS.above} \\d+ ${LABELS.more} · ${LABELS.below} \\d+ ${LABELS.more}$`).test(later.lines.at(-2) ?? ''), later.lines.at(-2) ?? '')
  const ok = shownIn(paneScreen(at(o, { type: 'focus', stop: 'ok' }), 78, rows, 'notes', '', '', false, true), rows, later.top)
  assert.ok(ok.lines.some(l => l.startsWith(` ${LABELS.cursor} ${LABELS.ok}`)))
  assert.ok(new RegExp(`^ ${LABELS.above} \\d+ ${LABELS.more}$`).test(ok.lines.at(-2) ?? ''), ok.lines.at(-2) ?? '')
})

test('page down and page up move the cursor a window’s room of lines, at least a stop, no further than either end', () => {
  const rows = 14
  const o = opened(MANY, MANY_STEPS) // on row number 1
  const sc = paneScreen(o, 78, rows, 'notes', '', '', false, true)
  const down = pageTo(sc, rows, 1)
  const at1 = sc.lines.findIndex(l => l.stop === 'c1')
  const room = rows - 1 - 1 - 1 // the header, the line of what is out of view, and the keys line
  assert.ok(down.lines > 0 && down.lines <= room, String(down.lines))
  assert.equal(sc.lines.findIndex(l => l.stop === down.stop) - at1, down.lines)
  const next = sc.stops[sc.stops.indexOf(down.stop) + 1]!
  assert.ok(sc.lines.findIndex(l => l.stop === next) - at1 > room) // the furthest within the room
  const end = paneScreen(at(o, { type: 'focus', stop: 'ok' }), 78, rows, 'notes', '', '', false, true)
  assert.deepEqual(pageTo(end, rows, 1), { stop: 'ok', lines: 0 })
  const top = paneScreen(at(o, { type: 'focus', stop: 'said' }), 78, rows, 'notes', '', '', false, true)
  assert.deepEqual(pageTo(top, rows, -1), { stop: 'said', lines: 0 })
  assert.equal(pageTo(sc, rows, -1).stop, 'said') // up from the second stop, the first
})

test('the keys line is counted as the pane lays it out: each piece whole, on the next row where this one has no room', () => {
  const o = opened(MANY, MANY_STEPS)
  const sc = paneScreen(o, 60, 14, 'notes', '', '', false, true)
  assert.deepEqual(footPieces(sc), ['y: yes, fine · ', 'enter confirm or change · ', 'd: details · ', 'tab next · ', 'pgup pgdn a page · ', 'h: help · ',
    `esc ${LABELS.keys.close}`])
  // in 59 cells after the margin: y, enter and d (54); tab, pgup and h (40); esc (20)
  const lines = sc.lines.length
  assert.equal(heightOf(sc), lines + 4)
  assert.equal(heightOf(paneScreen(o, 110, 14, 'notes', '', '', false, true)) - paneScreen(o, 110, 14, 'notes', '', '', false, true).lines.length, 2)
  assert.ok(fit(sc, 14, 0).lines.length + 3 <= 14)
})
