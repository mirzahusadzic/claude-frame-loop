import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, RenderChildren } from 'claude-code'

import { argvOf, digestsOf, examineFailure, failure, fieldsText, isWord, lineOfRan, NOTHING, pathOf, proposedOf, restoredOf, sameDigests, shownNow, shownOf, switchedOf, whereOf, windowsNow, wordOf, writtenOf } from './band/frameloop'
import type { Ran, Word } from './band/frameloop'
import { LABELS, SCHEMA } from './band/labels'
import { commandOf, commandText, isEnded, isPlain, isQuiet, lineOf, nowText, restTail, STALE_SECONDS } from './band/line'
import { changeTold, EMPTY, held, INPUT, pickerLine, pickerTold, replacedTold, step } from './band/picker'
import type { Effect, Event } from './band/picker'
import { fit, heightOf, helpLines, MAX_WIDTH, pageTo, paneScreen, rowsOf, screen, shown, stopsOf } from './band/view'
import type { Screen, ScreenLine, Seg } from './band/view'
import type { Open, Picker, Seat } from '../types'

// The shell: host events into the picker's events, its effects carried out, the picker drawn in a pane of its own and
// the line in the band above the prompt. What it decides is in hooks/band/, plain functions; the Python side, run
// through `hooks/hand.sh`, writes and says everything else.
const TOOL = 'mcp__frame-loop__propose'
const WITHDRAW = 'mcp__frame-loop__withdraw'
const FIELDS = ['kind', 'place', 'title', 'items', 'holds', 'split', 'options', 'reason']
const EXAMINE_MS = 600_000 // the check's own limit is 540 s (hooks.EXAMINE_SECONDS); the band waits a minute more
// The picker's pane: one, by this id, opened with the keyboard asked for, closed by esc as the person's own close.
const PANE = 'picker'
// The one tone of what needs the person: the host's own for its "auto mode on" label. Nothing else is coloured, and
// every state is told by its words alone.
const ACCENT = 'autoAccept'
// A pane drawn but not given the keyboard this long after it opened is told as waiting for ctrl+x tab.
const UNHELD_MS = 1500

// Kept by the engine for the session, through a reload of this module: the one open proposal with the ids that
// wait behind it, the live file's text as last read, and the person's own last prompt, as the prompt hook saw it.
const picker = atom({ plugin: 'frame-loop', key: 'picker' } as const, EMPTY, { shape: 'picker-5' })
const live = atom({ plugin: 'frame-loop', key: 'live' } as const, '')
const asked = atom({ plugin: 'frame-loop', key: 'asked' } as const, '')
// Whether the host's prompt holds text, as his edits leave it: the picker's last line says what enter there sends.
const drafted = atom({ plugin: 'frame-loop', key: 'drafted' } as const, false)
// Where the host seated the picker's pane: the band says what opens it where it waits undrawn or without the keys.
const seat = atom({ plugin: 'frame-loop', key: 'seat' } as const, { id: '', seat: '' } as Seat, { shape: 'seat-1' })
// The band's clock in whole seconds, moved each second only while a run goes on, so the line above the prompt and the
// pane's header are drawn again to move the spinner and the seconds; at rest it stays, and nothing is drawn again.
const beat = atom({ plugin: 'frame-loop', key: 'beat' } as const, 0)
const witnessed = atom({ plugin: 'frame-loop', key: 'witness' } as const, { line: '', told: false }, { shape: 'witness-1' })
// The person's word, kept in the host's own store for each machine folder, apart from the files a session's shell
// writes: approved.json's text and the switch's as the band's own writes left them, written only at the person's
// press in the picker or their typed command. KEPT is where the band's first witness kept their digests alone.
const WORD = 'word:'
const KEPT = 'kept-digests:'

type $ = EngineInterface

// The machine folder as `where` named it, or why it could not be asked, and the one ask in flight:
// asked once, and again only while unknown. A reload of the module asks again. `project` is the project's folder
// name, the head of the picker's path; `checking` the proposals whose check this band runs now.
let folder = ''
let whyNot = ''
let project = ''
let asking: Promise<string> | null = null
const checking = new Set<string>()
// The proposal `propose` last sent back for rows that look like several claims, by session and its fields' text: the
// same one sent again by that session is kept as written.
let several = { session: '', text: '' }
// The pane as this band last opened it: the proposal it holds, '' where none is open; the rows it asked for; when it
// opened; whether it has held the keyboard since and the host has listed it. `room` is the pane's body as last drawn,
// `top` the first line of the window over the list, by the proposal's id; `order` the keys of the elements drawn, in
// their order, and `ring` the one the ring last landed on, to tell a wrap of the ring from a move up; `band` the
// band's width, the pane's before it is drawn.
let paneFor = ''
let paneRows = 0
let paneAt = 0
let heldOnce = false
let listed = false
let room = { width: 0, rows: 0 }
let top = { id: '', at: 0 }
let order: string[] = []
let ring = ''
let band = 0
let draws = 0

