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

// Where the work is: one line always names the part and where it sits, and when it is done.
const IN_PART = { at: 40, part: { name: 'the 429 response', where: 'frame 0 › Each client is limited per minute', done: false },
                  finished: null }

const inPart = (on: any, live: unknown, where: unknown, dismissedAt = 0) => {
  const store = seed(on, live, dismissedAt)
  store.part = { value: where, version: 1 }
  on('clock.now', () => ({ value: 60000 }))
  return store
}

test('with nothing being read, one line names the part the work is in and where it sits', async ($, on) => {
  inPart(on, null, IN_PART)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^in / }))?.text).toBe('in the 429 response')
  expect((await ui.find({ type: 'Text', text: /›/ }))?.text).toBe(' · frame 0 › Each client is limited per minute')
  await ui.unmount()
})

test('a part whose requirements are all done says so on that line', async ($, on) => {
  inPart(on, null, { ...IN_PART, part: { ...IN_PART.part, done: true } })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /is done/ }))?.text).toBe('the 429 response is done')
  expect((await ui.find({ type: 'Text', text: /^✓ $/ }))?.props.color).toBe('success')
  await ui.unmount()
})

test('a part just left done is named, with the part the work is in now', async ($, on) => {
  inPart(on, null, { ...IN_PART, finished: 'counting' })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /is done/ }))?.text).toBe('counting is done · now in the 429 response')
  await ui.unmount()
})

test('while a reading runs, its one line still names the part', async ($, on) => {
  inPart(on, { session: 's', at: 1, state: 'reading', what: 'checking the change', started: 1, tokens: 2000 }, IN_PART)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /tokens/ }))?.text).toBe(' · 0:59 · 2k tokens · in the 429 response')
  await ui.unmount()
})

test('an outcome that needs the author names the part after it, and once seen the part line is back', async ($, on) => {
  inPart(on, { session: 's', at: 50, state: 'done', decision: 'rise', started: 10, lines: ['frame-loop ▲ needs you: x'] }, IN_PART)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /in the 429 response/ }))?.text).toBe(' · 0:40 · in the 429 response ')
  await ui.unmount()
})

test('an outcome already seen leaves the part line', async ($, on) => {
  inPart(on, { session: 's', at: 50, state: 'done', decision: 'pass', started: 10 }, IN_PART, 51)
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^in / }))?.text).toBe('in the 429 response')
  await ui.unmount()
})

test('at frame 0, with no part engaged and none just done, the band is as before', async ($, on) => {
  inPart(on, null, { at: 40, part: null, finished: null })
  on('ui.render', ($: any, e: any) => { const { Text } = $.ui.resolve(e); return <Text>engine</Text> })
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('engine')
  await ui.unmount()
})

