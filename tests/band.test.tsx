import { expect, test } from 'claude-code/testing'

const BAND = {
  plugin: 'frame-loop',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: true, rows: 40 },
} as const

// Stands for the engine's store: what a test seeds, and what the band writes.
const seed = (on: any, value: unknown, dismissedAt = 0) => {
  const store: Record<string, { value: unknown; version: number }> = {
    live: { value, version: 1 }, dismissedAt: { value: dismissedAt, version: 1 },
    openedAt: { value: 0, version: 1 }, frame: { value: 3, version: 1 }, off: { value: false, version: 1 } }
  on('state.get', (_: unknown, e: { key: string }) => ({ value: store[e.key] }))
  on('state.set', (_: unknown, e: { key: string; value: unknown }) => {
    const version = (store[e.key]?.version ?? 0) + 1
    store[e.key] = { value: e.value, version }
    return { value: { isSet: true, version } }
  })
  return store
}

test('a wait says what for, how far along, and how much is left, on every surface', async ($, on) => {
  seed(on, { session: 's', at: 1, state: 'reading', what: "checking the change against your requirements",
             why: 'it is a large change', so_far: 'does what you asked', step: 'does it break any of your rules?',
             n: 2, of: 2, started: 1, step_started: 30, answers: 6, expected: 12 })
  on('clock.now', () => ({ value: 60000 }))
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.find({ type: 'Text', text: /because it is a large change/ }))?.text).toContain('0:59')
    expect((await ui.find({ type: 'Text', text: /does what you asked/ }))?.text).toBe('✓ does what you asked · ')
    expect((await ui.find({ type: 'Text', text: /step 2 of 2/ }))?.text).toBe('step 2 of 2: does it break any of your rules?')
    expect((await ui.find({ type: 'Text', text: /answers/ }))?.text).toBe(' · 6 of about 12 answers · about 0:30 left')
    await ui.unmount()
  }
})

test('a reading that rose says it needs the author, until the next prompt', async ($, on) => {
  seed(on, { session: 's', at: 50, state: 'done', decision: 'rise', started: 10, lines: [] })
  on('clock.now', () => ({ value: 60000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /needs you/ }))?.text).toBe('needs you')
  await ui.unmount()
})

test('what the author has seen is gone', async ($, on) => {
  seed(on, { session: 's', at: 50, state: 'done', decision: 'pass', started: 10 }, 51)
  on('clock.now', () => ({ value: 60000 }))
  on('ui.render', ($: any, e: any) => { const { Text } = $.ui.resolve(e); return <Text>engine</Text> })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})

test('the outcome says why in one line, and its details unfold on a press', async ($, on) => {
  const store = seed(on, { session: 's', at: 50, state: 'done', decision: 'rise', started: 10,
             lines: ['frame-loop ▲ needs you: this serves none of your asks'],
             detail: ['frame-loop · turn · step 3 · signal: an area no rule covers (x.py)'] })
  on('clock.now', () => ({ value: 60000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /needs you: this serves none of your asks/ }))?.text)
    .toBe('needs you: this serves none of your asks')
  expect(await ui.find({ type: 'Text', text: /signal/ })).toBeUndefined()
  await ui.press({ key: 'details' })
  expect(store.openedAt?.value).toBe(50)
  const again = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await again.find({ type: 'Text', text: /signal/ }))?.text).toContain('an area no rule covers')
  await again.unmount()
  await ui.unmount()
})

test('a rise after a check mark shows the line that needs the author', async ($, on) => {
  seed(on, { session: 's', at: 50, state: 'done', decision: 'rise', started: null,
             lines: ['frame-loop ✓ checked: nothing in this change needed a closer look',
                     '  ▲ needs you: AGENTS.md: 1 line added; 1 of your rules lost their wording'] })
  on('clock.now', () => ({ value: 60000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /lost their wording/ }))?.text)
    .toBe('needs you: AGENTS.md: 1 line added; 1 of your rules lost their wording')
  await ui.unmount()
})

test('the switch: /frame-loop off writes the project switch', async ($, on) => {
  const store = seed(on, null)
  const written: Record<string, string> = {}
  on('fs.write', (_: unknown, e: { path: string; text: string }) => { written[e.path] = e.text; return { value: undefined } })
  on('command.run', () => ({ text: 'engine' }))
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('env.get', () => ({ value: '/home/u' }))
  on('session.id', () => ({ value: 's' }))
  on('clock.every', () => ({ value: undefined }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  const out = await $.command.run({ command: 'frame-loop', args: 'off' })
  expect(out.text).toBe('frame-loop is off for this project: nothing is checked or read.')
  expect(written).toEqual({ '/proj/.frame-loop/switch': 'off\n' })
  expect(store.off?.value).toBe(true)
})

test('past the usual count, the band never says almost done', async ($, on) => {
  seed(on, { session: 's', at: 1, state: 'reading', what: "checking the change against your requirements",
             step: 'does it do what you asked?', n: 1, of: 2, started: 1, step_started: 30, answers: 40, expected: 36 })
  on('clock.now', () => ({ value: 160000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  const line = (await ui.find({ type: 'Text', text: /answers/ }))?.text ?? ''
  expect(line).toBe(' · 40 answers, more than usual · longer than usual: asked again until the answers agree')
  expect(line.includes('almost done')).toBe(false)
  await ui.unmount()
})

// An act reported, an interrupted check or an outcome the band does not know is never a check mark.
for (const [decision, line] of [['noted', 'frame-loop · Claude pushed to GitHub'],
                                ['interrupted', 'frame-loop · the last check was interrupted'],
                                ['something new', '']] as const) {
  test(`the outcome "${decision}" is never a check mark`, async ($, on) => {
    seed(on, { session: 's', at: 50, state: 'done', decision, started: 10, lines: line ? [line] : [] })
    on('clock.now', () => ({ value: 60000 }))
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    expect(await ui.find({ type: 'Text', text: /✓/ })).toBeFalsy()
    expect((await ui.find({ type: 'Text', text: /^· $/ }))?.text).toBe('· ')
    await ui.unmount()
  })
}

test('the band reads the live folder the settings name', async ($, on) => {
  seed(on, null)
  const read: string[] = []
  on('fs.read', (_: unknown, e: { path: string }) => { read.push(e.path); throw new Error('none yet') })
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'FRAME_LOOP_LIVE' ? '/data/live' : '/home/u' }))
  on('session.id', () => ({ value: 's' }))
  let periods = 0
  on('clock.every', () => (periods++ < 1 ? { value: undefined } : { deny: 'one period' }))  // one period, then stop
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  for (let i = 0; i < 20 && !read.includes('/data/live/s.json'); i++) await new Promise(r => setTimeout(r, 10))
  expect(read).toContain('/data/live/s.json')
})