const run = async ($: $, verb: string, args: string[] = [], timeoutMs = 60000, stdin?: string): Promise<Ran> => {
  try {
    const env = await $.process.hookEnv()
    const init = { cwd: await $.session.root(), env, timeoutMs, ...(stdin === undefined ? {} : { stdin }) }
    return await $.process.run(argvOf($.plugin.root, verb, args), init)
  } catch (err) {
    return { exitCode: 1, stdout: '', stderr: String(err) }
  }
}
const where = async ($: $): Promise<string> => {
  asking ??= run($, 'where', [], 15000).then(async ran => {
    folder = whereOf(ran)
    whyNot = folder ? '' : failure(ran)
    project = (await $.session.root()).replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? ''
    return folder
  })
  const found = await asking
  if (!found) asking = null
  return found
}
// A proposal as the picker shows it, through `show`: what the Python side read, and the digests it read it by.
const show = async ($: $, id: string) => shownOf(await run($, 'show', [id], 15000), id)
const text = async ($: $, path: string): Promise<string | null> => $.fs.read(path).catch(() => null)
const seconds = async ($: $) => Math.floor((await $.clock.now()) / 1000)

// After each write of its own, the band keeps the word it answered. At each look (a session's start, each prompt,
// before each turn's end hook and as each turn completes) it sends the word to `look`, which puts back whatever the
// copies or the watch's record say other than it: the sentence of what was put back is its line, told to the
// session once. A band that has kept nothing for a folder takes its word from the copies only where its first
// witness kept their digests as they stand; else it keeps nothing, and the look takes out what it never wrote.
const keep = async ($: $, ran: Ran) => {
  const w = wordOf(ran)
  if (w && folder) await $.store.set(`${WORD}${folder}`, w)
}
const wordHeld = async ($: $): Promise<Word> => {
  const held = await $.store.get(`${WORD}${folder}`)
  if (isWord(held)) return held
  const read = await run($, 'look', [], 15000, '')
  const was = await $.store.get(`${KEPT}${folder}`)
  const now = digestsOf(read)
  const taken = now && was !== undefined && sameDigests(was, now) ? (wordOf(read, 'copies') ?? NOTHING) : NOTHING
  await $.store.set(`${WORD}${folder}`, taken)
  return taken
}
// Each look also names the proposals the picker holds, none of them approved, so the turn's end can tell work done
// while one waits.
const look = async ($: $): Promise<string> => {
  if (!folder) return ''
  const session = await $.session.id()
  const waiting = isPlain(session) ? ['--session', session, '--waiting', held(await read($, picker)).join(',')] : []
  return restoredOf(await run($, 'look', waiting, 15000, JSON.stringify(await wordHeld($))))
}
const looked = async ($: $) => {
  const found = await look($)
  if (found) await update($, witnessed, () => ({ line: found, told: false }))
}

// One event through the picker and its effects in order; answers what an effect has for the session to be told. With
// `later`, a check is started and not waited for: the propose call answers at once, so the session's turn can end
// while the pane draws what runs. Then the pane follows the picker: open while it holds a proposal, closed else.
const dispatch = async ($: $, event: Event, later = false): Promise<string[]> => {
  const at = draws
  let effects: Effect[] = []
  await update($, picker, s => {
    const next = step(s, event)
    effects = next.effects
    return next.state
  })
  const notes: string[] = []
  for (const fx of effects) {
    if (later && fx.kind === 'examine') void carry($, fx).catch(() => undefined)
    else notes.push(...(await carry($, fx, at)))
  }
  await paneNow($).catch(() => undefined)
  return notes
}
// The switch is not part of the proposal's digests. Read it with the proposal when the person asks to reopen, or after
// their own switch, so a proposal kept while the check was off is checked now that it is on.
const refresh = async ($: $, o: Open, later = false): Promise<boolean> => {
  const got = await show($, o.id)
  if (!got) return false
  const owed = got.check === 'on' && (got.examined === null || got.foreign)
  if (got.shown === o.shown && got.check === o.check && !(owed && !o.checking)) return false
  await dispatch($, { type: 'reshown', id: o.id, ...got, at: await seconds($) }, later)
  return true
}
// The one line that tells what the person approved, with the count, drawn until their next prompt.
const closingOf = (o: Open) => {
  const n = o.proposal.kind === 'options' ? 1 : rowsOf(o).length
  const base = shown(project) + (o.proposal.place ? `${LABELS.down}${shown(o.proposal.place)}` : '')
  return `${LABELS.name} · ${LABELS.approved} ${n} ${n === 1 ? LABELS.rows[0] : LABELS.rows[1]}${base ? ` ${LABELS.in} ${base}` : ''}`
}
// The band's own check of a proposal: `examine` run with this session's live file, so the pane's header shows what
// runs; then the files read back as they stand. A check that could not run is the picker's to say.
const examine = async ($: $, id: string): Promise<string[]> => {
  checking.add(id)
  try {
    const session = await $.session.id()
    const ran = await run($, 'examine', [id, ...(isPlain(session) ? ['--session', session] : [])], EXAMINE_MS)
    const failed = examineFailure(ran)
    const got = await show($, id)
    const held = (await read($, picker)).open
    const as = got ?? (held?.id === id ? { proposal: held.proposal, examined: held.examined, foreign: held.foreign, shown: held.shown, check: held.check } : null)
    if (as) await dispatch($, { type: 'checked', id, failed: failed ? `${LABELS.checkFailedLead} ${failed}` : '', ...as })
    return []
  } finally {
    checking.delete(id)
  }
}
const carry = async ($: $, fx: Effect, drawnAt = 0): Promise<string[]> => {
  if (fx.kind === 'examine') return examine($, fx.id)
  if (fx.kind === 'replaced') return [replacedTold(fx.id)]
  if (fx.kind === 'focus' && paneFor) void ringTo($, fx.key, drawnAt).catch(() => undefined)
  if (fx.kind === 'regain') afterDraw($, () => regain($))
  if (fx.kind === 'submit') { // the band's own submit passes no hook of its own, and takes no context: its text
    const told = pickerTold(await read($, picker)) // carries the picker as it then stands, after the person's words
    if (told.length) await dispatch($, { type: 'told' })
    await $.prompt.submit({ text: [fx.text, ...told].join('\n') })
  }
  if (fx.kind === 'approve') {
    const held = (await read($, picker)).open
    const ran = await run($, 'approve', fx.args)
    await keep($, ran)
    const done = writtenOf(fx.id, ran)
    return dispatch($, done.type === 'written' && held ? { ...done, closing: closingOf(held) } : done)
  }
  if (fx.kind === 'load') {
    const got = await show($, fx.id)
    return dispatch($, got ? { type: 'proposed', id: fx.id, ...got, at: await seconds($) } : { type: 'lost', id: fx.id })
  }
  return []
}