test('the band reads where the work is from the file beside the live state', async ($, on) => {
  const store = seed(on, null)
  store.part = { value: null, version: 1 } // as the engine holds an atom never written: its initial value
  const reads: string[] = []
  on('fs.read', (_: unknown, e: { path: string }) => {
    reads.push(posix(e.path))
    if (posix(e.path) === '/home/u/.claude/frame-loop/live/s.part.json') return { value: JSON.stringify(IN_PART) }
    throw new Error('no file')
  })
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.id', () => ({ value: 's' }))
  let periods = 0
  on('clock.every', () => (periods++ < 2 ? { value: undefined } : { deny: 'enough periods' }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  for (let i = 0; i < 30 && !store.part?.value; i++) await new Promise(r => setTimeout(r, 10))
  expect(reads).toContain('/home/u/.claude/frame-loop/live/s.part.json')
  expect((store.part?.value as any)?.part?.name).toBe('the 429 response')
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

// Off and on-and-idle show the same empty band: the label beside the session's modes is the
// one standing sign that nothing is being checked, so it stays for as long as the switch is off.
for (const [isOff, said] of [[true, 'modes: plan, frame-loop off'], [false, 'modes: plan']] as const) {
  test(`the switch: ${isOff ? 'off is said beside' : 'on adds nothing to'} the session's modes`, async ($, on) => {
    const store = seed(on, null)
    store.off = { value: isOff, version: 1 }
    on('ui.render', ($: any, e: any) => {
      const { Text } = $.ui.resolve(e)
      return <Text>{`modes: ${e.props.modes.join(', ')}`}</Text>
    })
    const ui = await $.ui.mount({ plugin: 'frame-loop', component: 'SessionMode', props: { modes: ['plan'] }, surface: 'terminal' })
    expect((await ui.find({ type: 'Text' }))?.text).toBe(said)
    await ui.unmount()
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

test('a record that cannot be read is never written over, and the answer says so', async ($, on) => {
  const sent = await picking($, on)
  sent.files[RECORD] = 'not json'
  await $.tool.call(PROPOSED as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key: 'approve' })
  expect(sent.files[RECORD]).toBe('not json')
  expect(sent.submit).toContain('could not keep this answer')
  await ui.unmount()
})

test('a record of another version is not added to, and the answer says so', async ($, on) => {
  const sent = await picking($, on)
  const other = JSON.stringify({ version: 2, rounds: [] })
  sent.files[RECORD] = other
  await $.tool.call(PROPOSED as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key: 'approve' })
  expect(sent.files[RECORD]).toBe(other)
  expect(sent.submit).toContain('could not keep this answer')
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

// A split: every part at once, one page each, and one approval on the review page.
const SPLIT = {
  tool: 'mcp__frame-loop__approve',
  title: 'Split: each client is limited per minute',
  parts: [
    { id: 'counting', name: 'counting', scope: ['limiter/count.py'], items: [
      { text: 'Requests are counted per client.', quotes: 'A1' },
      { text: 'The count resets each minute.', quotes: 'A1' }] },
    { id: 'the-429', name: 'the 429 response', scope: ['limiter/respond.py'], items: [
      { text: 'A client over its limit gets a 429 with a Retry-After header.', quotes: 'A1',
        detail: 'narrows: "is limited" · may change: limiter/respond.py' }] },
    { id: 'headers', name: 'headers', scope: ['limiter/headers.py'], items: [{ text: 'Every answer says how many requests are left.', quotes: 'A1' }] },
  ],
}

test('a split opens on its first part, one page each, with no approval before the review', async ($, on) => {
  await picking($, on)
  const called = await $.tool.call(SPLIT as any)
  expect(JSON.stringify(called)).toContain('End your turn')
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^Part 1:/ }))?.text).toBe('Part 1:  counting')
  expect(await ui.find({ key: 'item-0-1' })).toBeTruthy()
  expect(await ui.find({ key: 'item-1-0' })).toBeUndefined() // one part a page
  expect(await ui.find({ key: 'approve' })).toBeUndefined() // the last page closes the round
  expect((await ui.find({ type: 'Text', text: /1 \/ 3/ }))?.text).toBe('1 / 3')
  const row = (await ui.findAll({ type: 'Button' })).filter(x => x.key?.startsWith('go-')).map(x => x.text)
  expect(row).toEqual(['[counting]', 'the 429 response', 'headers', 'review'])
  await ui.unmount()
})

test('right and left page between the parts, and the focus starts on each page\'s first line', async ($, on) => {
  // The move of the ring itself ($.ui.focus) needs a site holding the keyboard, which no test
  // mount does: what is drawn is checked here, the move in a real session.
  await picking($, on)
  await $.tool.call(SPLIT as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await ui.find({ key: 'item-0-0' }))?.props.autoFocus).toBe(true)
  await ui.press({ key: 'next' })
  expect((await ui.find({ key: 'item-1-0' }))?.props.autoFocus).toBe(true) // the same pane, drawn again
  await ui.unmount()
  const two = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await two.find({ type: 'Text', text: /^Part 2:/ }))?.text).toBe('Part 2:  the 429 response')
  expect((await two.find({ type: 'Text', text: /may change/ }))?.text).toContain('limiter/respond.py')
  expect((await two.find({ key: 'item-1-0' }))?.props.autoFocus).toBe(true)
  await two.press({ key: 'prev' })
  await two.unmount()
  const back = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await back.find({ type: 'Text', text: /^Part 1:/ }))?.text).toBe('Part 1:  counting')
  await back.unmount()
})

// One press in a freshly drawn picker, as the person moves through it.
const pressIn = async ($: any, key: string) => {
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await ui.press({ key })
  await ui.unmount()
}

