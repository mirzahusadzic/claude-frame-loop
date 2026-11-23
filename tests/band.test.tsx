import { expect, mock, test } from 'claude-code/testing'

import { shownNow } from '../hooks/band/frameloop'
import { LABELS } from '../hooks/band/labels'
import { STALE_SECONDS } from '../hooks/band/line'
import { INPUT } from '../hooks/band/picker'

// The shell, through the engine's own kit (`claude plugin test .`). Each hook here stands for the engine.
// The kit runs no process, so the fake `hooks/hand.sh` is the `process.run` hook below: it plays
// each verb as the contract has it, from the files of a made-up home. No test reaches a real home:
// every file the band asks for outside /made-up/ is refused and counted in `reached`.
const HOME = '/made-up/home'
const FOLDER = `${HOME}/.frame/claude/notes-0123456789abcdef`
const DATA = `${HOME}/plugin-data`
const ROOT = '/made-up/notes'
const TOOL = 'mcp__frame-loop__propose'
const BAND = {
  plugin: 'frame-loop', component: 'AbovePrompt', requestId: 'band',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 30, bodyColumns: 78, scroll: { offset: 0, bodyRows: 30 }, view: {} },
} as const
// The picker's pane as the host seats it, docked with the keyboard given it, unless a test says other.
const PANE = {
  plugin: 'frame-loop', component: 'Pane', requestId: 'picker',
  props: { title: 'frame-loop · pick', isFocused: true, bodyColumns: 78, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} },
} as const

const SAID = 'a smal cli app for notes, add saves a note and --list prints them numberd'
const FRAME = {
  kind: 'frame', place: '', title: 'notes', holds: [], split: null, options: null, reason: null,
  items: [
    { words: 'add saves the note it is given', of: SAID, owner: 'work' },
    { words: '--list prints every note, numbered from 1', of: SAID, owner: 'work' },
  ],
}
const PAIR = { maker: 'private-1', lines: ['1. A note is kept.'], reversal: { words: 'It is not so that x', lines: ['1. Lost.'] } }
const QUESTION = '«add saves a note» may not hold. Is that fine?'
// The tool's own check as the made-up maker and readers make it: every claim its step, the second one asked about.
const CHECKED = { marks: [{ item: 1, kind: 'uncarried', words: QUESTION }], carried: null, validated: true, steps: { '0': PAIR, '1': PAIR } }
const BOTH = { ...CHECKED, marks: [0, 1].map(item => ({ item, kind: 'uncarried', words: QUESTION })) }
const FAILED = { marks: [], carried: null, validated: false, steps: {}, failed: 'The check could not run: Gadfly is not installed, as there is no gadfly command.' }

type Ran = { exitCode: number; stdout: string; stderr: string }
type Given = {
  faults?: string[]; several?: boolean; approve?: () => Ran | Promise<Ran>; files?: Record<string, string>; stored?: Record<string, unknown>; now?: number
  check?: 'on' | 'off'; examined?: unknown; examine?: () => Ran | Promise<Ran>; drop?: boolean; narrow?: boolean
}
const ok = (out: unknown, exitCode = 0): { value: Ran } => ({ value: { exitCode, stdout: JSON.stringify(out), stderr: '' } })

