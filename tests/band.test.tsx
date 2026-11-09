import { expect, test } from 'claude-code/testing'

const BAND = {
  plugin: 'frame-loop',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: true, rows: 40 },
} as const

// A path as the engine reports it on any system: Windows gives D:\\proj\\x for /proj/x.
const posix = (path: string) => path.replace(/^[A-Za-z]:/, '').replace(/\\/g, '/')

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

test('a wait is one live line: what is happening, the time left and the tokens, on every surface', async ($, on) => {
  seed(on, { session: 's', at: 1, state: 'reading', what: 'checking the change',
             why: 'it is a large change', step: 'does it break any of your rules?',
             n: 2, of: 2, started: 1, step_started: 30, answers: 6, expected: 12, tokens: 12400 })
  on('clock.now', () => ({ value: 60000 }))
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.find({ type: 'Text', text: /checking the change/ }))?.text).toBe('checking the change')
    expect((await ui.find({ type: 'Text', text: /tokens/ }))?.text).toBe(' · about 0:30 left · 12k tokens')
    expect(await ui.find({ type: 'Text', text: /because|step 2 of 2|answers/ })).toBeFalsy()
    await ui.unmount()
  }
})

test('a wait moves, and shows no tokens before the first is spent', async ($, on) => {
  seed(on, { session: 's', at: 1, state: 'reading', what: 'checking the change', started: 1 })
  on('clock.now', () => ({ value: 60000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^[◐◓◑◒] $/ }))?.text).toBeTruthy()
  expect((await ui.find({ type: 'Text', text: /0:59/ }))?.text).toBe(' · 0:59')
  await ui.unmount()
})

test('well past the usual count, the band says still asking and guesses no time left', async ($, on) => {
  seed(on, { session: 's', at: 1, state: 'reading', what: 'checking the change',
             started: 1, step_started: 30, answers: 32, expected: 24, tokens: 130000 })
  on('clock.now', () => ({ value: 94000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /still asking/ }))?.text).toBe('still asking')
  expect((await ui.find({ type: 'Text', text: /tokens/ }))?.text).toBe(' · 1:33 · 130k tokens')
  await ui.unmount()
})

// Once a reading has ended, only what needs the author stays, until the next prompt.
for (const decision of ['pass', 'quiet', 'noted', 'unsettled', 'interrupted', 'something new']) {
  test(`once a reading has ended, "${decision}" shows nothing`, async ($, on) => {
    seed(on, { session: 's', at: 50, state: 'done', decision, started: 10, tokens: 84000,
               lines: ['frame-loop · a line'], detail: ['a detail'] })
    on('clock.now', () => ({ value: 60000 }))
    on('ui.render', ($: any, e: any) => { const { Text } = $.ui.resolve(e); return <Text>engine</Text> })
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
    await ui.unmount()
  })
}

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

// The hooks read the switch under CLAUDE_PROJECT_DIR when it names a folder that is there,
// else under the session's directory: the band writes it where they read it.
for (const [why, projectDir, where] of [['no project folder is named', undefined, '/proj'],
                                        ['the project folder is named', '/project', '/project'],
                                        ['the folder named is not there', '/gone', '/proj']] as const) {
  test(`the switch: /frame-loop off writes the project switch when ${why}`, async ($, on) => {
    const store = seed(on, null)
    const written: Record<string, string> = {}
    on('fs.write', (_: unknown, e: { path: string; text: string }) => { written[posix(e.path)] = e.text; return { value: undefined } })
    on('fs.exists', (_: unknown, e: { path: string }) => ({ value: posix(e.path) === '/project' }))
    on('command.run', () => ({ text: 'engine' }))
    on('command.register', () => ({ value: { command: 'frame-loop' } }))
    on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'CLAUDE_PROJECT_DIR' ? projectDir : '/home/u' }))
    on('session.id', () => ({ value: 's' }))
    on('clock.every', () => ({ value: undefined }))
    on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
    await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
    const out = await $.command.run({ command: 'frame-loop', args: 'off' })
    expect(out.text).toBe('frame-loop is off for this project: nothing is checked or read.')
    expect(written).toEqual({ [`${where}/.frame-loop/switch`]: 'off\n' })
    expect(store.off?.value).toBe(true)
  })
}