test('the review lists each part, its lines and whether it was seen, and one approval fixes them all', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(SPLIT as any)
  for (const key of ['next', 'next', 'next']) await pressIn($, key)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^review$/ }))?.text).toBe('review')
  const rows = (await ui.findAll({ type: 'Button' })).filter(x => x.key?.startsWith('part-')).map(x => x.text)
  expect(rows.length).toBe(3)
  expect(rows[0]).toMatch(/^counting\s+2 lines\s+seen$/)
  expect(rows[1]).toMatch(/^the 429 response\s+1 line\s+seen$/)
  expect(rows[2]).toMatch(/^headers\s+1 line\s+seen$/)
  expect((await ui.find({ key: 'part-0' }))?.props.autoFocus).toBe(true) // never the approve button
  expect((await ui.find({ key: 'approve' }))?.props.autoFocus).toBeUndefined()
  expect((await ui.find({ key: 'approve' }))?.text).toBe('Approve all three')
  await ui.press({ key: 'approve' })
  expect(sent.submit).toBe('Approved, all three parts: counting, the 429 response, headers.')
  const rounds = JSON.parse(sent.files[RECORD]).rounds
  expect(rounds.map((r: any) => [r.frame, r.split, r.name, r.approved])).toEqual([
    ['counting', 'frame 0', 'counting', ['Requests are counted per client.', 'The count resets each minute.']],
    ['the-429', 'frame 0', 'the 429 response', ['A client over its limit gets a 429 with a Retry-After header.']],
    ['headers', 'frame 0', 'headers', ['Every answer says how many requests are left.']],
  ])
  await ui.unmount()
})

test('each part\'s page shows the files it may change, and its round records them and what each line narrows', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(SPLIT as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /^May change:/ }))?.text).toBe('May change:  limiter/count.py')
  await ui.press({ key: 'item-0-1' }) // a line not approved is no part of what the file may hold
  await ui.press({ key: 'go-review' })
  await ui.unmount()
  const review = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  await review.press({ key: 'approve' })
  await review.unmount()
  const [first, second] = JSON.parse(sent.files[RECORD]).rounds
  expect(first.scope).toEqual(['limiter/count.py'])
  expect(first.narrows).toEqual({ 'Requests are counted per client.': 'A1' })
  expect(second.scope).toEqual(['limiter/respond.py'])
  expect(second.narrows).toEqual({ 'A client over its limit gets a 429 with a Retry-After header.': 'A1' })
})

test('a part not yet seen shows so on the review and does not block the approval', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call({ ...SPLIT, parent: 'limits' } as any)
  await pressIn($, 'go-review')
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const rows = (await ui.findAll({ type: 'Button' })).filter(x => x.key?.startsWith('part-')).map(x => x.text)
  expect(rows[0]).toMatch(/seen$/)
  expect(rows[0]).not.toMatch(/not seen/)
  expect(rows[1]).toMatch(/not seen yet$/)
  await ui.press({ key: 'approve' })
  expect(sent.submit).toBe('Approved, all three parts: counting, the 429 response, headers.')
  expect(JSON.parse(sent.files[RECORD]).rounds.map((r: any) => r.split)).toEqual(['limits', 'limits', 'limits'])
  await ui.unmount()
})

test('from the review a part\'s row opens its page, and a line not approved is named with its part', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(SPLIT as any)
  await pressIn($, 'go-review')
  await pressIn($, 'part-1')
  const page = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await page.find({ type: 'Text', text: /^Part 2:/ }))?.text).toBe('Part 2:  the 429 response')
  await page.press({ key: 'item-1-0' })
  await page.press({ key: 'go-review' })
  await page.unmount()
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await ui.find({ key: 'part-1' }))?.text).toMatch(/1 not approved/)
  expect((await ui.find({ key: 'approve' }))?.text).toBe('Approve checked')
  await ui.press({ key: 'approve' })
  expect(sent.submit).toContain('Not approved:\n- the 429 response: A client over its limit gets a 429')
  expect(sent.submit).toContain('Ask me what is wrong')
  const [, second] = JSON.parse(sent.files[RECORD]).rounds
  expect(second.not_approved).toEqual(['A client over its limit gets a 429 with a Retry-After header.'])
  await ui.unmount()
})