const world = async ($: any, on: any, given: Given = {}) => {
  const seen = {
    ran: [] as string[][], inits: [] as any[], files: { ...given.files } as Record<string, string>,
    submitted: [] as string[], reached: [] as string[], focused: [] as any[],
    uiCalls: [] as string[],
    copies: { 'approved.json': null, switch: null } as Record<string, string | null>, contexts: [] as (readonly string[] | undefined)[],
    order: [] as string[], looks: [] as (string | undefined)[], forged: [] as string[], check: given.check ?? 'on',
    lookArgs: [] as string[][], opened: [] as any[], closed: 0, up: false, placed: false, holding: true, narrow: given.narrow ?? false,
    paneChecks: 0,
  }
  const inside = (path: string) => {
    if (path.startsWith('/made-up/')) return
    seen.reached.push(path)
    throw new Error('outside the made-up home')
  }
  on('fs.read', (_: unknown, e: { path: string }) => {
    inside(e.path)
    return seen.files[e.path] === undefined ? { deny: 'ENOENT' } : { value: seen.files[e.path] }
  })
  on('fs.write', (_: unknown, e: { path: string; text: string }) => {
    inside(e.path)
    seen.files[e.path] = e.text
    return { value: undefined }
  })
  on('process.hookEnv', () => ({ value: { CLAUDE_PLUGIN_DATA: DATA, CLAUDE_PROJECT_DIR: ROOT } }))
  on('process.run', async (_: unknown, e: { argv: readonly string[]; init?: { stdin?: string } }) => {
    seen.ran.push([...e.argv])
    seen.inits.push(e.init)
    seen.order.push(e.argv[1] ?? '')
    const [, verb, ...args] = e.argv
    if (verb === 'where') return ok({ folder: FOLDER })
    if (verb === 'propose') {
      if (given.faults) return ok({ id: '', path: '', faults: given.faults, said: 'The proposal has faults.' }, 1)
      if (given.several && !args.includes('--again')) {
        return ok({ id: null, path: null, faults: ['This row may say more than one thing: «a, b and c».'], several: true, said: 'Not kept yet: split it, or send it again.' }, 1)
      }
      const id = `p${seen.ran.filter(a => a[1] === 'propose').length}`
      seen.files[`${FOLDER}/proposals/${id}.json`] = JSON.stringify({ id, ...JSON.parse(seen.files[args[0] ?? ''] ?? '{}') })
      return ok({ id, path: `${FOLDER}/proposals/${id}.json`, faults: [], said: `Stored as ${id}.` })
    }
    if (verb === 'examine') { // the tool's own check, keeping its result beside the proposal
      if (given.examine) return { value: await given.examine() }
      const result = given.examined ?? CHECKED
      seen.files[`${FOLDER}/proposals/${args[0]}.examined.json`] = JSON.stringify(result)
      return ok({ examined: result, said: `Checked ${args[0]}.` })
    }
    if (verb === 'line') { // the line as the hooks wrote it, where the watch recorded that write: a forged one is none
      const text = seen.files[`${FOLDER}/live/${args[0]}.json`]
      if (text === undefined || seen.forged.includes(text)) return ok({ line: null })
      const { line, tension, flags, alert, now, spent, unapproved } = JSON.parse(text)
      return ok({ line, tension, flags: flags ?? {}, alert: alert ?? null, now: now ?? null, spent: spent ?? {}, unapproved: unapproved ?? null })
    }
    if (verb === 'show') { // the proposal and its examination as the files hold them, with the digests they are shown by
      const held = seen.files[`${FOLDER}/proposals/${args[0]}.json`]
      const exam = seen.files[`${FOLDER}/proposals/${args[0]}.examined.json`] ?? null
      if (held === undefined) return ok({ proposal: null, said: 'No such proposal.' }, 1)
      return ok({ proposal: JSON.parse(held), examined: exam === null ? null : JSON.parse(exam), shown: await shownNow(held, exam), check: seen.check })
    }
    if (verb === 'approve') {
      if (given.approve) return { value: await given.approve() }
      seen.copies = { ...seen.copies, 'approved.json': `ticks-${seen.ran.length}` } // the writer wrote them
      return ok({ written: ['.frame/frame.json'], approved: 2, said: 'I approved 2 rows.', word: seen.copies })
    }
    if (verb === 'switch') {
      seen.check = args[0] === 'on' ? 'on' : 'off'
      seen.copies = { ...seen.copies, switch: `${args[0]}\n` }
      return ok({ switch: args[0], said: `The check is now ${args[0]}.`, word: seen.copies })
    }
    if (verb === 'look') { // the look as the contract has it: the word sent puts back each copy that says other
      const sent = e.init?.stdin ?? ''
      seen.looks.push(sent)
      seen.lookArgs.push(args)
      if (!sent) return ok({ copies: seen.copies, digests: Object.fromEntries(Object.entries(seen.copies).map(([k, v]) => [k, v && `sha-${v}`])) })
      const word = JSON.parse(sent) as Record<string, string | null>
      const restored = Object.keys(seen.copies).filter(k => seen.copies[k] !== word[k])
      seen.copies = { ...word }
      return ok(restored.length ? { restored, said: `Put back: ${restored.join(', ')}.` } : { restored })
    }
    return ok({}, 2)
  })
  const stored = new Map<string, unknown>(Object.entries(given.stored ?? {})) // the host's own store, apart from every file
  on('store.get', (_: unknown, e: { key: string }) => ({ value: stored.get(e.key) }))
  on('store.set', (_: unknown, e: { key: string; value: unknown }) => {
    stored.set(e.key, e.value)
    return { value: undefined }
  })
  on('session.root', () => ({ value: ROOT }))
  on('session.id', () => ({ value: 's1' }))
  on('tool.register', (_: unknown, e: { name: string }) => ({ value: { tool: `mcp__frame-loop__${e.name}` } }))
  on('command.register', (_: unknown, e: { name: string }) => ({ value: { command: e.name } }))
  // The pane as the host keeps it: opened, drawn, or left undrawn while the terminal is too narrow for a pane nobody
  // asked for (the person's own open, which the test stands for by widening it), listed, and closed.
  on('ui.open', (_: unknown, e: unknown) => {
    seen.opened.push(e)
    seen.up = true
    seen.placed = seen.placed || !seen.narrow
    return { value: seen.placed ? { isPlaced: true } : { isPlaced: false, reason: 'unasked below 144 columns (100 now)' } }
  })
  on('ui.close', () => {
    seen.uiCalls.push('close')
    seen.closed++
    seen.up = false
    seen.placed = false
    return { value: undefined }
  })
  on('ui.panes', () => {
    seen.uiCalls.push('panes')
    seen.paneChecks++
    return { value: seen.up ? [{ id: 'picker', title: 'frame-loop · pick', isShown: true, isFocused: seen.holding, isPlaced: seen.placed }] : [] }
  })
  on('ui.focus', { plugin: '*' }, (_: unknown, e: any) => { // the pane holds the keyboard where the person gave it: the band's own ask, or the host's move
    seen.focused.push(e)
    seen.uiCalls.push(`focus:${e.origin === undefined ? e.key : e.element ?? ''}`)
    const answer = seen.holding ? {} : { deny: 'the pane does not hold the keyboard' }
    return e.origin === undefined ? { value: answer } : answer
  })
  on('ui.scroll', (_: unknown, e: any) => (e.origin === undefined ? { value: {} } : {})) // the host's window, which the band moves itself
  on('prompt.submit', (_: unknown, e: { text: string; context?: readonly string[] }) => {
    if (given.drop) return { drop: 'not now' } // a hook beneath the band's: the line never enters
    seen.submitted.push(e.text)
    seen.contexts.push(e.context)
    return { text: e.text, ...(e.context ? { context: e.context } : {}) }
  })
  on('turn.complete', (_: unknown, e: { answer: string }) => ({ text: e.answer }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('classic.Stop', () => { // the turn's end hook, beneath the band: it reads the copies as the band left them
    seen.order.push('Stop hook')
    return {}
  })
  on('ui.render', ($: any, e: any) => { // the engine's own row, where the band draws none
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })
  const clock = mock.clock(on, given.now === undefined ? undefined : { now: given.now })
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  // The propose tool as the model calls it: it answers once the proposal is kept, and the check it started runs on.
  const propose = async (fields: Record<string, unknown> = FRAME) => {
    const called = await $.tool.call({ tool: TOOL, ...fields } as any)
    await clock.settle()
    return called
  }
  // A move of the pane's ring as the host raises it, the person's by default; the kit has no ring of its own.
  const ring = async (element: string | undefined, origin: 'person' | 'plugin' = 'person') => {
    const done = await $.ui.focus({ component: 'Pane', requestId: 'picker', ...(element === undefined ? {} : { element, plugin: 'frame-loop' }),
      origin: origin === 'person' ? { kind: 'person' } : { kind: 'plugin', name: 'frame-loop' } } as any).catch(() => undefined)
    await clock.settle()
    return done
  }
  // A key the host's window would move by, as it raises it: an arrow a row, a page key the body's rows, a wheel's tick.
  const scroll = async (by: number, pointer = false) => {
    const done = await $.ui.scroll({ component: 'Pane', requestId: 'picker', offset: 0, by, bodyRows: 40, contentRows: 40, origin: { kind: 'person' },
      ...(pointer ? { pointer: { column: 3, row: 3 } } : {}) } as any).catch(() => undefined)
    await clock.settle()
    return done
  }
  // The pane gone from the host's list: the kit raises no person's close (esc), so a close the band did not hear
  // stands for it here; the hook itself is the picker's `closed` (tests/node/picker.spec.ts) and the live check's.
  const gone = async () => {
    await clock.advance(1000) // listed once
    seen.up = false
    await clock.advance(1000)
  }
  return { seen, clock, stored, propose, ring, scroll, gone }
}
// A command as the person types it at the prompt, or as anyone else runs it.
const typed = (args: string, kind = 'composer') =>
  ({ command: 'frame-loop', args, origin: { kind }, presentation: { isFullscreen: false, columns: 100 } }) as any
const verbs = (seen: { ran: string[][] }) => seen.ran.map(a => a[1])
const HAND = expect.stringMatching(/^\/.+\/hooks\/hand\.sh$/) // the plugin's own launcher, by its absolute path
// A prompt as the person sends it, and a turn's end of the main loop.
const said = (text: string) => ({ text, wait: false, origin: { kind: 'composer' } }) as any
const ended = { answer: 'Done.', durationMs: 5, isAborted: false, turnId: 't1', reason: 'answer' } as any
const flat = (x: any): string => (typeof x === 'string' ? x : (x.children ?? []).map(flat).join('') + (x.props?.label && !x.children?.length ? x.props.label : ''))
// The band as drawn, each line its text, with every colour left out: what the person reads.
const band = async ($: any) => {
  const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
  const tree = await ui.drawn()
  const ours = (tree.children ?? []).filter((child: any) => flat(child) !== 'engine')
  const lines = ours.flatMap((child: any) => (child?.props?.flexDirection === 'column' ? child.children : [child]).map(flat))
  return { ui, lines, text: lines.join('\n') }
}
// The band as drawn, read and unmounted at once.
const peek = async ($: any) => {
  const b = await band($)
  await b.ui.unmount()
  return b
}
// The pane as drawn, a line each row: a stop's lines, the open line as its value or placeholder, the keys line a cell
// in, each hotkey as its meaning alone (the host draws `y: ` before it).
const inputOf = (x: any): any => (x?.type === 'Input' ? x : (x?.children ?? []).map(inputOf).find(Boolean))
const linesOf = (tree: any): string[] => (tree.children ?? []).flatMap((child: any) => {
  if (child?.props?.flexWrap === 'wrap') return [` ${flat(child)}`]
  const input = inputOf(child)
  if (input) {
    const text = input.props.value || input.props.placeholder || ''
    const rows = Math.max(1, input.props.rows ?? 1)
    const width = child.children?.[0]?.props?.width ?? 0
    const ruled = child.children?.[1]?.type === 'Text'
    return Array.from({ length: rows }, (_, i) => {
      const line = `     ${i ? '' : text}`
      return ruled ? line.padEnd(width) + '│' : line
    })
  }
  return flat(child).split('\n')
})
const pane = async ($: any, props: Record<string, unknown> = {}) => {
  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, ...props }, surface: 'terminal' })
  const lines = linesOf(await ui.drawn())
  return { ui, lines, text: lines.join('\n') }
}
const look = async ($: any, props: Record<string, unknown> = {}) => {
  const p = await pane($, props)
  await p.ui.unmount()
  return p
}
const HEAD = ` ${LABELS.name} · ${LABELS.pick}`

test('the tool call keeps the proposal, opens the picker in its pane with the keys asked for, and checks it itself', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await $.prompt.submit(said(SAID))
  const called = await propose()
  expect(verbs(seen)).toEqual(['where', 'look', 'look', 'propose', 'show', 'examine', 'show'])
  expect(seen.ran[5]).toEqual([HAND, 'examine', 'p1', '--session', 's1'])
  expect(seen.inits[5].timeoutMs).toBe(600000)
  expect(called.result).toBe(`Stored as p1.\n${LABELS.checkingTold}\n${LABELS.opened}\n${LABELS.asked}`)
  expect(called.result).not.toContain('frame-loop examine') // the session is not asked to run anything
  expect(JSON.parse(seen.files[`${DATA}/drafts/s1.json`] ?? '')).toEqual(FRAME) // the proposal's fields, nothing of the engine's
  expect(seen.opened[0]).toMatchObject({ id: 'picker', title: `${LABELS.name} · ${LABELS.pick}`, focus: true, closeOnEscape: true,
    backgroundColor: 'transparent', columns: 110 })
  await clock.advance(1000) // the band's clock: opened again as tall as its content, once the rows show
  expect(seen.opened.at(-1).rows).toBeGreaterThan(seen.opened[0].rows)
  const { ui, lines } = await pane($)
  expect(lines[0]).toBe(`${HEAD} · ${LABELS.checked} · 2 rows · 1 ${LABELS.toReview} · row 2 of 2`)
  expect(lines[1]).toBe(' notes')
  expect(lines[2]).toContain(`${LABELS.youSaid}a smal cli app`) // his own words, typos and all
  expect(lines.join('\n')).toContain(`↳ ${QUESTION}`)
  const cursor = await ui.find({ key: 'c1' }) // the first row under review, an element of the host's, with its question
  expect(cursor?.props.autoFocus).toBe(true)
  expect(flat(cursor)).toContain(QUESTION)
  expect((await ui.findAll({ type: 'Button' })).filter((b: any) => b.props.autoFocus).length).toBe(1)
  expect(await ui.find({ key: 'key-o' })).toBeUndefined() // one row is left to review
  await ui.unmount()
  expect((await peek($)).text).toBe('') // the band draws nothing of an open picker: the engine's own row alone
  expect(seen.reached).toEqual([])
})