// The pane's ring onto the cursor's stop, where the pane holds the keys: after the hook that moved the cursor has
// answered, as a move asked from inside the host's own move of the ring, to an element its next drawing brings, does
// not land; asked again a few times while the cursor stays there. A focus effect waits for a pane drawing made after
// its event: the host keeps its place by position, so a changed list or a closed line moves it unless the ask follows
// that drawing.
const RING_TRIES = 4
const ringTo = async ($: $, key = '', after = 0) => {
  let to = ''
  for (let k = 0; k < RING_TRIES && paneFor; k++) {
    if (draws <= after || k) await $.clock.sleep(k === 0 || (k === 1 && !key) ? 0 : 60)
    if (draws <= after) continue
    const o = (await read($, picker)).open
    to ||= key || o?.cursor || ''
    if (!o || o.aside || o.changed || !to || (!key && o.cursor !== to) || (key && (!o.changing || o.changing !== o.cursor))) return
    if (!key && order.includes(INPUT)) continue // wait for the drawing in which the line is gone
    const pane = (await $.ui.panes().catch(() => [])).find(p => p.id === PANE)
    if (!pane) return
    const r = await $.ui.focus({ requestId: PANE, key: to }).catch(() => ({ deny: LABELS.cannotRun }))
    if (!r.deny) return
  }
}
// An effect that opens the pane again waits one turn, after the close that took its keys has been drawn.
const afterDraw = ($: $, effect: () => Promise<void>) => {
  const run = () => void effect().catch(() => undefined)
  try {
    $.clock.after(0, run)
  } catch {
    run()
  }
}
// The pane's rows while seated inline: all the height its content needs, as it would be drawn at the pane's width,
// or the band's before the pane was drawn.
const rowsWanted = async ($: $, o: Open) =>
  heightOf(screen(o, room.width || band || MAX_WIDTH, project, '', '', await read($, drafted), true, true)) + 1
// The pane opened, or opened again for a new proposal or for more rows: with the keyboard asked for, esc its close,
// a transparent background, as wide as the picker may be where docked, and as tall as its content where inline. Where
// the host leaves it undrawn, the band says what opens it.
const paneOpen = async ($: $, o: Open) => {
  const rows = await rowsWanted($, o)
  if (!paneFor) {
    heldOnce = false
    listed = false
    paneAt = await $.clock.now()
  }
  paneFor = o.id
  paneRows = rows
  const r = await $.ui.open({ id: PANE, title: `${LABELS.name} · ${LABELS.pick}`, focus: true, closeOnEscape: true,
    backgroundColor: 'transparent', columns: MAX_WIDTH, rows }).catch(() => null)
  const had = await read($, seat) // drawn again for more rows, a pane never given the keys is still without them
  await seated($, o.id, !r || !r.isPlaced ? 'undrawn' : had.id === o.id && had.seat === 'unheld' ? 'unheld' : 'shown')
}
const seated = async ($: $, id: string, now: Seat['seat']) => {
  const had = await read($, seat)
  if (had.id !== id || had.seat !== now) await update($, seat, () => ({ id, seat: now }))
}
// The pane follows the picker: open on the proposal it holds, unless closed by esc or while the session answers his
// change, and closed where none is open; and, from the band's clock, `grow`, opened again where its content wants more
// rows than it asked for, never from inside a move of the host's that the open would wait on.
const paneNow = async ($: $, grow = false) => {
  const o = (await read($, picker)).open
  const want = o && !o.aside && !o.changed ? o : null
  if (!want) {
    if (!paneFor) return
    paneFor = ''
    paneRows = 0
    await seated($, '', '')
    await $.ui.close({ id: PANE }).catch(() => undefined)
    return
  }
  if (paneFor !== want.id || (grow && (await rowsWanted($, want)) > paneRows)) await paneOpen($, want)
}
// Esc in the line: the host gives the keys back to the prompt as it closes the pane, which the band keeps open;
// opened again, the pane takes them back, its ring on the stop the line was under.
const regain = async ($: $) => {
  await $.ui.panes().catch(() => [])
  const o = (await read($, picker)).open
  if (o && !o.aside && !o.changed) await paneOpen($, o)
}
// His change, as he typed it in the line under a row or under his sentence: the picker closes while the session
// answers, and the session is told it as his change with the picker as it stands. Enter on nothing, or spaces alone,
// confirms a row under review or closes the line, and sends nothing. A line that never entered, as one another hook
// dropped, opens the picker again at once.
const sendChange = async ($: $, typed: string) => {
  const o = (await read($, picker)).open
  if (!o || !o.changing || o.aside || o.changed) return
  if (!typed.trim()) return void (await dispatch($, { type: 'submit', text: typed }))
  const told = changeTold(o)
  await dispatch($, { type: 'submit', text: typed })
  const now = pickerTold(await read($, picker))
  if (now.length) await dispatch($, { type: 'told' })
  const done = await $.prompt.submit({ text: [typed, ...told, ...now].join('\n') }).catch(() => ({ drop: LABELS.cannotRun }))
  if ('drop' in done) await dispatch($, { type: 'reopen' })
}
// Page down and page up: the cursor a page of the list away, and the window with it, so it stays where it was.
const paged = async ($: $, by: 1 | -1) => {
  const s = await read($, picker)
  const o = s.open
  if (!o || !room.rows) return
  const sc = paneScreen(o, room.width, room.rows, project, '', unapprovedOf(s, await read($, live)), await read($, drafted), true)
  const to = pageTo(sc, room.rows, by)
  if (!to.stop || to.stop === o.cursor) return
  top = { id: o.id, at: Math.max(0, (top.id === o.id ? top.at : 0) + to.lines) }
  await dispatch($, { type: 'go', stop: to.stop })
}
// Files changed while one of this picker's proposals waited, with nothing of it approved: the hooks' sentence for it.
const unapprovedOf = (s: Picker, text: string) => {
  const l = lineOf(text)
  const waited = held(s)
  return l.unapproved && l.unapproved.proposals.some(id => waited.includes(id)) ? l.unapproved.said : ''
}