// The tree's files as the hooks keep them, for the header to read.
const TREE_FILES = {
  '/project/.frame-loop/frame0.json': JSON.stringify({
    asks: [{ id: 'A1', text: 'Each client is limited per minute' }, { id: 'A2', text: 'Limits are set per plan' }],
    principles: [{ id: 'P1', text: 'A request that is not limited is answered as today' }],
  }),
  '/project/.frame-loop/tree/counting.json': JSON.stringify({
    parent: 'root', name: 'counting', scope: ['limiter/*'],
    asks: [{ id: 'C1', text: 'Requests are counted per client', quotes: 'A1', owner: 'children' }],
    principles: [{ id: 'P9', text: 'Counting adds no new store' }],
  }),
  '/project/.frame-loop/rules.json': JSON.stringify({ rules: [
    { id: 'R1', kind: 'principle', accepted: true }, { id: 'R2', kind: 'principle', accepted: true },
    { id: 'R3', kind: 'obligation', accepted: true }] }),
}

const texts = async (ui: any) => (await ui.findAll({ type: 'Text' })).map((x: any) => x.text)

test('each page\'s header is read from the tree: path, requirement split, principles and page', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES)
  await $.tool.call(SPLIT as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const shown = await texts(ui)
  expect(shown).toContain('frame 0 › Each client is limited per minute')
  expect(shown).toContain('Splitting:  "Each client is limited per minute"')
  expect(shown).toContain('Holds for every part:')
  expect(shown).toContain('  · A request that is not limited is answered as today  (frame 0)')
  expect(shown).toContain("  · and the project's two rules from its guide")
  expect(shown).toContain('1 / 3')
  expect(shown.join('\n')).not.toContain(SPLIT.title) // Claude's words name the tab alone
  await ui.press({ key: 'go-review' })
  await ui.unmount()
  const review = await texts(await $.ui.mount({ ...PICKER, surface: 'terminal' }))
  expect(review).toContain('frame 0 › Each client is limited per minute')
  expect(review).toContain('  · A request that is not limited is answered as today  (frame 0)')
})

// What a saved split reading was a reading of, as the hooks record it (splitcheck.shape_of).
const shapeOf = (given: any): string[] => {
  const out: string[] = []
  for (const part of given.parts ?? []) {
    out.push(['files', part.id, ...[...part.scope].sort()].join('|'))
    for (const item of part.items) out.push(['line', part.id, item.quotes ?? '', item.text, item.detail ?? ''].join('|'))
  }
  for (const c of given.contracts ?? []) out.push(['contract', c.text, ...[...c.parts].sort()].join('|'))
  return out.sort()
}

test('the split\'s reading shows on its pages: which lines are needed, which overlap, and what did not settle', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES, {
    '/project/.frame-loop/work/split-read.json': JSON.stringify({
      parent: 'frame 0',
      of: shapeOf(SPLIT),
      requirements: { A1: 'covered' },
      lines: { 'Requests are counted per client.': 'overlaps', 'The count resets each minute.': 'needed' },
      thin: ['The count resets each minute.'],
      parts: {
        counting: { breaks: 'A request that is not limited is answered as today', scoped: ['The limiter keeps no state on disk'], owes: ['limiter changes come with docs'] },
        headers: { breaks: 'not settled', scoped: [], owes: [] },
      },
    }),
  })
  await $.tool.call(SPLIT as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const shown = await texts(ui)
  expect(shown).toContain('      the other lines already cover this one')
  expect(shown).toContain('      needed: without it the requirement is not met')
  expect(shown).toContain('      says which words it narrows, not how')
  expect(shown).toContain("For this part's files, from the project's guide:")
  expect(shown).toContain('  · The limiter keeps no state on disk')
  expect(shown).toContain('A change here will owe:')
  expect(shown).toContain('  · limiter changes come with docs')
  expect(shown).toContain('Read before you: counting may break your rule "A request that is not limited is answered as today".')
  await ui.press({ key: 'go-review' })
  await ui.unmount()
  const review = await texts(await $.ui.mount({ ...PICKER, surface: 'terminal' }))
  expect(review).toContain('Read before you: the parts make what they split true.')
  expect(review).toContain('Read before you: counting may break your rule "A request that is not limited is answered as today".')
  expect(review).toContain('Read before you: not settled whether headers breaks a rule.')
})