test('with the check off the picker opens at once, says so, and OK approves the whole, told in one closing line', async ($, on) => {
  const { seen, propose } = await world($, on, { check: 'off' })
  expect((await propose()).result).toBe(`Stored as p1.\n${LABELS.opened}\n${LABELS.asked}`)
  expect(verbs(seen)).not.toContain('examine')
  const { ui, lines } = await pane($)
  expect(lines[0]).toBe(`${HEAD} · ${LABELS.checkOff} · 2 rows · row 1 of 2`)
  await ui.press({ key: 'key-o' })
  expect(seen.ran.at(-1)?.slice(1, 4)).toEqual(['approve', 'p1', '--ticked'])
  expect(seen.ran.at(-1)?.[4]).toBe('0,1')
  expect(seen.submitted.at(-1)).toBe(`I approved 2 rows.\n${LABELS.pickerNow} ${LABELS.pickerEmpty}.`)
  await ui.unmount()
  expect(seen.closed).toBe(1) // the pane is gone
  expect((await peek($)).text).toBe(`${LABELS.name} · ${LABELS.approved} 2 ${LABELS.rows[1]} in notes`)
})

test('turning the check on while a proposal waits gets it checked before /frame-loop reopens it', async ($, on) => {
  const { seen, propose, gone, clock } = await world($, on, { check: 'off' })
  await propose()
  expect(verbs(seen)).not.toContain('examine')
  const first = await pane($)
  expect(first.lines[0]).toContain(LABELS.checkOff)
  await first.ui.unmount()
  await gone()
  await $.command.run(typed('on'))
  await clock.settle()
  expect(seen.check).toBe('on')
  expect(seen.ran.filter(a => a[1] === 'examine').map(a => a[2])).toEqual(['p1'])
  expect((await $.command.run(typed(''))).text).toContain(`${LABELS.pickerHolds} p1`)
  expect((await pane($)).lines[0]).not.toContain(LABELS.checkOff)
})

test('a proposal sent after the switch on is checked, and the one it waits behind is too', async ($, on) => {
  const { seen, propose, clock } = await world($, on, { check: 'off' })
  await propose()
  await $.command.run(typed('on'))
  await clock.settle()
  const second = await propose({ ...FRAME, place: 'web', title: 'notes at web' })
  expect(second.result).toContain(`${LABELS.waitsBehind} p1.`)
  const first = await pane($)
  expect(first.lines[0]).not.toContain(LABELS.checkOff)
  await first.ui.press({ key: 'key-y' })
  await clock.settle()
  await first.ui.unmount()
  const answered = await pane($)
  await answered.ui.press({ key: 'ok' })
  await clock.settle()
  await answered.ui.unmount()
  expect(seen.ran.filter(a => a[1] === 'examine').map(a => a[2])).toEqual(['p1', 'p2'])
  expect((await pane($)).lines[0]).not.toContain(LABELS.checkOff)
})

test('y answers the row under review and counts down, the cursor going on; enter on OK approves', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'key-y' })
  await clock.settle()
  await first.ui.unmount()
  const { ui, lines } = await pane($)
  expect(lines[0]).toBe(`${HEAD} · ${LABELS.checked} · 2 rows · ${LABELS.allAnswered}`)
  expect(lines.some((l: string) => l.includes('--list prints every note') && l.trimEnd().endsWith(LABELS.yes))).toBe(true)
  expect((await ui.find({ key: 'ok' }))?.props.autoFocus).toBe(true) // the cursor on OK, where y left it
  expect(flat(await ui.find({ key: 'ok' }))).toContain(`${LABELS.cursor} ${LABELS.ok}`)
  await ui.press({ key: 'ok' }) // enter on OK
  expect(verbs(seen).at(-1)).toBe('approve')
  await ui.unmount()
})

test('a check that could not run is said in one plain line with retry and close, never OK', async ($, on) => {
  const { seen, propose, clock } = await world($, on, { examined: FAILED })
  await propose()
  const { ui, lines } = await pane($)
  expect(lines[0]).toBe(`${HEAD} · ${LABELS.checkFailed}`)
  expect(lines).toContain(' The check could not run: Gadfly is not installed, as there is no gadfly')
  expect(await ui.find({ key: 'key-o' })).toBeUndefined()
  expect(await ui.find({ key: 'key-r' })).toBeDefined()
  await ui.press({ key: 'key-r' })
  await clock.settle()
  expect(verbs(seen).filter(v => v === 'examine')).toHaveLength(2)
  await ui.unmount()
})

test('an examination that could not even start is a failure too, with the reason the process gave', async ($, on) => {
  const { propose } = await world($, on, { examine: () => ({ exitCode: 1, stdout: '', stderr: 'no Python 3.9 here' }) })
  const called = await propose()
  expect(called.result).toContain(LABELS.opened)
  const { ui, lines } = await pane($)
  expect(lines).toContain(` ${LABELS.checkFailedLead} no Python 3.9 here`)
  expect(await ui.find({ key: 'key-o' })).toBeUndefined()
  await ui.unmount()
})

test('a proposal changed under the open picker is checked again and shown as it now stands', async ($, on) => {
  const { seen, clock, propose } = await world($, on)
  await propose()
  const path = `${FOLDER}/proposals/p1.json`
  const held = JSON.parse(seen.files[path] ?? '{}')
  held.items[0].words = 'add keeps the note' // a shell, keeping the id, while the picker is open
  seen.files[path] = JSON.stringify(held)
  await clock.advance(1000)
  expect(verbs(seen).filter(v => v === 'examine')).toHaveLength(2)
  expect((await look($)).text).toContain('add keeps the note')
})

test('the propose call is one quiet line in the transcript, and its result none', async ($, on) => {
  await world($, on)
  for (const surface of ['terminal', 'desktop'] as const) {
    const row = await $.ui.mount({ plugin: 'frame-loop', component: 'ToolUse', requestId: 'call-1', surface,
      props: { tool_use_id: 'call-1', tool: TOOL, input: FRAME, isRunning: false, isErrored: false, isInterrupted: false } })
    expect((await row.findAll({ type: 'Text' })).map(t => t.text)).toEqual([`${LABELS.name} · ${LABELS.inPicker} · ${LABELS.proposed} notes`])
    await row.unmount()
    const result = await $.ui.mount({ plugin: 'frame-loop', component: 'ToolResult', requestId: 'call-1', surface,
      props: { tool_use_id: 'call-1', tool: TOOL, output: 'Stored as p1.', isErrored: false } })
    expect(await result.findAll({ type: 'Text' })).toEqual([])
    await result.unmount()
    const other = await $.ui.mount({ plugin: 'frame-loop', component: 'ToolUse', requestId: 'call-2', surface,
      props: { tool_use_id: 'call-2', tool: 'Bash', input: { command: 'ls' }, isRunning: false, isErrored: false, isInterrupted: false } })
    expect((await other.find({ type: 'Text' }))?.text).toBe('engine')
    await other.unmount()
  }
})

test('faults go back to the session as the tool’s answer, and no picker opens', async ($, on) => {
  const { seen, propose } = await world($, on, { faults: ['Claim 3 says two things.'] })
  const called = await propose()
  expect(called).toEqual({ deny: 'The proposal has faults.\nClaim 3 says two things.' })
  expect(verbs(seen)).not.toContain('examine')
  expect(seen.opened).toEqual([])
})

test('a row that looks like several claims goes back once: the same proposal sent again is kept, another is asked again', async ($, on) => {
  const { seen, propose } = await world($, on, { several: true })
  const first = await propose()
  expect(first).toEqual({ deny: 'Not kept yet: split it, or send it again.\nThis row may say more than one thing: «a, b and c».' })
  expect(seen.up).toBe(false)
  const other = await propose({ ...FRAME, title: 'notes, split' }) // another proposal: asked again
  expect('deny' in other).toBe(true)
  const turned = FRAME.items.map(i => Object.fromEntries(Object.entries(i).reverse()))
  const again = await propose({ ...FRAME, title: 'notes, split', items: turned }) // the same one again, its keys in another order
  expect('result' in again).toBe(true)
  const sent = seen.ran.filter(a => a[1] === 'propose').map(a => a.slice(3))
  expect(sent).toEqual([[], [], ['--again']])
  expect(seen.up).toBe(true)
})