// Seen: a reload left the band with only the current folder, and `/frame-loop on` said "on"
// for a switch the hooks never read. What the hooks say for this session decides.
test('the switch: /frame-loop writes where the hooks say they read it', async ($, on) => {
  const store = seed(on, null)
  const written: Record<string, string> = {}
  on('fs.write', (_: unknown, e: { path: string; text: string }) => { written[posix(e.path)] = e.text; return { value: undefined } })
  on('fs.exists', () => ({ value: false }))
  on('fs.read', (_: unknown, e: { path: string }) => {
    if (posix(e.path).endsWith('/s.project')) return { value: '/started\n' }
    throw new Error('no file')
  })
  on('command.run', () => ({ text: 'engine' }))
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.id', () => ({ value: 's' }))
  on('clock.every', () => ({ value: undefined }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/somewhere-else', surface: 'terminal', isInteractive: true })
  await $.command.run({ command: 'frame-loop', args: 'on' })
  expect(written).toEqual({ '/started/.frame-loop/switch': 'on\n' })
  expect(store.off?.value).toBe(false)
})

test('past the usual count, the band claims no disagreement and never almost done', async ($, on) => {
  seed(on, { session: 's', at: 1, state: 'reading', what: 'checking the change',
             started: 1, step_started: 30, answers: 40, expected: 36, tokens: 95000 })
  on('clock.now', () => ({ value: 66000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /still asking/ }))?.text).toBe('still asking')
  expect(await ui.find({ type: 'Text', text: /disagree/ })).toBeFalsy()
  expect((await ui.find({ type: 'Text', text: /tokens/ }))?.text).toBe(' · 1:05 · 95k tokens')
  expect(await ui.find({ type: 'Text', text: /almost done/ })).toBeFalsy()
  await ui.unmount()
})

test('a reading that could not be done says so, until the next prompt', async ($, on) => {
  seed(on, { session: 's', at: 50, state: 'done', decision: 'block', started: 10,
             lines: ['frame-loop ■ not read: it looks like it holds a secret'] })
  on('clock.now', () => ({ value: 60000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /not read/ }))?.text).toBe('not read: it looks like it holds a secret')
  await ui.unmount()
})

test('the band reads the live folder the settings name', async ($, on) => {
  seed(on, null)
  const read: string[] = []
  on('fs.read', (_: unknown, e: { path: string }) => { read.push(posix(e.path)); throw new Error('none yet') })
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

test('after /clear or a resume, the band shows the new session, never the last one', async ($, on) => {
  const store = seed(on, null)
  const files: Record<string, unknown> = {
    '/home/u/.claude/frame-loop/live/old.json': { session: 'old', at: 50, state: 'done', decision: 'pass', started: 10 },
    '/home/u/.claude/frame-loop/live/new.json': { session: 'new', at: 55, state: 'done', decision: 'rise', started: 52,
                                                  lines: ['frame-loop ▲ needs you: the new session'] },
  }
  on('fs.read', (_: unknown, e: { path: string }) => {
    const file = files[posix(e.path)]
    if (file === undefined) throw new Error('no such file')
    return { value: JSON.stringify(file) }
  })
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  let session = 'old'
  on('session.id', () => ({ value: session }))
  let periods = 0
  on('clock.every', () => {
    periods++
    if (periods === 3) session = 'new' // the hooks now write the new session's file
    return periods <= 5 ? { value: undefined } : { deny: 'enough periods' }
  })
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('clock.now', () => ({ value: 60000 }))
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  const shown = () => (store.live?.value as { session?: string } | null)?.session
  for (let i = 0; i < 50 && shown() !== 'new'; i++) await new Promise(r => setTimeout(r, 10))
  expect(shown()).toBe('new')
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /needs you/ }))?.text).toBe('needs you: the new session')
  await ui.unmount()
})

// The picker: a decomposition approved item by item, the answer on the record.
const PICKER = {
  plugin: 'frame-loop',
  component: 'Pane',
  requestId: 'approve',
  props: { title: 'Approve', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 20 }, view: {} },
} as const

const PROPOSED = {
  tool: 'mcp__frame-loop__approve',
  title: 'Approve frame 0',
  items: [{ text: 'Each client is limited per minute.' }, { text: 'Over the limit, the API returns 429.', detail: 'may change: limits' }],
  leftOut: ['Limits per endpoint.'],
}

