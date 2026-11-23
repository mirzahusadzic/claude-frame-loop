// The line above the prompt, and the /frame-loop command.
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { LABELS } from '../../hooks/band/labels'
import { commandOf, commandText, isEnded, isPlain, isQuiet, lineOf, nowText, restText, STALE_SECONDS, tokensShort } from '../../hooks/band/line'

const live = (line: unknown, tension: unknown, more: Record<string, unknown> = {}) => JSON.stringify({ line, tension, at: 1, ...more })
// The line a real turn left on the old band, which counted twice, named files and showed naughts.
const TURN = "frame-loop: the work changed in the root, cli, store · 1 held · in no claim's place: tests/__init__.py, tests/test_cli.py, tests/test_contract_notes_v1.py and 1 more · of 4 the change bears on: 1 fulfilled, 3 open"
const TYPICAL = live(TURN, { open: 5, fulfilled: 1, rest: 0, refused: 0 }, { flags: { outside: 3 } })
const NOW = { said: 'checking 2 of 5', began: 1000, at: 1040, until: 1600, writer: 0, maker: 3, records: 12, tokens: 8214 }

test('at rest, the tree counted once with its total, naughts and files left out, and what needs the eye counted', () => {
  assert.equal(restText(lineOf(TYPICAL)), `${LABELS.name} · 1 ${LABELS.of} 6 ${LABELS.counts.fulfilled} · 3 ${LABELS.flags.outside[1]}`)
  assert.equal(restText(lineOf(TYPICAL)), 'frame-loop · 1 of 6 passed · 3 files nobody asked for')
  const never = restText(lineOf(live('frame-loop: the work changed in the root · 1 held', { open: 5 }, { flags: { nostep: 5 } })))
  assert.equal(never, 'frame-loop · 0 of 5 passed · 5 not checked: no step')
})