test('a writer that refuses keeps the picker open with its reason, and submits nothing', async ($, on) => {
  const refused = { written: [], approved: 0, said: 'Nothing is written: the check is on, and 1 of its 2 rows were not checked: «x»' }
  const { seen, propose } = await world($, on, { check: 'off', approve: () => ok(refused, 1).value })
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'key-o' })
  await first.ui.unmount()
  const { ui, lines } = await pane($)
  expect(lines.join('\n').replace(/\n /g, ' ')).toContain(` ${LABELS.writerFailed} ${refused.said}`) // whole, wrapped
  expect(seen.submitted).toEqual([])
  expect(seen.closed).toBe(0)
  await ui.unmount()
})

test('the line at rest: the tree counted once, what needs the eye, and what this session’s checks spent', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  const { seen, clock } = await world($, on)
  await clock.advance(1000)
  const quiet = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await quiet.find({ type: 'Text' }))?.text).toBe('engine')
  await quiet.unmount()
  const turn = 'frame-loop: the work changed in web · files nobody asked for: web/a.py · of 1 the change touches: 1 open'
  seen.files[live] = JSON.stringify({ line: turn, tension: { open: 5, fulfilled: 1, rest: 0, refused: 0 }, flags: { outside: 3 }, spent: { tokens: 175000, calls: 40 }, at: 5 })
  await clock.advance(1000)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...BAND, surface })
    expect((await ui.findAll({ type: 'Text' })).map(t => t.text).filter(t => t !== 'engine').join('')).toBe(`${LABELS.name} · 1 ${LABELS.of} 6 ${LABELS.counts.fulfilled} · 3 ${LABELS.flags.outside[1]} · 175.0k ${LABELS.spend.tokens}`)
    await ui.unmount()
  }
  seen.files[live] = JSON.stringify({ line: 'Nothing here.', tension: { open: 0, fulfilled: 0, rest: 0, refused: 0 }, at: 6 })
  await clock.advance(1000)
  const gone = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await gone.find({ type: 'Text' }))?.text).toBe('engine')
  await gone.unmount()
  expect(seen.reached).toEqual([])
})

test('a line another hand wrote into the live file is never drawn, nor shown by /frame-loop', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  const { seen, clock } = await world($, on)
  seen.files[live] = JSON.stringify({ line: 'Frame 0: one claim open.', tension: { open: 1, fulfilled: 0, rest: 0, refused: 0 }, at: 5 })
  await clock.advance(1000)
  const forged = JSON.stringify({ line: 'frame-loop: ready: nothing under the frame is open', tension: { open: 0, fulfilled: 9, rest: 0, refused: 0 }, at: 6 })
  seen.files[live] = forged
  seen.forged.push(forged) // a job after the turn's end: the watch did not record it
  await clock.advance(1000)
  const shown = await $.ui.mount({ ...BAND, surface: 'terminal' })
  expect((await shown.find({ type: 'Text' }))?.text).toBe('engine') // nothing drawn of it
  await shown.unmount()
  expect((await $.command.run(typed(''))).text).not.toContain('ready')
  expect(verbs(seen).filter(v => v === 'line')).toHaveLength(2) // asked once a change, never drawn from the file
})

test('/frame-loop off runs the switch and shows its sentence; /frame-loop shows the line', async ($, on) => {
  const { seen } = await world($, on, {
    files: { [`${FOLDER}/live/s1.json`]: JSON.stringify({ line: 'One open.', tension: { open: 1 }, at: 1 }) },
  })
  const off = await $.command.run(typed('off'))
  expect(off.text).toBe('The check is now off.')
  expect(seen.ran.at(-1)).toEqual([HAND, 'switch', 'off'])
  const shown = await $.command.run(typed(''))
  expect(shown.text).toBe(`${LABELS.name} · 0 ${LABELS.of} 1 ${LABELS.counts.fulfilled} · 1 ${LABELS.counts.open} · 0 ${LABELS.counts.rest} · 0 ${LABELS.counts.refused}\nOne open.`)
})

// What runs, as the hooks write it into the live file while a check goes on.
const T0 = 1_800_000_000 // seconds since the epoch, where the band's clock starts in these tests
const running = (at: number) => ({ said: 'checking 2 of 5', began: T0, at, until: T0 + 600, writer: 0, maker: 3, records: 12, tokens: 8214 })

test('while a check goes on the band draws what runs in place of the rest, its spinner moving each second', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  const { seen, clock } = await world($, on, { now: (T0 + 47) * 1000 })
  const rest = { line: 'frame-loop: a Bash call is watched.', tension: { open: 1, fulfilled: 0, rest: 0, refused: 0 }, at: T0 }
  seen.files[live] = JSON.stringify({ ...rest, now: running(T0 + 40) })
  await clock.advance(1000)
  const drawn = async () => {
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text).filter(t => t !== 'engine') // the band's own
    await ui.unmount()
    return texts
  }
  expect(await drawn()).toEqual([`${LABELS.spinner[8]} ${LABELS.name} · 48 ${LABELS.seconds} · 8.2k ${LABELS.spend.tokens} · checking 2 of 5`])
  await clock.advance(1000)
  const next = await drawn()
  expect(next[0]?.startsWith(`${LABELS.spinner[9]} `)).toBe(true) // the spinner moves, and the seconds with it
  expect(next[0]).toContain(`49 ${LABELS.seconds}`)
  await clock.advance((STALE_SECONDS + 1) * 1000) // its hook silent: nothing written since
  expect(await drawn()).toEqual([`${LABELS.name} · checking 2 of 5 · ${LABELS.ended}`])
  seen.files[live] = JSON.stringify(rest) // the next event wrote its line, with nothing running
  await clock.advance(1000)
  expect(await drawn()).toEqual([LABELS.name, ` · 0 ${LABELS.of} 1 ${LABELS.counts.fulfilled}`])
  expect(seen.reached).toEqual([])
})

test('a line that tells a failure or an alert wraps whole, and is never cut at its end', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  const failed = `frame-loop: the check could not run: ${'a reason long and whole, '.repeat(8)}and its end. It runs again at the next turn's end.`
  const { seen, clock, propose, gone } = await world($, on, { now: T0 * 1000 })
  const warned = async () => {
    const ui = await $.ui.mount({ ...BAND, surface: 'terminal' })
    const found = (await ui.findAll({ type: 'Text' })).filter((t: any) => t.props.color === 'warning')
    await ui.unmount()
    return found.map((t: any) => [t.text, t.props.wrap])
  }
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 1, fulfilled: 0, rest: 0, refused: 0 }, at: T0, alert: failed })
  await clock.advance(1000)
  expect(await warned()).toEqual([[failed, 'wrap']]) // the alert at rest
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 1 }, at: T0, now: running(T0) })
  await clock.advance((STALE_SECONDS + 2) * 1000)
  expect(await warned()).toEqual([[`${LABELS.name} · checking 2 of 5 · ${LABELS.ended}`, 'wrap']]) // a run ended without a word
  await propose()
  await gone() // closed by esc: the alert above the line that says it waits
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 1 }, at: T0 + 60, alert: failed })
  await clock.advance(1000)
  expect(await warned()).toEqual([[failed, 'wrap']])
})

test('an examination that answers nothing is a failure too, and never OK', async ($, on) => {
  const { seen, propose } = await world($, on, { now: T0 * 1000, examine: () => ({ exitCode: 0, stdout: '', stderr: '' }) })
  await propose() // no examination was kept: the picker shows the check failed
  const { ui, lines } = await pane($)
  expect(lines.some((l: string) => l.includes(LABELS.checkFailedLead))).toBe(true)
  expect(await ui.find({ key: 'key-o' })).toBeUndefined()
  await ui.unmount()
  expect(seen.reached).toEqual([])
})

test('/frame-loop on and off are the person’s own: run by anyone else, nothing switches', async ($, on) => {
  const { seen } = await world($, on)
  for (const kind of ['plugin', 'sdk', 'peer']) expect((await $.command.run(typed('on', kind))).text).toBe(LABELS.personOnly)
  expect(verbs(seen)).not.toContain('switch')
})