test('a split that did not settle, or was read for another frame, says so or says nothing', async ($, on) => {
  const sent = await picking($, on)
  const read = (parent: string, said: string, of: string[] = shapeOf(SPLIT)) =>
    JSON.stringify({ parent, of, requirements: { A1: said }, lines: { 'Requests are counted per client.': 'needed' } })
  const pages = async () => {
    await $.tool.call(SPLIT as any)
    const first = await $.ui.mount({ ...PICKER, surface: 'terminal' })
    const page = await texts(first)
    await first.press({ key: 'go-review' })
    await first.unmount()
    const last = await $.ui.mount({ ...PICKER, surface: 'terminal' })
    const review = await texts(last)
    await last.unmount()
    return { page, review }
  }
  Object.assign(sent.files, TREE_FILES, { '/project/.frame-loop/work/split-read.json': read('frame 0', 'not settled') })
  expect((await pages()).review).toContain(
    'Read before you: not settled whether the parts make "Each client is limited per minute" true.',
  )
  sent.files['/project/.frame-loop/work/split-read.json'] = read('counting', 'covered') // another split's reading
  const other = await pages()
  expect(other.page.join('\n')).not.toContain('needed: without it')
  expect(other.review).toContain('Not read before you: this split was not read against what it splits.')
  // Pass 10, F5: a reading was matched by the frame it split alone, so a split revised after
  // its reading, or another split of the same frame, wore the earlier one's "true" and "needed".
  const revised = shapeOf({ ...SPLIT, parts: [{ ...SPLIT.parts[0], items: [{ text: 'Another line.', quotes: 'A1' }] }] })
  sent.files['/project/.frame-loop/work/split-read.json'] = read('frame 0', 'covered', revised)
  const stale = await pages()
  expect(stale.page.join('\n')).not.toContain('needed: without it')
  expect(stale.review).toContain('Not read before you: this split was not read against what it splits.')
  expect(stale.review.join('\n')).not.toContain('the parts make what they split true')
})

test('a split below frame 0 shows the path through the parts and the principles each adds', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES)
  const parts = [{ id: 'per-client', name: 'per client', scope: ['limiter/count.py'], items: [{ text: 'Each client has its own count.', quotes: 'C1' }] }]
  await $.tool.call({ ...SPLIT, parent: 'counting', parts } as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const shown = await texts(ui)
  expect(shown).toContain('frame 0 › counting › Requests are counted per client')
  expect(shown).toContain('  · A request that is not limited is answered as today  (frame 0)')
  expect(shown).toContain('  · Counting adds no new store  (counting)')
  expect(shown).toContain('1 / 1')
  await ui.unmount()
})

test('a requirement whose words are not the approved ones, or none at all, is said, never filled in', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES)
  sent.files[RECORD] = JSON.stringify({ version: 1, rounds: [
    { frame: 'frame 0', approved: ['Each client is limited per hour'], not_approved: [] }] })
  const parts = [
    { id: 'a', name: 'a', scope: ['a.py'], items: [{ text: 'A line.', quotes: 'A1' }] },
    { id: 'b', name: 'b', scope: ['b.py'], items: [{ text: 'A line.', quotes: 'A9' }] },
  ]
  await $.tool.call({ ...SPLIT, parts } as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect(await texts(ui)).toContain('Splitting:  "Each client is limited per minute"  (not in the words you approved)')
  await ui.press({ key: 'next' })
  await ui.unmount()
  const two = await texts(await $.ui.mount({ ...PICKER, surface: 'terminal' }))
  expect(two).toContain('Splitting:  (a line narrows no requirement of frame 0)')
  expect(two).toContain('frame 0')
})

test('a part being split that the tree does not hold is said, and no words of Claude\'s stand in', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES)
  await $.tool.call({ ...SPLIT, parent: 'gone' } as any)
  const shown = await texts(await $.ui.mount({ ...PICKER, surface: 'terminal' }))
  expect(shown).toContain('Splitting:  (not shown: the part being split is not in the tree)')
  expect(shown).toContain('frame 0')
  expect(shown.join('\n')).not.toContain('Each client is limited per minute')
})

// A contract: one statement two or more parts must each keep, written once beside the parts.
const SHARED = 'A client over its limit is never counted twice.'
const CONTRACTED = {
  ...SPLIT,
  contracts: [
    { text: SHARED, parts: ['counting', 'the-429'] },
    { text: 'Every part reads the limit from one place.', parts: ['counting', 'the-429', 'headers'] },
  ],
}