const picking = async ($: any, on: any, placed = true) => {
  const sent: { submit?: string; fill?: string; closed?: boolean; opened?: any; files: Record<string, string> } = { files: {} }
  on('ui.open', (_: unknown, e: any) => {
    sent.opened = e
    return { value: placed ? { isPlaced: true } : { isPlaced: false, reason: 'too narrow' } }
  })
  on('ui.close', () => { sent.closed = true; return { value: undefined } })
  on('prompt.submit', (_: unknown, e: any) => { sent.submit = e.text; return { text: e.text } })
  on('prompt.fill', (_: unknown, e: any) => { sent.fill = e.text; return { isFilled: true } })
  on('clock.now', () => ({ value: 5000 }))
  on('fs.write', (_: unknown, e: { path: string; text: string }) => { sent.files[posix(e.path)] = e.text; return { value: undefined } })
  on('fs.read', (_: unknown, e: { path: string }) => {
    if (posix(e.path).endsWith('/s.project')) return { value: '/project\n' }
    if (sent.files[posix(e.path)] !== undefined) return { value: sent.files[posix(e.path)] }
    throw new Error('no file')
  })
  on('fs.exists', () => ({ value: false }))
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('tool.register', () => ({ value: undefined }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.id', () => ({ value: 's' }))
  on('clock.every', () => ({ value: undefined }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/project', surface: 'terminal', isInteractive: true })
  return sent
}

const RECORD = '/project/.frame-loop/approved.json'

test('every item starts checked, and the tool tells Claude to end its turn', async ($, on) => {
  await picking($, on)
  const called = await $.tool.call(PROPOSED as any)
  expect(JSON.stringify(called)).toContain('End your turn')
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect(await ui.find({ key: 'item-0' })).toBeTruthy()
  await ui.unmount()
})

test('approving everything says so, starts the next turn and keeps the words on the record', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(PROPOSED as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key: 'approve' })
  expect(sent.submit).toBe('Approved, all 2.')
  expect(sent.closed).toBe(true)
  expect(JSON.parse(sent.files[RECORD]).rounds).toEqual([{
    frame: 'frame 0', title: 'Approve frame 0', at: 5,
    approved: ['Each client is limited per minute.', 'Over the limit, the API returns 429.'], not_approved: [],
  }])
  await ui.unmount()
})

test('one item approved reads as a sentence', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call({ ...PROPOSED, items: [PROPOSED.items[0]] } as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key: 'approve' })
  expect(sent.submit).toBe('Approved.')
  await ui.unmount()
})

test('a deselected item is named, kept as not approved, and Claude is sent to ask what is wrong', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call({ ...PROPOSED, node: 'counting' } as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key: 'item-1' })
  await ui.press({ key: 'approve' })
  expect(sent.submit).toContain('Approved:\n- Each client is limited per minute.')
  expect(sent.submit).toContain('Not approved:\n- Over the limit, the API returns 429.')
  expect(sent.submit).toContain('Ask me what is wrong')
  const [round] = JSON.parse(sent.files[RECORD]).rounds
  expect(round.frame).toBe('counting')
  expect(round.not_approved).toEqual(['Over the limit, the API returns 429.'])
  await ui.unmount()
})

test('words taken out are an item to approve, and only an approved removal takes them out', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call({ ...PROPOSED, removes: ['Each client has a limit.', 'Limits reset hourly.'] } as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await ui.find({ key: 'item-2' }))).toBeTruthy()
  await ui.press({ key: 'item-3' })
  await ui.press({ key: 'approve' })
  const [round] = JSON.parse(sent.files[RECORD]).rounds
  expect(round.approved).toEqual(['Each client is limited per minute.', 'Over the limit, the API returns 429.'])
  expect(round.not_approved).toEqual(['Each client has a limit.'])
  expect(sent.submit).toContain('Not approved:\n- Remove: Limits reset hourly.')
  await ui.unmount()
})

test('a later round is added to the record, never over it', async ($, on) => {
  const sent = await picking($, on)
  for (const _ of [1, 2]) {
    await $.tool.call(PROPOSED as any)
    const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
    await ui.press({ key: 'approve' })
    await ui.unmount()
  }
  expect(JSON.parse(sent.files[RECORD]).rounds.length).toBe(2)
})