test('the band keeps the word its own writes answer, and its look puts it back before the turn’s end hook reads it', async ($, on) => {
  const { seen, clock, propose } = await world($, on, { check: 'off' })
  await clock.advance(1000)
  expect((await $.prompt.submit(said('Hello.'))).context).toBeUndefined() // nothing kept, nothing held: nothing told
  await propose()
  const { ui } = await pane($)
  await ui.press({ key: 'key-o' }) // the band's own write, whose sentence it submits as the next prompt
  await ui.unmount()
  const word = { ...seen.copies }
  const picker = `${LABELS.pickerNow} ${LABELS.pickerEmpty}.` // told at each prompt, once the session proposed
  expect(seen.contexts.at(-1)).toBeUndefined() // its own write is no change
  expect(seen.submitted.at(-1)?.endsWith(`\n${picker}`)).toBe(true) // its own submit carries the picker in its text
  seen.copies = { ...seen.copies, 'approved.json': 'written-by-another-hand' } // a shell, in the turn
  seen.order = []
  await $.classic.Stop({ stop_hook_active: false } as any)
  expect(seen.order).toEqual(['look', 'Stop hook']) // the look first: the hook reads the word put back
  expect(JSON.parse(seen.looks.at(-1) ?? '')).toEqual(word) // the word its own write answered
  expect(seen.copies).toEqual(word)
  expect((await $.prompt.submit(said('What changed?'))).context).toEqual(['Put back: approved.json.', picker])
  expect((await $.prompt.submit(said('And now?'))).context).toEqual([picker]) // told once
  seen.copies = { ...seen.copies, switch: 'on\n' } // a job after the turn's end
  expect((await $.prompt.submit(said('Once more.'))).context).toEqual(['Put back: switch.', picker]) // before the prompt's hook
  const off = await $.command.run(typed('off'))
  expect(off.text).toBe('The check is now off.')
  expect((await $.prompt.submit(said('Off, by my hand.'))).context).toEqual([picker]) // its own switch is no change
  expect(JSON.parse(seen.looks.at(-1) ?? '')).toEqual({ ...word, switch: 'off\n' })
  void ended
})

test('a band that kept nothing for a folder takes out what the copies hold: a first look is never silent', async ($, on) => {
  const { seen } = await world($, on)
  seen.copies = { 'approved.json': 'ticked-before', switch: 'on\n' }
  expect((await $.prompt.submit(said('Hello.'))).context).toEqual(['Put back: approved.json, switch.'])
  expect(seen.copies).toEqual({ 'approved.json': null, switch: null }) // nothing it never wrote counts
})

test('the band takes its word from the copies where its first witness kept their digests as they stand', async ($, on) => {
  const kept = { 'approved.json': 'sha-ticked-by-the-band', switch: 'sha-on\n' }
  const { seen, stored } = await world($, on, { stored: { [`kept-digests:${FOLDER}`]: kept } })
  seen.copies = { 'approved.json': 'ticked-by-the-band', switch: 'on\n' }
  expect((await $.prompt.submit(said('Hello again.'))).context).toBeUndefined()
  expect(stored.get(`word:${FOLDER}`)).toEqual({ 'approved.json': 'ticked-by-the-band', switch: 'on\n' })
})

test('while the check runs the pane shows the spinner header, the path and his sentence, and asks him to wait', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  let done = false
  const { seen, clock } = await world($, on, { now: T0 * 1000, examine: async () => {
    await clock.sleep(30_000) // the check takes its time
    done = true
    seen.files[`${FOLDER}/proposals/p1.examined.json`] = JSON.stringify(CHECKED)
    return ok({ examined: CHECKED, said: 'Checked p1.' }).value
  } })
  await $.prompt.submit(said(SAID))
  const called = await Promise.race([$.tool.call({ tool: TOOL, ...FRAME } as any), clock.settle().then(() => null)])
  expect(called?.result).toBe(`Stored as p1.\n${LABELS.checkingTold}\n${LABELS.opened}\n${LABELS.asked}`) // before the check ends
  expect(done).toBe(false)
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 0 }, at: T0, now: { ...running(T0 + 4), said: 'checking 1 of 2' } })
  await clock.advance(5000)
  const during = await pane($)
  expect(during.lines[0]).toMatch(new RegExp(`^ . ${LABELS.name} · 5 ${LABELS.seconds} · .+ · checking 1 of 2$`))
  expect(during.lines.slice(1)).toEqual([' notes', `   ${LABELS.youSaid}${SAID.slice(0, 64)}${LABELS.cut}`, ' ', ` ${LABELS.pleaseWait}`])
  expect(await during.ui.findAll({ type: 'Button' })).toEqual([]) // no row yet, and no stop
  await during.ui.unmount()
  expect((await peek($)).text).toBe('') // the band draws nothing of it: the pane's header is the running line
  await clock.advance(30_000)
  expect(done).toBe(true)
  const after = await pane($)
  expect(after.lines[0]).toContain(`2 rows · 1 ${LABELS.toReview}`)
  expect((await after.ui.find({ key: 'c1' }))?.props.autoFocus).toBe(true)
  await after.ui.unmount()
})

test('the last line is always there: without the keyboard it says how to give it, with it the keys, the hotkeys the host’s', async ($, on) => {
  const { propose } = await world($, on)
  await propose()
  const before = await pane($, { isFocused: false })
  expect(before.lines[0]).toBe(`${HEAD} · ${LABELS.checked} · 2 rows · 1 ${LABELS.toReview} · row 2 of 2`) // no hint in the header
  expect(before.lines.at(-1)).toBe(` ${LABELS.hintAll} · ${LABELS.toAnswer} y yes, fine · enter confirm or change · d details`)
  expect(await before.ui.find({ key: 'key-y' })).toBeUndefined()
  expect((await before.ui.find({ key: 'c1' }))?.props.autoFocus).toBe(true) // ctrl+x tab: the ring starts on the cursor
  await before.ui.unmount()
  const after = await pane($)
  expect(after.lines[0]).toBe(before.lines[0])
  expect(after.lines.at(-1)).toContain(`esc ${LABELS.keys.close}`)
  expect((await after.ui.find({ key: 'key-y' }))?.props.hotkey).toBe('y')
  expect((await after.ui.find({ key: 'key-h' }))?.props.hotkey).toBe('h')
  expect(await after.ui.find({ key: 'key-x' })).toBeUndefined() // nothing closes it but OK, a change and esc
  await after.ui.unmount()
})

test('h opens the key list; h again closes it on the same mark, whose enter approves, the ring asked for after each drawing', async ($, on) => {
  const { seen, propose, clock, ring } = await world($, on, { check: 'off' })
  await propose()
  await ring('ok')
  const held = await pane($)
  const before = linesOf(await held.ui.drawn())
  const first = seen.uiCalls.length
  const checks = seen.paneChecks
  await held.ui.press({ key: 'key-h' })
  await clock.settle()
  expect(seen.paneChecks).toBeGreaterThan(checks) // the kit lands no plugin's focus; it holds the wait before the ask
  expect(seen.uiCalls.slice(first)[0]).toBe('panes')
  expect((await held.ui.find({ key: 'ok' }))?.props.autoFocus).toBe(true)
  expect((await held.ui.find({ key: 'key-h' }))?.props.hotkey).toBe('h') // the list's own h closes it
  expect(linesOf(await held.ui.drawn()).at(-1)).toBe(` ${LABELS.keys.listClose} · ${LABELS.keys.esc} ${LABELS.keys.listClose}`)
  const second = seen.uiCalls.length
  const again = seen.paneChecks
  await held.ui.press({ key: 'key-h' })
  await clock.settle()
  expect(seen.uiCalls.slice(second)[0]).toBe('panes')
  expect(seen.paneChecks).toBeGreaterThan(again)
  expect(linesOf(await held.ui.drawn())).toEqual(before)
  expect((await held.ui.find({ key: 'ok' }))?.props.autoFocus).toBe(true)
  await held.ui.press({ key: 'ok' })
  await clock.settle()
  expect(verbs(seen).filter(verb => verb === 'approve')).toHaveLength(1)
})

test('d opens a row’s details; d again closes them on the same row, whose line still opens, the ring asked for after each drawing', async ($, on) => {
  const { seen, propose, clock } = await world($, on, { check: 'off' })
  await propose()
  const held = await pane($)
  const before = linesOf(await held.ui.drawn())
  const first = seen.uiCalls.length
  const checks = seen.paneChecks
  await held.ui.press({ key: 'key-d' })
  await clock.settle()
  expect(seen.uiCalls.slice(first)[0]).toBe('panes')
  expect(seen.paneChecks).toBeGreaterThan(checks)
  expect(linesOf(await held.ui.drawn()).length).toBeGreaterThan(before.length)
  expect((await held.ui.find({ key: 'c0' }))?.props.autoFocus).toBe(true)
  const second = seen.uiCalls.length
  const again = seen.paneChecks
  await held.ui.press({ key: 'key-d' })
  await clock.settle()
  expect(seen.uiCalls.slice(second)[0]).toBe('panes')
  expect(seen.paneChecks).toBeGreaterThan(again)
  expect(linesOf(await held.ui.drawn())).toEqual(before)
  await held.ui.press({ key: 'c0' })
  await clock.settle()
  expect(await held.ui.find({ key: INPUT })).toBeDefined()
})