test('a contract shows on the page of every part it binds, in the same words, naming the other parts', async ($, on) => {
  await picking($, on)
  await $.tool.call(CONTRACTED as any)
  const first = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const one = await texts(first)
  expect(one).toContain('Contracts with other parts:')
  expect((await first.find({ key: 'contract-0-0' }))?.text).toBe(`[x] ${SHARED}`)
  expect(one).toContain('      shared with: the 429 response')
  expect(one).toContain('      shared with: the 429 response, headers')
  await first.press({ key: 'next' })
  await first.unmount()
  const second = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await second.find({ key: 'contract-1-0' }))?.text).toBe(`[x] ${SHARED}`)
  expect(await texts(second)).toContain('      shared with: counting')
  await second.press({ key: 'next' })
  await second.unmount()
  const third = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const shown = (await third.findAll({ type: 'Button' })).filter(x => x.key?.startsWith('contract-')).map(x => x.text)
  expect(shown).toEqual(['[x] Every part reads the limit from one place.']) // the first binds no headers
  expect(await texts(third)).toContain('      shared with: counting, the 429 response')
  await third.unmount()
})

test('a contract taken out on one page is out on every page, named once, and kept off the record', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(CONTRACTED as any)
  await pressIn($, 'contract-0-0')
  await pressIn($, 'next')
  const second = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await second.find({ key: 'contract-1-0' }))?.text).toBe(`[ ] ${SHARED}`)
  await second.press({ key: 'go-review' })
  await second.unmount()
  const review = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await review.find({ key: 'approve' }))?.text).toBe('Approve checked')
  await review.press({ key: 'approve' })
  await review.unmount()
  expect(sent.submit).toContain(`Not approved:\n- the contract between counting and the 429 response: ${SHARED}`)
  expect(sent.submit?.split(SHARED).length).toBe(2) // once, however many pages showed it
  const rounds = JSON.parse(sent.files[RECORD]).rounds
  const every = { text: 'Every part reads the limit from one place.' }
  expect(rounds.map((r: any) => [r.frame, r.contracts])).toEqual([
    ['counting', [{ ...every, with: ['the-429', 'headers'] }]],
    ['the-429', [{ ...every, with: ['counting', 'headers'] }]],
    ['headers', [{ ...every, with: ['counting', 'the-429'] }]],
  ])
})

test('a split\'s one approval approves its contracts, and each part\'s round keeps the ones that bind it', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(CONTRACTED as any)
  await pressIn($, 'go-review')
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect(await texts(ui)).toContain('Contracts between the parts:')
  expect((await ui.find({ key: 'approve' }))?.text).toBe('Approve all three')
  await ui.press({ key: 'approve' })
  await ui.unmount()
  expect(sent.submit).toBe('Approved, all three parts: counting, the 429 response, headers, and the two contracts between them.')
  const [counting, the429, headers] = JSON.parse(sent.files[RECORD]).rounds
  expect(counting.contracts).toEqual([
    { text: SHARED, with: ['the-429'] },
    { text: 'Every part reads the limit from one place.', with: ['the-429', 'headers'] },
  ])
  expect(the429.contracts.map((c: any) => c.with)).toEqual([['counting'], ['counting', 'headers']])
  expect(headers.contracts).toEqual([{ text: 'Every part reads the limit from one place.', with: ['counting', 'the-429'] }])
})

test('what the split\'s reading found of each contract shows on the pages of the parts it binds', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES, {
    '/project/.frame-loop/work/split-read.json': JSON.stringify({
      parent: 'frame 0',
      of: shapeOf(CONTRACTED),
      requirements: { A1: 'covered' },
      lines: {},
      parts: {},
      contracts: { [SHARED]: 'not kept', 'Every part reads the limit from one place.': 'not settled' },
    }),
  })
  await $.tool.call(CONTRACTED as any)
  const first = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const page = await texts(first)
  expect(page).toContain('      Read before you: their lines do not keep it.')
  expect(page).toContain('      Read before you: not settled whether their lines keep it.')
  await first.press({ key: 'go-review' })
  await first.unmount()
  const review = await texts(await $.ui.mount({ ...PICKER, surface: 'terminal' }))
  expect(review).toContain(`Read before you: the lines of counting and the 429 response do not keep "${SHARED}".`)
  expect(review).toContain(
    'Read before you: not settled whether the lines of counting, the 429 response and headers keep "Every part reads the limit from one place.".',
  )
})

