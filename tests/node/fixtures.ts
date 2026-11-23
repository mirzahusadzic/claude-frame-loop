// Proposals as the Python side stores them, read back as the band reads them, and the picker's states built from
// them with no host.
import { readFileSync } from 'node:fs'

import { examinedOf, proposalOf } from '../../hooks/band/frameloop'
import { EMPTY, step } from '../../hooks/band/picker'
import type { Event } from '../../hooks/band/picker'
import type { Examined, Open, Picker, Proposal } from '../../types'

const SENTENCE = 'Requests are counted per client and reset each day.'

export const FRAME_FILE = {
  id: 'p1', kind: 'frame', place: '', title: 'Frame 0: the rate limit',
  items: [
    { words: 'Requests are counted for each client.', of: SENTENCE, narrows: null, owner: 'work',
      step: { maker: 'private-1', lines: ['a count kept per client id'] }, predicts: 'fulfilled', old: null },
    { words: 'The counts reset each day.', of: SENTENCE, narrows: null, owner: 'work', step: null, predicts: 'fulfilled', old: null },
    { words: 'Over the limit, the API answers 429.', of: 'Over the limit, callers are told so.', narrows: null, owner: 'work', step: null, predicts: '', old: null },
  ],
  holds: [{ words: 'The tests pass.', command: 'python3 -m unittest' }, { words: 'Payments stay untouched.', untouched: ['src/pay/**'] }],
  split: null, options: null, reason: null,
}

// A crossing of src/api into its two parts, each with its own claim, as one proposal.
export const SPLIT_FILE = {
  id: 'p2', kind: 'split', place: 'src/api', title: 'Split: src/api',
  items: [
    { words: 'Requests are counted for each client.', of: SENTENCE, narrows: { place: '', words: 'Requests are counted per client.' }, owner: 'parts',
      step: { maker: 'private-1', lines: ['count', 'per client'] }, predicts: 'fulfilled', old: null },
  ],
  holds: [],
  split: {
    parts: [
      { place: 'src/api/limits', items: [{ words: 'Limits count each client.', of: SENTENCE, narrows: { place: 'src/api', words: 'Requests are counted for each client.' },
        owner: 'work', step: { maker: 'm', lines: ['a limit per client'] }, predicts: 'fulfilled', old: null }],
        holds: [{ words: 'The limits tests pass.', command: 'python3 -m unittest discover -s src/api/limits' }] },
      { place: 'src/api/auth', items: [{ words: 'Auth names the client.', of: SENTENCE, narrows: { place: 'src/api', words: 'Requests are counted for each client.' },
        owner: 'work', step: null, predicts: 'fulfilled', old: null }], holds: [] },
    ],
    holes: [{ claim: 'Requests are counted for each client.', from: ['src/api/limits', 'src/api/auth'], kind: 'fulfils' }],
    contracts: [{ id: 'CLIENT-ID-V1', words: 'A client id is a string.', provides: 'src/api/auth', depends: ['src/api/limits'], command: 'true' }],
  },
  options: null, reason: null,
}

export const REFRAME_FILE = {
  id: 'p3', kind: 'reframe', place: '', title: 'Reframe',
  items: [{ words: 'The counts reset at midnight UTC.', of: SENTENCE, old: 'The counts reset each day.' }],
  holds: [], split: null, options: null,
  reason: { words: 'A reading found "each day" cannot be met: there is no clock here.', about: 'The counts reset each day.' },
}

export const OPTIONS_FILE = {
  id: 'p4', kind: 'options', place: '', title: 'Which limit?',
  items: [{ words: 'A limit.', of: SENTENCE }],
  holds: [], split: null, reason: null,
  options: [{ words: 'Per minute', cost: 'a timer' }, { words: 'Per day', cost: 'a clock' }],
}