test('tab, shift+tab and the arrows walk the stops and never close the pane: twenty moves each way, round at either end', async ($, on) => {
  const { seen, propose, ring, scroll } = await world($, on, { check: 'off' })
  await propose()
  const stops = ['c0', 'c1', 'ok']
  const held = await pane($) // drawn while he moves
  const cursor = async () => linesOf(await held.ui.drawn())[0] ?? ''
  for (let k = 0; k < 20; k++) await ring('key-h') // past the last stop onto the last line: the cursor down, round again
  expect(stops[20 % stops.length]).toBe('ok')
  expect(await cursor()).toBe(`${HEAD} · ${LABELS.checkOff} · 2 rows`) // on OK
  expect((await held.ui.find({ key: 'ok' }))?.props.autoFocus).toBe(true)
  for (let k = 0; k < 20; k++) await ring('head') // past the first onto the header: up, round again
  expect(await cursor()).toContain('row 1 of 2')
  for (let k = 0; k < 20; k++) expect(await ring(undefined)).toEqual({}) // off every element: kept on the list
  for (let k = 0; k < 20; k++) await scroll(k % 2 ? 1 : -1) // the arrows where the host would scroll its window
  expect(await cursor()).toContain('row 1 of 2')
  await ring('c1') // the ring landing on a stop of its own moves the cursor there
  expect(await cursor()).toContain('row 2 of 2')
  await held.ui.unmount()
  expect(seen.closed).toBe(0)
  expect(seen.opened.length).toBe(1)
})

test('page down and page up move the cursor a page of the list, the window with it, and the header says where', async ($, on) => {
  const { propose, scroll } = await world($, on, { check: 'off' })
  const long = { ...FRAME, items: [...Array(12).keys()].map(k => ({ words: `row ${k} of a long list`, of: SAID, owner: 'work', ask: `Row ${k}? OK?` })) }
  await propose(long)
  const rows = 12
  const shown = async () => (await look($, { scroll: { offset: 0, bodyRows: rows } })).lines
  const first = await shown()
  expect(first.length).toBeLessThanOrEqual(rows) // the header and the last line stay; the rest windowed
  expect(first[0]).toBe(`${HEAD} · ${LABELS.checkOff} · 12 rows · 12 ${LABELS.toReview} · row 1 of 12`)
  expect(first.at(-2)).toMatch(new RegExp(`^ ${LABELS.below} \\d+ ${LABELS.more}$`))
  await scroll(rows) // page down
  const down = await shown()
  const at = Number(/row (\d+) of 12/.exec(down[0] ?? '')?.[1])
  expect(at).toBeGreaterThan(2)
  expect(down.filter((l: string) => l.includes(LABELS.cursor)).map((l: string) => l.split('│')[0]?.trimEnd())).toEqual([` ${LABELS.cursor} row ${at - 1} of a long list`])
  expect(down.at(-2)).toMatch(new RegExp(`^ ${LABELS.above} \\d+ ${LABELS.more} · ${LABELS.below} \\d+ ${LABELS.more}$`))
  for (let k = 0; k < 10; k++) await scroll(rows)
  expect((await shown()).some((l: string) => l.startsWith(` ${LABELS.cursor} ${LABELS.ok}`))).toBe(true) // no further than OK
  for (let k = 0; k < 10; k++) await scroll(-rows)
  expect((await shown())[0]).toContain('row 1 of 12')
  await scroll(1, true) // a wheel's tick: the next stop
  expect((await shown())[0]).toContain('row 2 of 12')
})

test('the pane closed, as by esc: the proposal waits with its answers, the band says /frame-loop reopens it, which it does', async ($, on) => {
  const { seen, propose, gone } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'key-y' })
  await first.ui.unmount()
  await gone()
  const aside = await peek($)
  expect(aside.text).toBe(`${LABELS.name} · ${LABELS.waiting} · ${LABELS.reopens}`)
  expect(await aside.ui.find({ type: 'Button' }).catch(() => undefined)).toBeUndefined()
  expect((await $.command.run(typed(''))).text).toContain(`${LABELS.pickerHolds} p1`)
  expect(seen.up).toBe(true) // opened again at his command
  expect(seen.opened.at(-1)).toMatchObject({ id: 'picker', focus: true, closeOnEscape: true })
  expect((await look($)).lines[0]).toContain(LABELS.allAnswered) // his yes kept
  expect((await peek($)).text).toBe('')
  expect(verbs(seen)).not.toContain('approve')
})

test('enter on a row opens one line under it with the keyboard in it; enter with words sends his change to that row', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const first = await pane($)
  expect(first.lines.at(-1)).toContain(`enter ${LABELS.keys.choose}`)
  await first.ui.press({ key: 'c1' }) // enter on the row under review
  await clock.settle()
  await first.ui.unmount()
  const open = await pane($)
  const row = open.lines.findIndex((l: string) => l.includes('--list prints every note'))
  expect(open.lines[row]?.trimEnd().endsWith(LABELS.review)).toBe(true) // nothing answered or changed yet
  expect(open.lines[row + 2]).toBe(`     ${LABELS.inputHint}`.padEnd(70) + '│') // under the row and its question
  expect((await open.ui.find({ key: INPUT }))?.props).toMatchObject({ placeholder: LABELS.inputHint, submitLabel: '', autoFocus: true, rows: 1, value: '' })
  expect(open.lines.at(-1)).toBe(` enter ${LABELS.keys.confirm} · esc ${LABELS.keys.back}`)
  expect(open.lines.filter((l: string) => /type|write/i.test(l))).toEqual([open.lines[row + 2]]) // the hint to write is only in the line
  expect((await open.ui.findAll({ type: 'Button' })).filter((b: any) => b.props.autoFocus)).toEqual([])
  expect((await open.ui.findAll({ type: 'Input' })).filter((i: any) => i.props.autoFocus)).toHaveLength(1)
  await open.ui.input({ key: INPUT, text: 'start the numbers at 0', kind: 'change' })
  await clock.settle()
  await open.ui.unmount()
  const typing = await pane($)
  expect(typing.lines[row]?.trimEnd().endsWith(LABELS.review)).toBe(true)
  expect(typing.lines[row + 2]).toBe(`     start the numbers at 0`.padEnd(70) + '│')
  expect((await typing.ui.find({ key: INPUT }))?.props).toMatchObject({ autoFocus: true, value: 'start the numbers at 0' })
  expect(typing.lines.at(-1)).toBe(` enter ${LABELS.keys.send} · esc ${LABELS.keys.back}`)
  expect(await typing.ui.find({ key: 'key-y' })).toBeUndefined() // every key is his words while he types
  expect(seen.submitted).toEqual([]) // nothing sent until he presses enter there
  await typing.ui.input({ key: INPUT, text: 'start the numbers at 0' })
  await typing.ui.unmount()
  expect(seen.submitted.at(-1)?.split('\n').slice(0, 3)).toEqual(['start the numbers at 0', // his line, as he typed it
    `${LABELS.changeRow} p1: “--list prints every note, numbered from 1”.`, LABELS.changeTold])
  expect(seen.closed).toBe(1) // closed while the session answers
  expect((await peek($)).text).toBe(`${LABELS.name} · ${LABELS.changeSent} · ${LABELS.opensAgain}`)
  await $.turn.complete(ended) // the session made no new proposal: the same one again
  expect(seen.up).toBe(true)
  expect((await look($)).lines[0]).toContain(`2 rows · 1 ${LABELS.toReview}`)
  expect(verbs(seen)).not.toContain('approve')
})

test('enter in the empty line answers a row under review yes, as y does; spaces alone are empty', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await clock.settle()
  await first.ui.unmount()
  const typed_ = await pane($)
  await typed_.ui.input({ key: INPUT, text: '  ', kind: 'change' })
  await clock.settle()
  await typed_.ui.unmount()
  const spaces = await pane($)
  expect(spaces.lines.at(-1)).toBe(` enter ${LABELS.keys.confirm} · esc ${LABELS.keys.back}`) // spaces alone are empty
  expect(seen.submitted).toEqual([])
  expect(seen.closed).toBe(0)
  await spaces.ui.input({ key: INPUT, text: '  ' }) // enter in the empty line
  await clock.settle()
  await spaces.ui.unmount()
  const after = await pane($)
  expect(after.lines[0]).toContain(LABELS.allAnswered)
  expect(after.lines.some((l: string) => l.includes(LABELS.inputHint))).toBe(false) // the line closed
  expect(after.lines.some((l: string) => l.includes('--list prints every note') && l.trimEnd().endsWith(LABELS.yes))).toBe(true)
  expect((await after.ui.find({ key: 'ok' }))?.props.autoFocus).toBe(true) // on to OK after the last
  await after.ui.unmount()
  expect(seen.submitted).toEqual([])
})