test('a contract kept shows so on its pages; one the reading never saw says it was not read', async ($, on) => {
  const sent = await picking($, on)
  Object.assign(sent.files, TREE_FILES, {
    '/project/.frame-loop/work/split-read.json': JSON.stringify({
      parent: 'frame 0',
      of: shapeOf(CONTRACTED), requirements: { A1: 'covered' }, lines: {}, parts: {}, contracts: { [SHARED]: 'kept' },
    }),
  })
  await $.tool.call(CONTRACTED as any)
  const first = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  const page = await texts(first)
  expect(page).toContain('      Read before you: their lines keep it.')
  expect(page).toContain('      Not read before you.')
  await first.press({ key: 'go-review' })
  await first.unmount()
  const review = await texts(await $.ui.mount({ ...PICKER, surface: 'terminal' }))
  expect(review).toContain(
    'Not read before you: whether the lines of counting, the 429 response and headers keep "Every part reads the limit from one place.".',
  )
  expect(review.join('\n')).not.toContain(`keep "${SHARED}"`) // a kept contract asks nothing of the author
})

test('a split with no contracts shows none, answers as before and records no contracts', async ($, on) => {
  const sent = await picking($, on)
  await $.tool.call(SPLIT as any)
  const ui = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await texts(ui)).join('\n')).not.toContain('Contracts')
  await ui.press({ key: 'go-review' })
  await ui.unmount()
  const review = await $.ui.mount({ ...PICKER, surface: 'terminal' })
  expect((await texts(review)).join('\n')).not.toContain('Contracts')
  await review.press({ key: 'approve' })
  expect(sent.submit).toBe('Approved, all three parts: counting, the 429 response, headers.')
  expect(JSON.parse(sent.files[RECORD]).rounds.every((r: any) => !('contracts' in r))).toBe(true)
})

for (const [why, wrong, said] of [
  ['a contract binding one part', { contracts: [{ text: SHARED, parts: ['counting'] }] }, 'two or more'],
  ['a contract binding one part twice', { contracts: [{ text: SHARED, parts: ['counting', 'counting'] }] }, 'two or more'],
  ['a contract naming a part not in the split', { contracts: [{ text: SHARED, parts: ['counting', 'billing'] }] }, 'not a part of this split'],
  ['a contract with no words', { contracts: [{ text: ' ', parts: ['counting', 'headers'] }] }, 'a statement'],
  ['two contracts in the same words', { contracts: [{ text: SHARED, parts: ['counting', 'headers'] }, { text: SHARED, parts: ['counting', 'the-429'] }] }, 'written once'],
] as const) {
  test(`a split is refused for ${why}, and nothing is opened`, async ($, on) => {
    const sent = await picking($, on)
    const called = await $.tool.call({ ...SPLIT, ...wrong } as any)
    expect(JSON.stringify(called)).toContain(said)
    expect(sent.opened).toBeUndefined()
  })
}

test('contracts with no split are refused, and nothing is opened', async ($, on) => {
  const sent = await picking($, on)
  const called = await $.tool.call({ ...PROPOSED, contracts: [{ text: SHARED, parts: ['a', 'b'] }] } as any)
  expect(JSON.stringify(called)).toContain('between the parts of a split')
  expect(sent.opened).toBeUndefined()
})

for (const [why, wrong, said] of [
  ['a part with no id', { parts: [{ name: 'x', scope: ['x'], items: [{ text: 'A line.' }] }] }, 'an id'],
  ['a part with no files it may change', { parts: [{ id: 'x', name: 'x', items: [{ text: 'A line.' }] }] }, 'its scope'],
  ['two parts sharing an id', { parts: [SPLIT.parts[0], SPLIT.parts[0]] }, 'share an id'],
  ['a part with no lines', { parts: [{ id: 'x', name: 'x', scope: ['x'], items: [] }] }, 'at least one line'],
  ['parts beside items', { items: [{ text: 'A line.' }] }, 'its parts alone'],
  ['a part named by a path', { parts: [{ id: '../frame0', name: 'x', scope: ['x'], items: [{ text: 'A line.' }] }] }, 'an id'],
] as const) {
  test(`a split is refused for ${why}, and nothing is opened`, async ($, on) => {
    const sent = await picking($, on)
    const called = await $.tool.call({ ...SPLIT, ...wrong } as any)
    expect(JSON.stringify(called)).toContain(said)
    expect(sent.opened).toBeUndefined()
  })
}

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

