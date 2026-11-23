// The Python side's answers and stored files, as the band reads them.
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { argvOf, digestsOf, examinedOf, examineFailure, failure, fieldsText, proposalOf, proposedOf, sameDigests, shownOf, switchedOf, whereOf, writtenOf } from '../../hooks/band/frameloop'
import { LABELS } from '../../hooks/band/labels'

const ran = (stdout: unknown, exitCode = 0, stderr = '') => ({ exitCode, stdout: typeof stdout === 'string' ? stdout : JSON.stringify(stdout), stderr })

test('each verb runs through the plugin’s own launcher, never a python3 of the project’s path', () => {
  assert.deepEqual(argvOf('/the/plugin', 'switch', ['off']), ['/the/plugin/hooks/hand.sh', 'switch', 'off'])
  assert.deepEqual(argvOf('/the/plugin', 'where'), ['/the/plugin/hooks/hand.sh', 'where'])
})

test('where names the folder, or nothing, and why in the sentence it refused with', () => {
  assert.equal(whereOf(ran({ folder: '/m/.frame/claude/app-0123456789abcdef/' })), '/m/.frame/claude/app-0123456789abcdef')
  assert.equal(whereOf(ran({ folder: '/m' }, 1)), '')
  assert.equal(whereOf(ran({ folder: '/m\n/x' })), '')
  assert.equal(whereOf(ran('not json')), '')
  const refused = ran({ folder: null, said: 'A made-up refusal: no repository here.' }, 1)
  assert.equal(whereOf(refused), '')
  assert.equal(failure(refused), 'A made-up refusal: no repository here.')
})

test('propose: faults go back as the answer; a stored one by its id; anything else as a failure', () => {
  assert.deepEqual(proposedOf(ran({ id: 'p1', path: '/x', faults: ['claim 2 says two things', { item: 3 }], said: 'Two faults.' }, 1)), {
    kind: 'faults', text: 'Two faults.\nclaim 2 says two things\n{"item":3}',
  })
  assert.deepEqual(proposedOf(ran({ id: 'p1', path: '/x', faults: [], said: 'Stored.' })), { kind: 'stored', id: 'p1', said: 'Stored.' })
  assert.deepEqual(proposedOf(ran('', 2, 'Traceback: boom\n')), { kind: 'failed', text: 'Traceback: boom' })
  assert.deepEqual(proposedOf(ran({ faults: [] }, 0)), { kind: 'failed', text: '{"faults":[]}' })
  assert.deepEqual(proposedOf(ran('', 3)), { kind: 'failed', text: `${LABELS.exitCode} 3` })
  assert.deepEqual(proposedOf(ran({ id: null, path: null, faults: [], said: 'A made-up refusal.' }, 1)), { kind: 'failed', text: 'A made-up refusal.' })
})

test('propose: rows that look like several claims are faults it marks as such, and a proposal is known again by its fields', () => {
  const back = { id: null, path: null, faults: ['This row may say more than one thing: «a; b».'], several: true, said: 'Not kept yet.' }
  assert.deepEqual(proposedOf(ran(back, 1)), { kind: 'faults', text: 'Not kept yet.\nThis row may say more than one thing: «a; b».', several: true })
  assert.equal(fieldsText({ kind: 'frame', items: [{ words: 'a', of: 'b' }] }), fieldsText({ items: [{ of: 'b', words: 'a' }], kind: 'frame' }))
  assert.notEqual(fieldsText({ items: [{ words: 'a' }, { words: 'b' }] }), fieldsText({ items: [{ words: 'b' }, { words: 'a' }] }))
})

test('approve: its sentence when it wrote, the sentence it refused with, or its words when it failed', () => {
  assert.deepEqual(writtenOf('p1', ran({ written: ['.frame/frame.json'], approved: 2, said: 'I approve two claims.' })), { type: 'written', id: 'p1', said: 'I approve two claims.', closing: '' })
  const refused = { written: [], approved: 0, said: 'Nothing is written: a made-up refusal.' }
  assert.deepEqual(writtenOf('p1', ran(refused, 1)), { type: 'unwritten', id: 'p1', text: refused.said })
  assert.deepEqual(writtenOf('p1', ran(refused, 1, 'a stray warning')), { type: 'unwritten', id: 'p1', text: refused.said })
  assert.deepEqual(writtenOf('p1', ran('', 1, 'locked')), { type: 'unwritten', id: 'p1', text: 'locked' })
  assert.deepEqual(writtenOf('p1', ran({ written: [] })), { type: 'unwritten', id: 'p1', text: '{"written":[]}' })
})

test('switch: its sentence, the sentence it refused with, or why it could not run', () => {
  assert.equal(switchedOf(ran({ switch: 'off', said: 'The reading is off here.' })), 'The reading is off here.')
  assert.equal(switchedOf(ran({ switch: 'off', said: 'A made-up refusal inside a hook.' }, 1)), 'A made-up refusal inside a hook.')
  assert.equal(switchedOf(ran('', 1, 'no module named frameloop')), `${LABELS.cannotRun} no module named frameloop`)
})