test('after enter confirms a row, enter opens the line under the next row the mark shows', async ($, on) => {
  const { seen, propose, clock } = await world($, on, { examined: BOTH })
  await propose()
  const first = await pane($)
  expect(first.lines[0]).toContain(`2 ${LABELS.toReview}`)
  const before = seen.paneChecks
  await first.ui.press({ key: 'c0' }) // enter on the first row under review
  await clock.settle()
  expect(await first.ui.find({ key: INPUT })).toBeDefined()
  await first.ui.input({ key: INPUT, text: '' }) // enter in the empty line: yes
  await clock.settle()
  expect(seen.paneChecks).toBeGreaterThan(before) // the ring was asked again only after the next drawing
  expect(await first.ui.find({ key: INPUT })).toBeUndefined()
  expect((await first.ui.find({ key: 'c1' }))?.props.autoFocus).toBe(true) // the mark is on the next under review
  await first.ui.press({ key: 'c1' }) // enter there
  await clock.settle()
  expect(await first.ui.find({ key: INPUT })).toBeDefined() // its line opened
  const lines = linesOf(await first.ui.drawn())
  const row = lines.findIndex((line: string) => line.includes('--list prints every note'))
  expect(lines[row + 2]).toContain(LABELS.inputHint)
})

test('with one row left under review, enter, enter, then enter approves the proposal', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const first = await pane($)
  const before = seen.paneChecks
  await first.ui.press({ key: 'c1' })
  await clock.settle()
  await first.ui.input({ key: INPUT, text: '' })
  await clock.settle()
  expect(seen.paneChecks).toBeGreaterThan(before)
  expect((await first.ui.find({ key: 'ok' }))?.props.autoFocus).toBe(true) // the mark is on OK
  await first.ui.press({ key: 'ok' })
  await clock.settle()
  expect(verbs(seen).filter(verb => verb === 'approve')).toHaveLength(1)
  expect(seen.ran.at(-1)?.slice(1, 4)).toEqual(['approve', 'p1', '--ticked'])
  expect(seen.submitted.at(-1)).toBe(`I approved 2 rows.\n${LABELS.pickerNow} ${LABELS.pickerEmpty}.`)
})

test('enter, back off the line, then enter opens the same row’s line again', async ($, on) => {
  const { seen, propose, clock, ring } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await clock.settle()
  expect(await first.ui.find({ key: INPUT })).toBeDefined()
  const before = seen.paneChecks
  await ring('c1') // the host's ring leaves the line for the row itself
  expect(seen.paneChecks).toBeGreaterThan(before) // the ask waits for the drawing without the line
  expect(await first.ui.find({ key: INPUT })).toBeUndefined()
  await first.ui.press({ key: 'c1' })
  await clock.settle()
  expect(await first.ui.find({ key: INPUT })).toBeDefined()
})

test('enter in an empty line closes a row not under review or You said, unanswered; words under You said change the whole', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await $.prompt.submit(said(SAID))
  await propose()
  const sentBefore = seen.submitted.length
  const first = await pane($)
  await first.ui.press({ key: 'c0' }) // a Clear row
  await clock.settle()
  await first.ui.unmount()
  const clear = await pane($)
  await clear.ui.input({ key: INPUT, text: '' })
  await clock.settle()
  await clear.ui.unmount()
  const closed = await pane($)
  expect(closed.lines.some((l: string) => l.includes(LABELS.inputHint))).toBe(false)
  expect(closed.lines[0]).toContain(`1 ${LABELS.toReview}`)
  expect((await closed.ui.find({ key: 'c0' }))?.props.autoFocus).toBe(true)
  await closed.ui.unmount()
  const said_ = await pane($)
  await said_.ui.press({ key: 'said' })
  await clock.settle()
  await said_.ui.unmount()
  const whole = await pane($)
  expect(whole.lines.at(-1)).toBe(` enter ${LABELS.keys.confirm} · esc ${LABELS.keys.back}`)
  await whole.ui.input({ key: INPUT, text: '' })
  await clock.settle()
  await whole.ui.unmount()
  const shut = await pane($)
  expect(shut.lines.some((l: string) => l.includes(LABELS.inputHint))).toBe(false) // empty closes it
  expect(seen.submitted).toHaveLength(sentBefore)
  await shut.ui.unmount()
  const again = await pane($)
  await again.ui.press({ key: 'said' })
  await clock.settle()
  await again.ui.unmount()
  const changing = await pane($)
  await changing.ui.input({ key: INPUT, text: 'start the numbers at 0', kind: 'change' })
  await clock.settle()
  await changing.ui.input({ key: INPUT, text: 'start the numbers at 0' })
  await clock.settle()
  await changing.ui.unmount()
  expect(seen.submitted.at(-1)?.split('\n').slice(0, 2)).toEqual(['start the numbers at 0', `${LABELS.changeWhole} p1.`])
})

test('a change longer than its line wraps inside the table: the Input is as many rows tall as the drawn rule', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await first.ui.unmount()
  const typing = await pane($)
  const long = 'start the numbers at zero, and keep each note to one line of at most eighty characters please'
  await typing.ui.input({ key: INPUT, text: long, kind: 'change' } as any) // each key as the host tells it
  await clock.settle()
  await typing.ui.unmount()
  const grown = await pane($)
  const field = (await grown.ui.find({ key: INPUT }))?.props
  expect(field).toMatchObject({ value: long })
  expect(field.rows).toBeGreaterThan(1)
  const line = (await grown.ui.drawn()).children.find((c: any) => inputOf(c))
  expect(flat(line.children[1]).split('\n')).toHaveLength(field.rows)
  expect(line.children[0].props.width).toBe(70) // up to the table's rule, at the pane's 78 columns
  await grown.ui.unmount()
  expect(seen.submitted).toEqual([]) // typing sends nothing
})

test('the ring moved off the line closes it, nothing sent and nothing answered', async ($, on) => {
  const { seen, propose, clock, ring } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await clock.settle()
  await first.ui.unmount()
  await ring('c0')
  const moved = await pane($)
  expect(moved.lines.some((l: string) => l.includes(LABELS.inputHint))).toBe(false)
  expect(moved.lines[0]).toContain(`1 ${LABELS.toReview}`)
  await moved.ui.unmount()
  expect(seen.submitted).toEqual([])
})

test('a plugin focus retry, or a focus with no element, leaves the line and its words open', async ($, on) => {
  const { propose, clock, ring } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await clock.settle()
  await first.ui.unmount()
  const typing = await pane($)
  await typing.ui.input({ key: INPUT, text: 'keep this change', kind: 'change' })
  await clock.settle()
  await typing.ui.unmount()
  await ring('c1', 'plugin') // a stale ring retry from before the line opened
  await ring(undefined, 'plugin')
  await ring(undefined, 'person') // the ring did not move off the line
  const held = await pane($)
  expect((await held.ui.find({ key: INPUT }))?.props.value).toBe('keep this change')
  expect(held.lines.at(-1)).toBe(` enter ${LABELS.keys.send} · esc ${LABELS.keys.back}`)
  await held.ui.unmount()
})

test('a line he types at the host’s prompt is a change to the whole proposal, even with a row’s line open', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await first.ui.unmount()
  const sent = await $.prompt.submit(said('and a delete command'))
  expect(sent.context).toEqual([`${LABELS.changeWhole} p1.`, LABELS.changeTold, `${LABELS.pickerNow} ${LABELS.pickerHolds} p1, ${LABELS.pickerChanged}.`,
    LABELS.unapprovedTold])
  expect(seen.closed).toBe(1)
  const again = await propose({ ...FRAME, place: 'web', kind: 'frame', title: 'notes with delete' }) // its answer, whatever its place
  expect(again.result).toContain(`${LABELS.replaced} p1${LABELS.replacedTail}`)
  await clock.settle()
  const { lines } = await look($)
  expect(lines[0]).toContain(`${LABELS.pick} · ${LABELS.checked}`)
  expect(lines[1]).toBe(' notes → web')
  await $.turn.complete(ended)
  expect((await look($)).lines[1]).toBe(' notes → web') // the new one stays open
  expect(verbs(seen)).not.toContain('approve')
})

test('a change that never entered, dropped by another hook, opens the picker again at once', async ($, on) => {
  const { seen, propose } = await world($, on, { drop: true }) // beneath the band: the line never reaches the session
  await propose()
  await $.prompt.submit(said('wait'))
  expect((await look($)).lines[0]).toContain(LABELS.toReview)
  const first = await pane($)
  await first.ui.press({ key: 'c1' })
  await first.ui.unmount()
  const line = await pane($)
  await line.ui.input({ key: INPUT, text: 'start at 0' })
  await line.ui.unmount()
  expect(seen.up).toBe(true)
  expect((await look($)).lines[0]).toContain(LABELS.toReview)
})