// Each second: the live file of this session, drawn only as `line` finds the hooks wrote it, the watch recording that
// write as the file stands, and the band's clock while a run goes on; where the host seated the pane, and the pane
// following the picker; and the open proposal and its examination as they stand: where either is not what the picker
// showed, it is shown again, as it now stands. A check this band no longer runs, with nothing running and no word for
// longer than a run may stay silent, is told as ended.
let lastLive = ''
const tick = async ($: $) => {
  if (!folder) return
  const id = await $.session.id()
  const held = isPlain(id, windowsNow()) ? await $.fs.read(pathOf(folder, 'live', `${id}.json`)).catch(() => '') : ''
  if (held !== lastLive) {
    lastLive = held
    const drawn = held ? lineOfRan(await run($, 'line', [id], 15000)) : ''
    if (drawn !== (await read($, live))) await update($, live, () => drawn)
  }
  const l = lineOf(await read($, live))
  const open = (await read($, picker)).open
  if (l.now || open?.checking) {
    const now = await seconds($)
    if (now !== (await read($, beat))) await update($, beat, () => now)
    if (open?.checking && !checking.has(open.id) && !l.now && now - open.began > STALE_SECONDS) {
      return void (await dispatch($, { type: 'checked', id: open.id, failed: LABELS.checkSilent, proposal: open.proposal,
        examined: open.examined, foreign: open.foreign, shown: open.shown, check: open.check }))
    }
  }
  await seatNow($)
  await paneNow($, true)
  if (!open || open.writing) return
  const kept = await text($, pathOf(folder, 'proposals', `${open.id}.json`))
  if (kept === null || (await shownNow(kept, await text($, pathOf(folder, 'proposals', `${open.id}.examined.json`)))) === open.shown) return
  const got = await show($, open.id)
  if (got && got.shown !== open.shown) await dispatch($, { type: 'reshown', id: open.id, ...got, at: await seconds($) })
}
// Where the host seated the pane, as its list says: undrawn, drawn without the keyboard since it opened, or shown. A
// pane the host listed and no longer lists, gone with no close the band heard, leaves the proposal waiting as esc does.
const seatNow = async ($: $) => {
  const o = (await read($, picker)).open
  if (!o || o.aside || o.changed || paneFor !== o.id) return
  const p = (await $.ui.panes().catch(() => [])).find(x => x.id === PANE)
  if (!p) {
    if (!listed) return
    paneFor = ''
    return void (await dispatch($, { type: 'aside' }))
  }
  listed = true
  if (p.isFocused) heldOnce = true
  const waited = (await $.clock.now()) - paneAt >= UNHELD_MS
  await seated($, o.id, !p.isPlaced ? 'undrawn' : heldOnce || !waited ? 'shown' : 'unheld')
}

// Whether the host's prompt holds text, kept as his edits and the host's own changes leave it.
const typing = async ($: $, text: string) => {
  if ((text.trim() !== '') !== (await read($, drafted))) await update($, drafted, () => text.trim() !== '')
}
// The pieces of one line of the pane, each its Text; a stop's lines padded to the picker's width, so the host's focus
// look covers its block whole, and a blank line as a space, so it takes its row.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Els = { Box: any; Button: any; Input: any; Text: any }
const pieces = ({ Text }: Els, line: ScreenLine, k: number, pad = 0) => {
  const used = line.segs.reduce((n, x) => n + x.text.length, 0)
  const fill: Seg[] = pad > used ? [{ text: ' '.repeat(pad - used) }] : used === 0 ? [{ text: ' ' }] : []
  return [...line.segs, ...fill].map((x, j) => (
    <Text key={`s${k}-${j}`} color={x.tone === 'accent' || x.cursor ? ACCENT : undefined} dimColor={x.tone === 'dim' ? true : undefined}
      bold={x.tone === 'bold' ? true : undefined}>{x.text}</Text>
  ))
}