test('the resting line is short, holds no file name, no naught, and no sentence of the turn', () => {
  const drawn = restText(lineOf(TYPICAL))
  assert.ok(drawn.length <= 80, `${drawn.length}: ${drawn}`)
  assert.doesNotMatch(drawn, /\.py\b|\//)
  assert.doesNotMatch(drawn, /(^|\s)0 (?!of )/)
  assert.doesNotMatch(drawn, /changed in|held|bears on/)
  const all = restText(lineOf(live('', { open: 1, fulfilled: 2, rest: 1, refused: 1 }, { flags: { off: 2, opened: 1, outside: 4, unchecked: 1, failing: 2 } })))
  for (const piece of [`2 ${LABELS.flags.off[1]}`, `1 ${LABELS.flags.opened[0]}`, `4 ${LABELS.flags.outside[1]}`, `1 ${LABELS.flags.unchecked[0]}`, `2 ${LABELS.flags.failing[1]}`])
    assert.ok(all.includes(` · ${piece}`), piece)
})

test('the band counts in one form alone, and never in the turn’s', () => {
  for (const tension of [{ open: 5, fulfilled: 1 }, { open: 0, fulfilled: 3 }, { open: 2, fulfilled: 1, rest: 1, refused: 1 }, { open: 4 }]) {
    const drawn = restText(lineOf(live(TURN, tension)))
    assert.equal(drawn.match(/\d+ of \d+ /g)?.length, 1, drawn)
    assert.doesNotMatch(drawn, /the change bears on|: \d/)
  }
})

test('the numbers the band draws add up to its total', () => {
  const states = [
    { open: 5, fulfilled: 1, rest: 0, refused: 0 }, { open: 0, fulfilled: 6, rest: 0, refused: 0 },
    { open: 2, fulfilled: 1, rest: 2, refused: 0 }, { open: 0, fulfilled: 0, rest: 1, refused: 3 }, { open: 7, fulfilled: 0, rest: 0, refused: 0 },
  ]
  for (const tension of states) {
    const pieces = restText(lineOf(live('', tension))).split(' · ').slice(1)
    const [head = '', ...rest] = pieces
    const [fulfilled, total] = (head.match(/^(\d+) of (\d+) /)?.slice(1) ?? []).map(Number)
    const named = Object.fromEntries(rest.map(piece => [piece.replace(/^\d+ /, ''), Number(piece.split(' ')[0])]))
    const open = named[LABELS.counts.open] ?? (total ?? 0) - (fulfilled ?? 0) // left out only where it is all the rest
    if (named[LABELS.counts.open] === undefined) assert.equal((named[LABELS.counts.rest] ?? 0) + (named[LABELS.counts.refused] ?? 0), 0, head)
    assert.equal((fulfilled ?? 0) + open + (named[LABELS.counts.rest] ?? 0) + (named[LABELS.counts.refused] ?? 0), total, JSON.stringify(tension))
  }
})

test('no two numbers ever stand next to each other in the band’s line', () => {
  const lines = [
    live(TURN, { open: 5, fulfilled: 0, rest: 0, refused: 0 }, { flags: { nostep: 5 } }),
    live('frame-loop: the work changed in the root · 1 held · open, not read: 5', { open: 5 }, { flags: { off: 5, outside: 12 } }),
    live('', { open: 1, fulfilled: 22, rest: 3, refused: 4 }, { flags: { unchecked: 2, failing: 1 } }),
  ]
  for (const text of lines) assert.doesNotMatch(restText(lineOf(text)), /\d[\s,]+\d/)
  assert.doesNotMatch(nowText({ ...NOW, writer: 2 }, 1047), /\d \d/)
})

test('nothing with no frame, nothing running and nothing to alert, with no file, or with one in mid-write', () => {
  for (const text of ['', '{"line": "x", "tens', live('A line.', { open: 0, fulfilled: 0, rest: 0, refused: 0 }), live('A line.', null), 'null'])
    assert.equal(isQuiet(lineOf(text)), true, text)
  assert.equal(isQuiet(lineOf(live('', {}, { now: NOW }))), false) // an examination before any frame
  assert.equal(isQuiet(lineOf(live('', {}, { alert: 'frame-loop could not do its part.' }))), false)
})

test('a count that is not a count reads as naught; a line with a break stays one line', () => {
  const l = lineOf(live('one\ntwo\u001b[31m', { open: '3', fulfilled: -2, rest: 1.7, refused: Infinity }, { flags: { outside: 'x' } }))
  assert.deepEqual([l.line, l.counts, l.flags], ['one ⏎ two�[31m', [0, 0, 1, 0], [0, 0, 0, 0, 0, 0]])
})

test('while a run goes on: a spinner frame that moves each second, what runs, its seconds and what it spent so far', () => {
  const l = lineOf(live(TURN, { open: 1 }, { now: NOW }))
  assert.equal(nowText(l.now!, 1047), `${LABELS.spinner[7]} ${LABELS.name} · 47 ${LABELS.seconds} · 8.2${LABELS.thousands} ${LABELS.spend.tokens} · checking 2 of 5`)
  assert.equal(nowText(l.now!, 1047), '⠧ frame-loop · 47 s · 8.2k tokens · checking 2 of 5')
  assert.notEqual(nowText(l.now!, 1048).split(' ')[0], nowText(l.now!, 1047).split(' ')[0])
  const first = nowText({ ...NOW, maker: 0, records: 0, tokens: null, writer: 1 }, 1000)
  assert.equal(first, `${LABELS.spinner[0]} ${LABELS.name} · 0 ${LABELS.seconds} · 1 ${LABELS.spend.calls[0]} · checking 2 of 5`) // no tokens known: the calls
  assert.equal(nowText({ ...NOW, maker: 0, records: 0, tokens: null }, 1000), `${LABELS.spinner[0]} ${LABELS.name} · 0 ${LABELS.seconds} · checking 2 of 5`) // no naught
  assert.match(nowText({ ...NOW, at: 1095 }, 1100), / · 1 m 40 s · /) // past a minute, in minutes
  // what runs comes last, so a cut at the end of the line takes the quoted words and never a count
  const quoted = nowText({ ...NOW, said: 'checking 3 of 5: «A note longer than 200 characters is refused with a message.»' }, 1047)
  assert.equal(quoted, '⠧ frame-loop · 47 s · 8.2k tokens · checking 3 of 5: «A note longer than 200 characters is refused with a message.»')
  assert.ok(quoted.indexOf('8.2k') < quoted.indexOf('«'))
})

test('tokens in short, one form everywhere: as they are below a thousand, in thousands with one decimal, then millions', () => {
  const cases: [number, string][] = [[0, '0'], [842, '842'], [999, '999'], [1000, '1.0k'], [8200, '8.2k'], [9949, '9.9k'], [9950, '10.0k'],
    [57300, '57.3k'], [422300, '422.3k'], [999949, '999.9k'], [999950, '1m'], [1000000, '1m'], [1250000, '1.3m'], [12340000, '12.3m']]
  for (const [k, said] of cases) assert.equal(tokensShort(k), said, String(k))
})

test('at rest the line ends with what the checks of this session spent, and draws nothing of a spend of naught', () => {
  assert.equal(restText(lineOf(live('', { open: 5, fulfilled: 1 }, { spent: { tokens: 175000, calls: 40 } }))), 'frame-loop · 1 of 6 passed · 175.0k tokens')
  assert.equal(restText(lineOf(live('', { open: 5, fulfilled: 1 }, { spent: { tokens: 0, calls: 12 } }))), 'frame-loop · 1 of 6 passed · 12 model calls')
  for (const spent of [{ tokens: 0, calls: 0 }, {}, { tokens: -3, calls: 'x' }]) {
    const drawn = restText(lineOf(live('', { open: 5, fulfilled: 1 }, { spent })))
    assert.equal(drawn, 'frame-loop · 1 of 6 passed', JSON.stringify(spent))
  }
  assert.equal(isQuiet(lineOf(live('', {}, { spent: { tokens: 0, calls: 0 } }))), true)
  assert.equal(isQuiet(lineOf(live('', {}, { spent: { tokens: 900, calls: 3 } }))), false)
})

test('a run whose hook went silent, or passed its limit, ends without a word', () => {
  assert.equal(isEnded(NOW, NOW.at + STALE_SECONDS), false)
  assert.equal(isEnded(NOW, NOW.at + STALE_SECONDS + 1), true)
  assert.equal(isEnded({ ...NOW, at: 1599 }, 1601), true)
  assert.equal(nowText(NOW, NOW.at + STALE_SECONDS + 1), `${LABELS.name} · ${NOW.said} · ${LABELS.ended}`)
  assert.equal(lineOf(live('', {}, { now: { ...NOW, began: 'soon' } })).now, null) // what is not in its form is nothing
})

test('/frame-loop shows the whole state: every count, the alert, the last sentence and what runs', () => {
  const whole = commandText(lineOf(TYPICAL), 0).split('\n')
  assert.deepEqual(whole, [`${LABELS.name} · 1 ${LABELS.of} 6 ${LABELS.counts.fulfilled} · 5 ${LABELS.counts.open} · 0 ${LABELS.counts.rest} · 0 ${LABELS.counts.refused} · 3 ${LABELS.flags.outside[1]}`, TURN])
  const running = commandText(lineOf(live('A line.', { open: 1 }, { now: NOW, alert: 'frame-loop: a hand changed it.' })), 1047).split('\n')
  assert.deepEqual(running.slice(1), ['frame-loop: a hand changed it.', 'A line.', nowText(NOW, 1047)])
})

test('/frame-loop on and off switch only by the person’s hand', () => {
  assert.deepEqual(commandOf('', false), { kind: 'show' })
  assert.deepEqual(commandOf(' OFF ', true), { kind: 'switch', to: 'off' })
  assert.deepEqual(commandOf('on', true), { kind: 'switch', to: 'on' })
  assert.deepEqual(commandOf('off', false), { kind: 'say', text: LABELS.personOnly })
  assert.deepEqual(commandOf('review', true), { kind: 'say', text: LABELS.usage })
})

test('a session id names a file only when it is plain', () => {
  assert.equal(isPlain('5d608460-dcb6-f138'), true)
  for (const id of ['', '../escape', 'a/b', 'a.json', 'x'.repeat(129)]) assert.equal(isPlain(id), false, id)
})

test('a line is never drawn with the word ready, whatever a file says', () => {
  const l = lineOf(JSON.stringify({ line: 'frame-loop: the work changed in web · 3 held · ready: nothing under the frame is open', tension: { open: 0 } }))
  assert.equal(l.line, 'frame-loop: the work changed in web · 3 held')
})