test('adding what is missing leaves the answer in the prompt for the person to finish', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(PROPOSED as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key: 'missing' })
  expect(sent.submit).toBeUndefined()
  expect(sent.fill).toBe('Approved, all 2.\n\nMissing: ')
  await ui.unmount()
})

test('a picker that cannot be shown says so to Claude, never as an approval', async ($, on) => {
  const sent = await picking($, on, false)
  const called = await $.tool.call(PROPOSED as any)
  expect(JSON.stringify(called)).toContain('Ask in chat')
  expect(sent.submit).toBeUndefined()
  expect(sent.files[RECORD]).toBeUndefined()
})

test('no items is refused', async ($, on) => {
  await picking($, on)
  const called = await $.tool.call({ ...PROPOSED, items: [] } as any)
  expect(JSON.stringify(called)).toContain('at least one item')
})

test('an act that needs the author shows as the act, after its mark', async ($, on) => {
  seed(on, { session: 's', at: 50, state: 'done', decision: 'rise', started: 10,
             lines: ['frame-loop ▲ deleted build/'], detail: ['▲ deleted build/: rm -rf build'] })
  on('clock.now', () => ({ value: 60000 }))
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /deleted/ }))?.text).toBe('deleted build/')
  await ui.unmount()
})

// A reading that landed starts a turn, once the session is free.
const LANDED = { session: 's', at: 50, state: 'done', decision: 'rise', started: 10, wake: true,
                 lines: ['frame-loop ▲ needs you: this serves none of your requirements'], detail: [] }

const waking = async ($: any, on: any, { shown = LANDED as unknown, draft = '', working = false, dismissed = 0, ticks = 2 } = {}) => {
  const store = seed(on, null, dismissed)
  store.woken = { value: 0, version: 1 }
  store.proposal = { value: null, version: 1 }
  const sent: string[] = []
  on('prompt.submit', (_: unknown, e: { text: string }) => { sent.push(e.text); return { text: e.text } })
  on('prompt.read', () => ({ value: { text: draft, cursor: 0 } }))
  on('fs.read', (_: unknown, e: { path: string }) => {
    if (posix(e.path).endsWith('/s.json')) return { value: JSON.stringify(shown) }
    throw new Error('no file')
  })
  on('fs.exists', () => ({ value: false }))
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('tool.register', () => ({ value: undefined }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.id', () => ({ value: 's' }))
  on('clock.now', () => ({ value: 60000 }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('ui.render', ($: any, e: any) => { const { Text } = $.ui.resolve(e); return <Text>engine</Text> })
  // The ticks wait until the band has been drawn once, as it is in a session.
  let drawn = () => {}
  const ready = new Promise<void>(r => { drawn = r })
  let periods = 0
  on('clock.every', async () => {
    await ready
    return periods++ < ticks ? { value: undefined } : { deny: 'enough periods' }
  })
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, props: { ...BAND.props, isWorking: working }, surface: 'terminal' })
  drawn()
  for (let i = 0; i < 30 && periods <= ticks; i++) await new Promise(r => setTimeout(r, 10))
  await ui.unmount()
  return { sent, store }
}

const WOKEN = 'frame-loop: a reading of the work landed. Deal with what it found.'

test('a reading that landed starts one turn, however often the band looks', async ($, on) => {
  const { sent, store } = await waking($, on, { ticks: 4 })
  expect(sent).toEqual([WOKEN])
  expect(store.woken?.value).toBe(50)
})

test('a wake waits while the person is typing', async ($, on) => {
  expect((await waking($, on, { draft: 'half a sent' })).sent).toEqual([])
})

test('a wake waits while Claude works', async ($, on) => {
  expect((await waking($, on, { working: true })).sent).toEqual([])
})

test('a prompt sent since the reading landed has told Claude already', async ($, on) => {
  expect((await waking($, on, { dismissed: 55 })).sent).toEqual([])
})

test('a reading with no wake starts no turn', async ($, on) => {
  expect((await waking($, on, { shown: { ...LANDED, wake: undefined } })).sent).toEqual([])
})

test('a wake does not clear the ▲ from the band, and the person\'s own prompt does', async ($, on) => {
  const { store } = await waking($, on, {})
  await $.prompt.submit({ text: WOKEN })
  expect(store.dismissedAt?.value).toBe(0)
  await $.prompt.submit({ text: 'go on' })
  expect(store.dismissedAt?.value).toBe(60)
})