// The line under the stop he pressed enter on: one Input, held by the keyboard as it opens, whose dim words say what
// enter does; as many rows tall as his words take at the table's width, with the column rule beside each row there.
const inputLine = (els: Els, o: Open, sc: Screen, rows: number, $: $) => {
  const { Box, Input, Text } = els
  const inTable = o.changing !== 'said'
  return (
    <Box key="input-line" flexDirection="row">
      <Box flexDirection="row" flexShrink={0} width={inTable ? sc.width - 8 : sc.width}>
        <Text>{'     '}</Text>
        <Box flexGrow={1} flexShrink={1}>
          <Input key={INPUT} placeholder={LABELS.inputHint} submitLabel="" autoFocus rows={Math.max(1, rows)} value={o.typed.trim() ? o.typed : ''}
            onInput={(v: string) => void dispatch($, { type: 'typed', text: String(v ?? '') })} onSubmit={(v: string) => void sendChange($, v)} />
        </Box>
      </Box>
      {inTable ? <Text>{Array.from({ length: rows }, () => '│').join('\n')}</Text> : null}
    </Box>
  )
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    paneFor = '' // a session's own pane is opened by its own picker
    paneRows = 0
    top = { id: '', at: 0 }
    order = []
    ring = ''
    draws = 0
    await $.tool.register({ name: 'propose', description: LABELS.tool, inputSchema: SCHEMA, isDeferred: false }).catch(() => undefined)
    const withdrawSchema = { type: 'object', properties: { id: { type: 'string', description: LABELS.withdrawId } }, required: ['id'] } as const
    await $.tool.register({ name: 'withdraw', description: LABELS.withdrawTool, inputSchema: withdrawSchema, isDeferred: false }).catch(() => undefined)
    await $.command.register({ name: 'frame-loop', description: LABELS.command, argumentHint: '[on|off]' })
    void where($)
    $.clock.every(1000, () => tick($))
    return next(e)
  })

  // The tool call keeps the proposal and opens the picker with it in its pane; with the check on, the check runs after
  // the call answers, and the pane shows the rows once it is done.
  on('tool.call', { tool: TOOL }, async ($, e) => {
    if (!(await where($))) return { deny: `${LABELS.cannotRun} ${whyNot}` }
    const given = e as unknown as Record<string, unknown>
    const fields = Object.fromEntries(FIELDS.filter(k => k in given).map(k => [k, given[k]]))
    const session = await $.session.id()
    const draft = pathOf((await $.process.hookEnv()).CLAUDE_PLUGIN_DATA ?? '', 'drafts', `${isPlain(session, windowsNow()) ? session : 'session'}.json`)
    await $.fs.write(draft, `${JSON.stringify(fields, null, 2)}\n`)
    const sent = fieldsText(fields)
    const again = several.session === session && several.text === sent
    const got = proposedOf(await run($, 'propose', again ? [draft, '--again'] : [draft]))
    several = got.kind === 'faults' && got.several ? { session, text: sent } : { session: '', text: '' }
    if (got.kind !== 'stored') return { deny: got.kind === 'faults' ? got.text : `${LABELS.cannotRun} ${got.text}` }
    const shownNowIs = await show($, got.id)
    if (!shownNowIs) return { deny: `${LABELS.cannotRun} ${pathOf(folder, 'proposals', `${got.id}.json`)}` }
    const notes = await dispatch($, { type: 'proposed', id: got.id, ...shownNowIs, said: await read($, asked), at: await seconds($) }, true)
    const now = await read($, picker)
    const told = (text: string) => ({ result: [got.said, ...notes, text, LABELS.asked].filter(Boolean).join('\n') })
    if (now.open?.id === got.id) return told(now.open.checking ? `${LABELS.checkingTold}\n${LABELS.opened}` : LABELS.opened)
    const at = now.waiting.findIndex(w => w.id === got.id)
    if (now.open && at >= 0) {
      const ahead = [now.open.id, ...now.waiting.slice(0, at).map(w => w.id)].join(', ')
      return told(`${LABELS.waitsBehind} ${ahead}. ${LABELS.waits}`)
    }
    return { deny: [got.said, ...notes, LABELS.unplaced].filter(Boolean).join('\n') }
  }).catch(() => ({ deny: LABELS.cannotRun }))

  // The pane's ring walks the list as the host moves it, each stop an element of the host's. A move onto the header is
  // the person's up, onto the last line their down, and the ring stays where it is while the cursor moves; the ring
  // landing on a stop moves the cursor there, and off his change's line closes it, nothing sent.
  on('ui.focus', async ($, e, next) => {
    if (e.component !== 'Pane' || e.requestId !== PANE) return next(e)
    if (e.origin.kind === 'person') heldOnce = true // the person moves a ring only in a pane that holds the keys
    const o = (await read($, picker)).open
    if (!o || o.aside || o.changed || o.checking) return next(e)
    const stops = stopsOf(o)
    const leaving = !!o.changing && e.origin.kind === 'person' && e.element !== undefined && e.element !== INPUT // the person moved the ring off the line
    if (leaving) {
      if (e.element && stops.includes(e.element)) {
        await dispatch($, { type: 'focus', stop: e.element })
        void ringTo($).catch(() => undefined) // the line is gone from the next drawing before the ring asks again
      }
      else if (e.element !== 'head' && !e.element?.startsWith('key-')) await dispatch($, { type: 'back' })
    }
    if (e.origin.kind === 'person') {
      if (e.element === undefined) return {} // the ring stays on the list: round again, never out
      const wrapped = ring !== '' && ring === order.at(-1) // forward past the last element, round to the first
      if (e.element === 'head') return (await dispatch($, { type: 'move', by: wrapped ? 1 : -1 }), {})
      if (e.element.startsWith('key-')) return (await dispatch($, { type: 'move', by: 1 }), {}) // the ring follows once this answered
    }
    if (!leaving && !o.changing && e.element && stops.includes(e.element)) await dispatch($, { type: 'focus', stop: e.element })
    const done = await next(e)
    if (!done.deny) heldOnce = true
    if (!done.deny && e.element) ring = e.element
    return done
  }).catch(($, e, next) => next(e))

  // The arrows, where the host would scroll rather than move the ring, a wheel's tick, and the page keys, which move
  // only the host's window: each moves the cursor, the ring with it, and the pane's own window follows it.
  on('ui.scroll', async ($, e, next) => {
    if (e.component !== 'Pane' || e.requestId !== PANE || e.origin.kind !== 'person') return next(e)
    const o = (await read($, picker)).open
    if (!o || o.aside || o.changed || o.checking || !e.by) return next(e)
    const by = e.by > 0 ? 1 : -1
    if (e.pointer || Math.abs(e.by) === 1) await dispatch($, { type: 'move', by })
    else await paged($, by)
    return {}
  }).catch(($, e, next) => next(e))

  // The person's close, by esc, the close mark or its key: the proposal waits with its answers until /frame-loop. Esc
  // in the line closes only that line: the pane is kept open, and takes the keys back on the stop.
  on('ui.close', async ($, e, next) => {
    if (e.id !== PANE || e.origin.kind !== 'person') return next(e)
    const o = (await read($, picker)).open
    if (!o || o.aside || o.changed) return next(e)
    if (!o.changing && !o.help && !o.details) {
      paneFor = ''
      await seated($, '', '')
    }
    await dispatch($, { type: 'closed' })
    return (await read($, picker)).open?.aside ? next(e) : { value: undefined }
  }).catch(($, e, next) => next(e))

  // A key the person types into the prompt box: whether the box holds text, for the picker's last line to say what
  // enter there sends.
  on('prompt.edit', async ($, e, next) => {
    await typing($, `${e.text.slice(0, e.start)}${e.inputText}${e.text.slice(e.end)}`)
    return next(e)
  }).catch(($, e, next) => next(e))
  on('prompt.change', async ($, e, next) => {
    await typing($, e.text)
    return next(e)
  }).catch(($, e, next) => next(e))

  // The session's withdrawal of the open proposal: only while a change of the person's to it stands unanswered, which
  // only his own line sets, so the session cannot close a picker of its own accord.
  on('tool.call', { tool: WITHDRAW }, async ($, e) => {
    const id = String((e as unknown as { id?: unknown }).id ?? '')
    const o = (await read($, picker)).open
    if (!o || !o.changed || (id && id !== o.id)) return { deny: `${LABELS.withdrawRefused} ${o?.id ?? id}.` }
    await dispatch($, { type: 'withdrawn' })
    return { result: [`${LABELS.proposal} ${o.id} ${LABELS.withdrawn}`, `${LABELS.pickerNow} ${pickerLine(await read($, picker))}.`].join('\n') }
  }).catch(() => ({ deny: LABELS.cannotRun }))

  // /frame-loop: the whole state; asked by the person, it brings back the picker closed by esc, and draws a pane that
  // waits undrawn, at any width, with the keyboard.
  on('command.run', { command: 'frame-loop' }, async ($, e) => {
    const c = commandOf(e.args ?? '', e.origin?.kind === 'composer' || e.origin?.kind === 'bridge')
    if (c.kind === 'say') return { text: c.text }
    if (!(await where($))) return { text: `${LABELS.cannotRun} ${whyNot}` }
    if (c.kind === 'switch') {
      const ran = await run($, 'switch', [c.to], 15000)
      await keep($, ran)
      const o = (await read($, picker)).open
      if (ran.exitCode === 0 && o) await refresh($, o, true)
      return { text: switchedOf(ran) }
    }
    await tick($)
    const o = (await read($, picker)).open
    if (o && !o.changed && !o.writing) await refresh($, o, true)
    const nowOpen = (await read($, picker)).open
    if (nowOpen?.aside) await dispatch($, { type: 'resume' })
    else if (nowOpen && !nowOpen.changed) await paneOpen($, nowOpen)
    const now = await read($, picker)
    return { text: [commandText(lineOf(await read($, live)), await seconds($)), ...(now.ever ? [pickerLine(now)] : [])].join('\n') }
  })

  // As a session starts and before each turn's end hook: the band looks first, so the hooks read the person's word.
  on('classic.SessionStart', async ($, e, next) => {
    if (await where($)) await looked($)
    return next(e)
  }).catch(($, e, next) => next(e))
  on('classic.Stop', async ($, e, next) => {
    if (folder) await looked($)
    return next(e)
  }).catch(($, e, next) => next(e))

  // At each prompt, before its hook: a line the person sends while the picker is open is his change to the whole
  // proposal, told so to the session beside his line, and the picker is closed while the session answers it; else his
  // own words kept word for word, for the picker's "You said". Then what the look finds, or what it found since, told
  // to the session once.
  on('prompt.submit', async ($, e, next) => {
    if (e.command || !(await where($))) return next(e)
    let change: string[] = []
    if (e.origin?.kind === 'composer') {
      await typing($, '')
      const s = await read($, picker)
      if (s.open && !s.open.aside && !s.open.changed && !s.open.writing) {
        change = changeTold(s.open, true)
        await dispatch($, { type: 'changed', text: e.text })
      } else {
        await update($, asked, () => e.text)
        if (s.closing) await dispatch($, { type: 'prompted' })
      }
    }
    const found = await look($)
    const held = await read($, witnessed)
    const say = found || (held.line && !held.told ? held.line : '')
    await update($, witnessed, () => (say ? { line: say, told: true } : { line: held.told ? '' : held.line, told: false }))
    // the picker as the person sees it, and each proposal closed with nothing written since the last prompt
    const told = pickerTold(await read($, picker))
    if (told.length) await dispatch($, { type: 'told' })
    const context = [...change, ...(say ? [say] : []), ...told]
    const done = await next(context.length ? { ...e, context: [...(e.context ?? []), ...context] } : e)
    if (change.length && 'drop' in done) await dispatch($, { type: 'reopen' }) // his line never entered: no answer comes
    return done
  }).catch(($, e, next) => next(e))

  // A main turn ended: the picker his change closed opens again, on the same proposal where the session made no new
  // one, with his answers; and the line that told what he approved gives way to the band at rest.
  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined) await dispatch($, { type: 'turned' })
    if (e.agentId === undefined && folder) await looked($)
    return done
  }).catch(($, e, next) => next(e))

  // The propose call is one quiet line in the transcript, and its result none: the picker is the one place. Where it
  // says it is, before the title, so a cut at the end takes only the session's words.
  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    if (e.props.tool !== TOOL || e.props.isExpanded) return next(e)
    const { Text } = $.ui.resolve(e)
    const title = shown(String((e.props.input as { title?: unknown } | undefined)?.title ?? ''))
    return <Text dimColor wrap="truncate-end">{`${LABELS.name} · ${LABELS.inPicker} · ${LABELS.proposed} ${title}`}</Text>
  })
  on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
    if (e.props.tool !== TOOL || e.props.isExpanded) return next(e)
    const { Box } = $.ui.resolve(e)
    return <Box />
  })

  // The picker in its pane, one list the host's ring walks: the header, the path, his sentence in one line, the table
  // with every row and its one question, OK, a blank line and the keys line; each stop one element of the host's, the
  // cursor's drawn first to take the ring; his change's one line under the stop he chose. Where the whole is taller
  // than the pane's body, the header and the last line stay and the rest is windowed around the cursor, with what is
  // out of view counted. With the keyboard the last line's hotkeys are the host's Buttons; without it, what a line
  // typed at the prompt is and how to give the pane the keys.
  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    draws++
    const s = await read($, picker)
    const l = await read($, live)
    const at = await read($, beat)
    const typed = await read($, drafted)
    const els = $.ui.resolve(e)
    const { Box, Button, Input, Text } = els
    const o = s.open
    if (!o || o.aside || o.changed) return <Box />
    const rows = Math.max(4, e.props.scroll.bodyRows)
    room = { width: e.props.bodyColumns, rows }
    const now = lineOf(l).now
    const sc = paneScreen(o, e.props.bodyColumns, rows, project, o.checking && now ? nowText(now, at) : '', unapprovedOf(s, l), typed, e.props.isFocused)
    const win = fit(sc, rows, top.id === o.id ? top.at : 0)
    top = { id: o.id, at: win.top }
    const send = (event: Event) => () => void dispatch($, event)
    const drawn: RenderChildren[] = []
    const keys: string[] = []
    for (let k = 0; k < win.lines.length;) {
      const line = win.lines[k]!
      if (line.kind === 'input') { // the one line under the stop, the Input wrapping with his words
        const block: ScreenLine[] = []
        while (k < win.lines.length && win.lines[k]!.kind === 'input') block.push(win.lines[k++]!)
        keys.push(INPUT)
        drawn.push(inputLine(els, o, sc, block.length, $))
        continue
      }
      const stop = line.stop
      if (stop && sc.stops.includes(stop)) { // a stop's lines, its row, its question and its details, as one element
        const block: ScreenLine[] = []
        while (k < win.lines.length && win.lines[k]!.stop === stop && win.lines[k]!.kind !== 'input') block.push(win.lines[k++]!)
        keys.push(stop)
        drawn.push(
          <Button key={stop} plain autoFocus={!o.changing && stop === sc.cursor ? true : undefined} onPress={send({ type: 'press', stop })}>
            {block.flatMap((b, i) => [...(i ? [<Text key={`n${i}`}>{'\n'}</Text>] : []), ...pieces(els, b, k * 100 + i, sc.width)])}
          </Button>,
        )
        continue
      }
      if (line.kind === 'head' && sc.stops.length) { // a move of the ring onto it is the person's up
        keys.push('head')
        drawn.push(<Button key="head" plain onPress={send({ type: 'move', by: -1 })}>{pieces(els, line, k)}</Button>)
      } else if (line.kind === 'unapproved') {
        drawn.push(<Text key={`l${k}`} color="warning">{line.segs.map(x => x.text).join('')}</Text>)
      } else {
        drawn.push(<Text key={`l${k}`}>{pieces(els, line, k)}</Text>)
      }
      k++
    }
    const keyOf = (hotkey: string): Event =>
      hotkey === 'y' ? { type: 'yes' } : hotkey === 'o' ? { type: 'approve' } : hotkey === 'd' ? { type: 'details' } : hotkey === 'r' ? { type: 'retry', at } : { type: 'help' }
    // the last line in pieces, each going whole to the next row where this one has no room for it, as `footPieces`
    // counts them: the lead, then each key, bold, and its meaning, a hotkey the host's Button
    const f = sc.foot
    const lead = f.lead ? `${f.lead}${f.keys.length ? ' ' : ''}` : ''
    const last = sc.help.length
      ? [
          ...helpLines(sc).map((line, i) => <Text key={`h${i}`} dimColor>{line}</Text>),
          <Box key="help-close" flexWrap="wrap" paddingLeft={1}>
            <Button key="key-h" plain dimColor hotkey="h" onPress={send({ type: 'help' })}>{LABELS.keys.listClose}</Button>
            <Text key="help-esc" dimColor>{` · ${LABELS.keys.esc} ${LABELS.keys.listClose}`}</Text>
          </Box>,
        ]
      : [
          <Box key="keys" flexWrap="wrap" paddingLeft={1}>
            {lead ? <Text key="lead" dimColor>{lead}</Text> : null}
            {f.keys.map((k, i) => {
              if (k.hotkey && sc.focused) keys.push(`key-${k.hotkey}`)
              const dot = i < f.keys.length - 1 ? ' · ' : ''
              return (
                <Box key={`p${i}`} flexShrink={0}>
                  {k.hotkey && sc.focused ? (
                    <Button key={`key-${k.hotkey}`} plain dimColor hotkey={k.hotkey} onPress={send(keyOf(k.hotkey))}>{k.means}</Button>
                  ) : (
                    <Text key="k" dimColor>
                      <Text bold>{k.key}</Text>
                      {` ${k.means}`}
                    </Text>
                  )}
                  {dot ? <Text key="d" dimColor>{dot}</Text> : null}
                </Box>
              )
            })}
          </Box>,
        ]
    order = keys
    if (sc.help.length) order = ['key-h']
    return (
      <Box flexDirection="column">
        {drawn}
        {last}
      </Box>
    )
  })

  // The band above the prompt: only what bears value. For an open picker, nothing but an alert, and one line where its
  // pane is not in front of him: closed by esc and how to reopen it, waiting undrawn or without the keyboard and what
  // opens it, or closed while the session answers his change. With no picker open: what runs, while a run goes on;
  // else the line that tells what was approved, until the turn it starts ends; else what the band's look put back, or
  // an alert the hooks wrote; else the band at rest, one short line of the tree's tension, what needs the person's eye
  // and what the checks spent. The event's own sentence is never drawn. A line in the warning tone tells a failure or
  // an alert, and wraps whole; every other line puts its state and counts first, so a cut at its end takes no count.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    band = e.props.bodyColumns
    const s = await read($, picker)
    const text_ = await read($, live)
    const l = lineOf(text_)
    const w = (await read($, witnessed)).line
    const at = await read($, beat)
    const where_ = await read($, seat)
    if (e.props.hasSurvey) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    const o = s.open
    const unapproved = unapprovedOf(s, text_)
    // work done while a proposal waited is the picker's to show: once none of its proposals waits, it is gone
    const alert = l.unapproved && l.alert === l.unapproved.said && !unapproved ? '' : l.alert
    if (o) {
      const placed = where_.id === o.id ? where_.seat : ''
      const opens = o.aside ? LABELS.reopens : placed === 'undrawn' ? LABELS.opens : placed === 'unheld' ? LABELS.answers : ''
      const line = o.changed ? `${LABELS.name} · ${LABELS.changeSent} · ${LABELS.opensAgain}` : opens ? `${LABELS.name} · ${LABELS.waiting} · ${opens}` : ''
      const warned = unapproved || (w ? shown(w) : '') || alert
      if (!line && !warned) return next(e)
      return (
        <Box flexDirection="column">
          {warned ? <Text key="alert" color="warning" wrap="wrap">{warned}</Text> : null}
          {line ? <Text key="waits" wrap="truncate-end">{line}</Text> : null}
        </Box>
      )
    }
    if (isQuiet(l) && !w && !s.closing) return next(e)
    if (l.now) {
      const ended = isEnded(l.now, at)
      return (
        <Box>
          <Text color={ended ? 'warning' : undefined} wrap={ended ? 'wrap' : 'truncate-end'}>{nowText(l.now, at)}</Text>
        </Box>
      )
    }
    if (s.closing) {
      return (
        <Box>
          <Text wrap="truncate-end">{s.closing}</Text>
        </Box>
      )
    }
    if (w || alert) {
      return (
        <Box>
          <Text color="warning" wrap="wrap">{w ? shown(w) : alert}</Text>
        </Box>
      )
    }
    return (
      <Box>
        <Box flexShrink={0}>
          <Text bold>{LABELS.name}</Text>
        </Box>
        <Text wrap="truncate-end">{restTail(l)}</Text>
      </Box>
    )
  })
}