test('a stored proposal of any shape reads as texts and lists', () => {
  assert.equal(proposalOf(null, 'x'), null)
  assert.equal(proposalOf([1], 'x'), null)
  const p = proposalOf({ title: 7, items: [{ words: ['a', 'b'], step: 'one step' }, 'not an item'], holds: 'none', split: { parts: [{ place: 'src/a' }], holes: 'none' }, options: [{}] }, 'x')
  assert.deepEqual(p, {
    id: 'x', kind: '', place: '', title: '7',
    items: [
      { words: '["a","b"]', of: '', narrows: '', owner: '', step: ['one step'], reversal: null, predicts: '', old: '', ask: '' },
      { words: '', of: '', narrows: '', owner: '', step: [], reversal: null, predicts: '', old: '', ask: '' },
    ],
    holds: [], split: { parts: [{ place: 'src/a', items: [], holds: [] }], holes: [], contracts: [] }, options: [{ words: '', cost: '' }], reason: null,
  })
})

test('a crossing reads each part with its own claims and holds, and a contract with no check yet as none', () => {
  const p = proposalOf({ kind: 'split', items: [{ words: 'C' }], split: {
    parts: [{ place: 'store', items: [{ words: 'S', narrows: { place: '', words: 'C' } }], holds: [{ words: 'It builds.', command: 'make' }] }, 'cli'],
    holes: [{ claim: 'C', from: ['store'], kind: 'fulfils' }],
    contracts: [{ id: 'N-1', words: 'w', provides: 'store', depends: ['cli'], command: null }],
  } }, 'x')
  assert.deepEqual(p?.split?.parts, [
    { place: 'store', items: [{ words: 'S', of: '', narrows: 'C', owner: '', step: [], reversal: null, predicts: '', old: '', ask: '' }],
      holds: [{ words: 'It builds.', detail: 'make', byCommand: true }] },
    { place: 'cli', items: [], holds: [] },
  ])
  assert.equal(p?.split?.contracts[0]?.command, '')
})

test('show answers the switch of the check it read, and examine a failure where it could not run', () => {
  const proposal = { kind: 'frame', place: '', title: 'T', items: [{ words: 'W' }], holds: [], split: null, options: null, reason: null }
  assert.equal(shownOf(ran({ proposal, examined: null, shown: 'a:none', check: 'on' }), '1')?.check, 'on')
  assert.equal(shownOf(ran({ proposal, examined: null, shown: 'a:none' }), '1')?.check, 'off') // anything else: off
  assert.equal(examineFailure(ran({ examined: {}, said: 'checked' })), '')
  assert.equal(examineFailure(ran({ examined: null, said: 'A made-up refusal.' }, 1)), 'A made-up refusal.')
  assert.equal(examineFailure(ran('', 1, 'killed after 600000 ms')), 'killed after 600000 ms')
})

test('an examination absent is none; present, its marks and whether the parts carry', () => {
  assert.equal(examinedOf(null), null)
  assert.deepEqual(examinedOf({ marks: [{ item: '1', kind: 'gap', words: 'w' }], carried: 'yes', validated: 'true' }), {
    above: {}, contracts: {}, marks: [{ item: -1, kind: 'gap', words: 'w' }], carried: null, validated: false, steps: {}, failed: '',
  })
  assert.deepEqual(examinedOf({ marks: [], carried: false, validated: true }), { above: {}, contracts: {}, marks: [], carried: false, validated: true, steps: {}, failed: '' })
  assert.equal(examinedOf({ marks: [], steps: {}, failed: 'The check could not run: a made-up reason.' })?.failed, 'The check could not run: a made-up reason.')
  const crossing = examinedOf({ above: { '0': { carried: true, carry: ['store'], idle: ['cli'] }, '1': { carried: 1 }, x: {} }, contracts: { '0': false, '1': 'yes' } })
  assert.deepEqual(crossing?.above, { '0': { carried: true, carry: ['store'], idle: ['cli'] }, '1': { carried: null, carry: [], idle: [] } })
  assert.deepEqual(crossing?.contracts, { '0': false, '1': null })
})

test('an examination’s steps read as each item’s pair by its index, whatever their shape', () => {
  const steps = {
    '0': { maker: 'private-1', lines: ['1. A client is one caller.'], reversal: { words: 'It is not so that X', lines: ['1. One count for all.'] } },
    '1': { maker: 'private-1', lines: 'one line' },
    'x': { lines: ['not an item'] },
    '2': 'no step',
  }
  assert.deepEqual(examinedOf({ marks: [], carried: null, validated: true, steps })?.steps, {
    '0': { lines: ['1. A client is one caller.'], reversal: { words: 'It is not so that X', lines: ['1. One count for all.'] } },
    '1': { lines: ['one line'], reversal: null },
    '2': { lines: [], reversal: null },
  })
  const p = proposalOf({ items: [{ words: 'X', step: { maker: 'm', lines: ['a'], reversal: { words: 'It is not so that X', lines: ['b'] } } }] }, 'x')
  assert.deepEqual(p?.items[0]?.reversal, { words: 'It is not so that X', lines: ['b'] })
})

test('the digests the band keeps as a witness: read from a good answer alone, and held the same in any order', () => {
  const d = { 'approved.json': 'a1', switch: null }
  assert.deepEqual(digestsOf(ran({ digests: d })), d)
  for (const bad of [ran({ digests: d }, 1), ran({ digests: [1] }), ran({ digests: { switch: 3 } }), ran('not json'), ran({})])
    assert.equal(digestsOf(bad), null)
  assert.equal(sameDigests({ switch: null, 'approved.json': 'a1' }, d), true)
  for (const other of [{ 'approved.json': 'a2', switch: null }, { 'approved.json': 'a1' }, null, 'a1', undefined])
    assert.equal(sameDigests(other, d), false)
})