const waking = async ($: any, on: any, { shown = LANDED as unknown, draft = '', working = false, dismissed = 0, ticks = 2, command = '' } = {}) => {
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
  const said = command ? (await $.command.run({ command: 'frame-loop', args: command })).text : ''
  drawn()
  for (let i = 0; i < 30 && periods <= ticks; i++) await new Promise(r => setTimeout(r, 10))
  await ui.unmount()
  return { sent, store, said }
}

const WOKEN = 'frame-loop: a reading of the work landed. Deal with what it found.'

test('a reading that landed starts one turn, however often the band looks', async ($, on) => {
  const { sent, store } = await waking($, on, { ticks: 4 })
  expect(sent).toEqual([WOKEN])
  expect(store.woken?.value).toBe(50)
})

test('/frame-loop check asks Claude once, leaves the switch alone, and works with no reading yet', async ($, on) => {
  const { sent, store, said } = await waking($, on, { shown: null, command: 'check', ticks: 4 })
  expect(said).toBe('frame-loop: checking what a first reading needs.')
  expect(sent.length).toBe(1)
  expect(sent[0]).toContain(': frame-loop-check')
  expect(store.off?.value).toBe(false)
})

test('/frame-loop check that did not go is tried once more, and no more', async ($, on) => {
  const store = seed(on, null, 0)
  store.woken = { value: 0, version: 1 }
  store.proposal = { value: null, version: 1 }
  let tries = 0
  on('prompt.submit', () => { tries++; throw new Error('a dialog is up') })
  on('prompt.read', () => ({ value: { text: '', cursor: 0 } }))
  on('fs.read', () => { throw new Error('no file') })
  on('fs.exists', () => ({ value: false }))
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('tool.register', () => ({ value: undefined }))
  on('env.get', () => ({ value: undefined }))
  on('session.id', () => ({ value: 's' }))
  on('clock.now', () => ({ value: 60000 }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('ui.render', ($: any, e: any) => { const { Text } = $.ui.resolve(e); return <Text>engine</Text> })
  let drawn = () => {}
  const ready = new Promise<void>(r => { drawn = r })
  let periods = 0
  on('clock.every', async () => {
    await ready
    return periods++ < 5 ? { value: undefined } : { deny: 'enough periods' }
  })
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ ...BAND, props: { ...BAND.props, isWorking: false }, surface: 'terminal' })
  await $.command.run({ command: 'frame-loop', args: 'check' })
  drawn()
  for (let i = 0; i < 40 && periods <= 5; i++) await new Promise(r => setTimeout(r, 10))
  await new Promise(r => setTimeout(r, 20))
  await ui.unmount()
  expect(tries).toBe(2)
})

test('/frame-loop check waits while the person is typing', async ($, on) => {
  const { sent } = await waking($, on, { shown: null, command: 'check', draft: 'half a thought', ticks: 4 })
  expect(sent).toEqual([])
})

test('a wake that did not go is tried once more, and no more', async ($, on) => {
  const store = seed(on, null, 0)
  store.woken = { value: 0, version: 1 }
  store.proposal = { value: null, version: 1 }
  let tries = 0
  on('prompt.submit', () => { tries++; throw new Error('a dialog is up') })
  on('prompt.read', () => ({ value: { text: '', cursor: 0 } }))
  on('fs.read', (_: unknown, e: { path: string }) => {
    if (posix(e.path).endsWith('/s.json')) return { value: JSON.stringify(LANDED) }
    throw new Error('no file')
  })
  on('fs.exists', () => ({ value: false }))
  on('command.register', () => ({ value: { command: 'frame-loop' } }))
  on('tool.register', () => ({ value: undefined }))
  on('env.get', (_: unknown, e: { name: string }) => ({ value: e.name === 'HOME' ? '/home/u' : undefined }))
  on('session.id', () => ({ value: 's' }))
  on('clock.now', () => ({ value: 60000 }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  let periods = 0
  on('clock.every', async () => {
    await new Promise(r => setTimeout(r, 5))
    return periods++ < 8 ? { value: undefined } : { deny: 'enough periods' }
  })
  await $.session.start({ cwd: '/proj', surface: 'terminal', isInteractive: true })
  for (let i = 0; i < 30 && periods <= 8; i++) await new Promise(r => setTimeout(r, 10))
  expect(tries).toBe(2)
})

test('a reading that landed long ago wakes nothing', async ($, on) => {
  expect((await waking($, on, { shown: { ...LANDED, at: -4000 } })).sent).toEqual([])
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