// The settled sketch's crossing: the notes app split into store and cli, with the person's own sentence.
export const SAID = 'a small cli app for notes, add saves a note and --list prints them numbered'
const it = (words: string, narrows: unknown = null, owner = 'work') => ({ words, of: SAID, narrows, owner, step: null, predicts: 'fulfilled', old: null })
const ADD = 'add saves a note'
const LIST = '--list prints them numbered'
export const NOTES_SPLIT = {
  id: '3', kind: 'split', place: '', title: 'notes: store and cli', holds: [], options: null, reason: null,
  items: [it(ADD, null, 'parts'), it(LIST, null, 'parts')],
  split: {
    parts: [
      { place: 'store', items: [it('keeps each note it is given', { place: '', words: ADD }), it('gives them back in the order added', { place: '', words: LIST })], holds: [] },
      { place: 'cli', items: [it('add hands its note to the store', { place: '', words: ADD }), it('--list prints the notes, numbered from 1', { place: '', words: LIST })], holds: [] },
    ],
    holes: [{ claim: ADD, from: ['store', 'cli'], kind: 'fulfils' }, { claim: LIST, from: ['store', 'cli'], kind: 'fulfils' }],
    contracts: [{ id: 'NOTES-V1', words: 'one check that runs both sides', provides: 'store', depends: ['cli'], command: 'python3 -m unittest' }],
  },
}
const PAIR = { maker: 'private-1', lines: ['1. A note is kept.'], reversal: { words: 'It is not so that x', lines: ['1. A note is lost.'] } }
const stepsFor = (n: number) => Object.fromEntries([...Array(n).keys()].map(k => [String(k), PAIR]))
export const IDLE = 'this would hold even without the store. OK?'
// The check as it found the sketch: every claim with its step, the parts carrying both claims above, the second
// held without the store, and the contract kept.
export const NOTES_CHECKED = examinedOf({
  marks: [{ item: 1, kind: 'idle', words: IDLE }], carried: true, validated: true, steps: stepsFor(6),
  above: { '0': { carried: true, carry: ['store', 'cli'], idle: [] }, '1': { carried: true, carry: ['cli'], idle: ['store'] } }, contracts: { '0': true },
})!
// A proposal with no split and two rows under review: one the check asks about, one the session asks about itself.
export const NOTES_FRAME = {
  id: '4', kind: 'frame', place: '', title: 'notes', split: null, options: null, reason: null,
  holds: [{ words: 'the tests pass', command: 'python3 -m unittest' }],
  items: [it('add saves the note it is given'), it('--list prints every note, numbered from 1'),
    { ...it('a note is one line of text'), ask: 'You did not say a note is one line; I would keep it to one. OK?' }],
}
// The brief's sketch: one row seen in the work, one the check says only a test can show, and two holds a command
// checks, the second row's mark the tool's own.
export const UNSEEN = 'Only a test can show this, and it has no command. OK as it is?'
export const NOTES_ROADS = {
  id: '5', kind: 'frame', place: '', title: 'notes', split: null, options: null, reason: null,
  items: [it('The list option prints each saved note on its own line'), it('Notes are kept between runs')],
  holds: [{ words: 'The store is the tool\'s own code', command: 'python3 check_imports.py' },
    { words: 'The round-trip tests pass', command: 'python3 -m unittest test_notes' },
    { words: 'Payments stay untouched', untouched: ['src/pay/**'] }],
}
export const ROADS_CHECKED = examinedOf({ marks: [{ item: 1, kind: 'unseen', words: UNSEEN }], carried: null, validated: true, steps: stepsFor(2) })!
export const ALONE = 'this may lean on another row and not stand on its own. OK?'
export const FRAME_CHECKED = examinedOf({ marks: [{ item: 1, kind: 'alone', words: ALONE }], carried: null, validated: true, steps: stepsFor(3) })!
export const GADFLY = 'Gadfly is not installed, as there is no gadfly command'
export const FAILED = examinedOf({
  marks: [0, 1, 2].map(item => ({ item, kind: 'unread', words: `could not be checked: ${GADFLY}.` })), carried: null, validated: false,
  steps: {}, failed: `The check could not run: ${GADFLY}.`,
})!

// A split exactly as the Python side keeps it, each hole naming its claim by its words: tests/test_proposal.py
// holds this same file to what propose keeps.
export const KEPT_SPLIT: { id: string; split: { parts: { place: string }[]; holes: { claim: string; from: string[]; kind: string }[] } } =
  JSON.parse(readFileSync(new URL('./kept-split.json', import.meta.url), 'utf-8'))

// A proposal as stored: its id, and any other field read as the band reads it.
export type Raw = { id: string; [field: string]: unknown }
export const read = (raw: Raw): Proposal => {
  const p = proposalOf(raw, raw.id)
  if (!p) throw new Error('not a proposal')
  return p
}
// A proposal opened in the picker, as `show` would give it: its examination, the switch, and the person's sentence.
export const proposed = (raw: Raw, examined: Examined | null = null, check: 'on' | 'off' = 'on', said = SAID): Event =>
  ({ type: 'proposed', id: raw.id, proposal: read(raw), examined, shown: `shown-${raw.id}:x`, check, said, at: 100 })
export const run = (events: Event[], from: Picker = EMPTY) =>
  events.reduce((at, e) => {
    const next = step(at.state, e)
    return { state: next.state, effects: [...at.effects, ...next.effects] }
  }, { state: from, effects: [] as ReturnType<typeof step>['effects'] })
export const opened = (raw: Raw, examined: Examined | null = null, check: 'on' | 'off' = 'on', said = SAID): Open => {
  const o = run([proposed(raw, examined, check, said)]).state.open
  if (!o) throw new Error('not opened')
  return o
}