test('the session withdraws a proposal only at his word: refused without a change of his, done after one', async ($, on) => {
  const { seen, propose } = await world($, on)
  await propose()
  const refused = await $.tool.call({ tool: 'mcp__frame-loop__withdraw', id: 'p1' } as any)
  expect(refused).toEqual({ deny: `${LABELS.withdrawRefused} p1.` })
  expect((await look($)).lines[0]).toContain(LABELS.toReview)
  await $.prompt.submit(said('drop it, I changed my mind'))
  const done = await $.tool.call({ tool: 'mcp__frame-loop__withdraw', id: 'p1' } as any)
  expect(done.result).toBe(`${LABELS.proposal} p1 ${LABELS.withdrawn}\n${LABELS.pickerNow} ${LABELS.pickerEmpty}.`)
  expect((await peek($)).text).toBe('')
  expect(seen.up).toBe(false)
  expect(verbs(seen)).not.toContain('approve')
})

test('without the keyboard the pane says what a line typed at the prompt sends, and the hint goes as it closes', async ($, on) => {
  const { propose } = await world($, on, { check: 'off' })
  await propose()
  expect((await look($, { isFocused: false })).lines.at(-1)).toContain(LABELS.hintAll)
  await ($.prompt as any).edit({ text: '', cursor: 0, start: 0, end: 0, inputText: 'h', origin: { kind: 'composer' } }).catch(() => undefined)
  const typed_ = await look($, { isFocused: false })
  expect(typed_.lines[0]).toContain(LABELS.checkOff)
  expect(typed_.lines.at(-1)?.startsWith(` ${LABELS.sendsAll} · ${LABELS.toAnswer}`)).toBe(true)
  const held = await pane($)
  await held.ui.press({ key: 'key-o' }) // approved: the picker closes
  await held.ui.unmount()
  const after = await peek($)
  expect(after.text).not.toContain(LABELS.hintAll)
  expect(after.text).not.toContain(LABELS.sendsAll)
})

test('after the turn his approval started, the band at rest says how many passed of how many, not what was approved', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  const { seen, clock, propose } = await world($, on, { check: 'off' })
  await propose()
  const { ui } = await pane($)
  await ui.press({ key: 'key-o' })
  await ui.unmount()
  expect((await peek($)).text).toBe(`${LABELS.name} · ${LABELS.approved} 2 ${LABELS.rows[1]} in notes`)
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 1, fulfilled: 1, rest: 0, refused: 0 }, spent: { tokens: 168100 }, at: 9 })
  await clock.advance(1000)
  await $.turn.complete(ended) // the turn that built it ended
  expect((await peek($)).text).toBe(`${LABELS.name} · 1 ${LABELS.of} 2 ${LABELS.counts.fulfilled} · 168.1k ${LABELS.spend.tokens}`)
})

test('where the host leaves the pane undrawn, the band says a proposal waits and /frame-loop opens it, which draws it', async ($, on) => {
  const { seen, propose, clock } = await world($, on, { check: 'off', narrow: true })
  await propose()
  expect(seen.placed).toBe(false)
  expect((await peek($)).text).toBe(`${LABELS.name} · ${LABELS.waiting} · ${LABELS.opens}`)
  await clock.advance(1000)
  expect((await peek($)).text).toBe(`${LABELS.name} · ${LABELS.waiting} · ${LABELS.opens}`) // the host's list says so too
  const opens = seen.opened.length
  seen.narrow = false // the person's own open is drawn at any width
  await $.command.run(typed(''))
  expect(seen.opened.length).toBe(opens + 1)
  expect(seen.placed).toBe(true)
  expect((await peek($)).text).toBe('')
})

test('a pane drawn but never given the keyboard: the band says ctrl+x tab answers it, until the pane holds the keys', async ($, on) => {
  const { seen, propose, clock, ring } = await world($, on, { check: 'off' })
  seen.holding = false // text in his prompt, say: the host opens the pane without the keyboard
  await propose()
  await clock.advance(1000)
  expect((await peek($)).text).toBe('') // a moment for the host to give it
  await clock.advance(1000)
  expect((await peek($)).text).toBe(`${LABELS.name} · ${LABELS.waiting} · ${LABELS.answers}`)
  seen.holding = true
  await ring('c0', 'plugin') // ctrl+x tab: the cursor's element takes the ring
  await clock.advance(1000)
  expect((await peek($)).text).toBe('')
})

test('files changed while a proposal waits: the failure stands under the pane’s header and in the band, until it is closed', async ($, on) => {
  const live = `${FOLDER}/live/s1.json`
  const failed = 'frame-loop failed: 3 files changed while proposal p1 waited in the picker, and nothing of it is approved. Approve it there, or close it.'
  const { seen, clock, propose, gone } = await world($, on)
  await propose()
  await $.classic.Stop({ stop_hook_active: false } as any) // each look names what the picker holds, none of it approved
  expect(seen.lookArgs.at(-1)).toEqual(['--session', 's1', '--waiting', 'p1'])
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 0 }, at: 5, alert: failed, unapproved: { said: failed, files: 3, proposals: ['p9'] } })
  await clock.advance(1000)
  expect((await look($)).text).not.toContain('failed') // not a proposal of this picker's: nothing of it drawn
  seen.files[live] = JSON.stringify({ line: 'x', tension: { open: 0 }, at: 6, alert: failed, unapproved: { said: failed, files: 3, proposals: ['p1'] } })
  await clock.advance(1000)
  expect((await look($)).lines[1]?.startsWith(' frame-loop failed: 3 files changed while proposal p1 waited')).toBe(true) // under the header
  expect((await peek($)).lines).toEqual([failed]) // and the band's alert
  await gone()
  expect((await peek($)).lines).toEqual([failed, `${LABELS.name} · ${LABELS.waiting} · ${LABELS.reopens}`])
  await $.prompt.submit(said('drop it')) // closed by esc, his line is no change: the session withdraws nothing
  expect((await $.tool.call({ tool: 'mcp__frame-loop__withdraw', id: 'p1' } as any)).deny).toBeDefined()
  await $.command.run(typed(''))
  await $.prompt.submit(said('drop it')) // his change, and the session withdraws it at his word
  await $.tool.call({ tool: 'mcp__frame-loop__withdraw', id: 'p1' } as any)
  expect((await peek($)).text).not.toContain('failed')
  expect((await $.prompt.submit(said('ok'))).context).toEqual([`${LABELS.proposal} p1 ${LABELS.closedUnwritten}`, `${LABELS.pickerNow} ${LABELS.pickerEmpty}.`])
  expect(seen.lookArgs.at(-1)).toEqual(['--session', 's1', '--waiting', ''])
})

test('his sentence in one line, the host’s paste tags not his; d on it, or his change’s line under it, shows it whole', async ($, on) => {
  const { propose, ring } = await world($, on, { check: 'off' })
  await $.prompt.submit(said('\n<pasted_content id="7">\nwrite me a notes tool\n\nwith add and list\n</pasted_content id="7">\n'))
  await propose()
  expect((await look($)).lines[2]?.trimEnd()).toBe(`   ${LABELS.youSaid}write me a notes tool ${LABELS.cutLead}1 ${LABELS.lines[0]}`)
  await ring('said')
  const on_ = await pane($)
  expect(on_.lines.at(-1)).toContain(LABELS.keys.whole)
  await on_.ui.press({ key: 'key-d' })
  await on_.ui.unmount()
  const { lines } = await look($)
  expect(lines.slice(2, 4).map((l: string) => l.trimEnd())).toEqual([` ${LABELS.cursor} ${LABELS.youSaid}write me a notes tool`, '             with add and list'])
  expect(lines.join('\n')).not.toMatch(/pasted_content|⏎/)
})

test('a second proposal waits behind the open one, says behind which, and is checked when it opens', async ($, on) => {
  const { seen, propose, clock } = await world($, on)
  await propose()
  const second = await propose({ ...FRAME, place: 'web', title: 'notes at web' })
  expect(second.result).toBe(`Stored as p2.\n${LABELS.waitsBehind} p1. ${LABELS.waits}\n${LABELS.asked}`)
  expect(verbs(seen).filter(v => v === 'examine')).toHaveLength(1)
  await $.prompt.submit(said('drop the first')) // his change; the session withdraws it, and the next opens
  await $.tool.call({ tool: 'mcp__frame-loop__withdraw', id: 'p1' } as any)
  await clock.settle()
  expect(seen.ran.filter(a => a[1] === 'examine').map(a => a[2])).toEqual(['p1', 'p2'])
  expect(seen.up).toBe(true)
})

test('a re-proposal for the same place and kind takes the open one’s place, says it dropped it, and is checked', async ($, on) => {
  const { seen, propose } = await world($, on)
  await propose()
  const again = await propose({ ...FRAME, title: 'notes, said again' })
  expect(again.result).toBe(`Stored as p2.\n${LABELS.replaced} p1${LABELS.replacedTail}\n${LABELS.checkingTold}\n${LABELS.opened}\n${LABELS.asked}`)
  expect(verbs(seen).filter(v => v === 'examine')).toHaveLength(2)
  expect(seen.closed).toBe(0) // the same pane, holding the new one
})
