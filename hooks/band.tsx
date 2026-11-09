import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Item, Live, Proposal } from '../types'

// frame-loop's hooks write what they ask now to FRAME_LOOP_LIVE/<session>.json
// (one small file, rewritten whole); this band draws it above the prompt.
const live = atom({ plugin: 'frame-loop', key: 'live' } as const, null as Live | null)
const frame = atom({ plugin: 'frame-loop', key: 'frame' } as const, 0)
const dismissedAt = atom({ plugin: 'frame-loop', key: 'dismissedAt' } as const, 0)
// The fold: the outcome whose details are open, by its time; a new outcome starts closed.
const openedAt = atom({ plugin: 'frame-loop', key: 'openedAt' } as const, 0)
// The author's switch, mirrored from <project>/.frame-loop/switch, which the hooks read.
const off = atom({ plugin: 'frame-loop', key: 'off' } as const, false)
// The picker: what is being approved, until its round closes.
const proposal = atom({ plugin: 'frame-loop', key: 'proposal' } as const, null as Proposal | null)

const PICKER = 'approve'
const APPROVE = /^mcp__frame-loop__approve$/
const APPROVE_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string', description: 'What is being approved, in plain words.' },
    node: { type: 'string', description: "The node's id, for a node of the tree; left out for frame 0." },
    items: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        properties: {
          text: { type: 'string', description: 'One plain sentence, in the words to be written; never JSON or an id.' },
          detail: { type: 'string', description: 'What it narrows and what it may change, if anything.' },
        },
        required: ['text'],
      },
    },
    leftOut: { type: 'array', items: { type: 'string' }, description: 'What the proposal leaves out on purpose.' },
  },
  required: ['title', 'items'],
}

// What the next turn reads: plain sentences, as the person would say them.
const answer = ({ items }: Proposal): string => {
  const not = items.filter(x => !x.isChecked)
  if (not.length === 0) return items.length === 1 ? 'Approved.' : `Approved, all ${items.length}.`
  const yes = items.filter(x => x.isChecked)
  return [
    yes.length ? `Approved:\n${yes.map(x => `- ${x.text}`).join('\n')}` : 'Nothing approved.',
    `Not approved:\n${not.map(x => `- ${x.text}`).join('\n')}`,
    'Ask me what is wrong with each one I did not approve, before anything is written.',
  ].join('\n\n')
}

const SPIN = ['◐', '◓', '◑', '◒']
const STALE = 180 // seconds without an update: the read was interrupted, not running

const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

// The tokens the reader has spent, once it has spent any.
const spentTokens = (tokens: number | undefined) =>
  !tokens ? '' : ` · ${tokens < 1000 ? tokens : `${Math.round(tokens / 1000)}k`} tokens`

// Colours by measured contrast (WCAG) in Claude Code's four themes (light, light
// colour-blind, dark, dark colour-blind), against white or black:
//   success 5.3 6.2 6.8 5.7 · error 6.7 5.9 6.1 5.8 · inactive 5.7 5.7 5.9 5.9 (text, ≥ 4.5)
//   permission 4.4 4.7 8.9 9.9 (marks only, ≥ 3)
// Never subtle (2.1-2.2), claude (2.1 in light colour-blind) or warning (2.1 there),
// and never dimColor, whose contrast the terminal decides. Words are the theme's text.
export const COLOURS = { text: ['success', 'error', 'inactive'], mark: ['success', 'error', 'inactive', 'permission'] }

// Once a reading has ended, only what needs the author is drawn, until the next prompt:
// a ▲ or a ■. Anything else ended with the reading, as Claude Code's own lines do.
const outcome = (decision: string | undefined) =>
  decision === 'rise'
    ? { mark: '▲', color: 'permission', word: 'needs you', wordColor: undefined }
    : decision === 'block'
      ? { mark: '■', color: 'error', word: 'not read', wordColor: 'error' }
      : null

let switchPath = ''
let liveFolder = ''

// Whose switch the hooks read: what they said for this session. Only they are told the
// project, and after a reload this band knows only the current folder.
const followTheHooks = async ($: any) => {
  try {
    const project = (await $.fs.read(`${liveFolder}/${await $.session.id()}.project`)).trim()
    if (project) switchPath = `${project}/.frame-loop/switch`
  } catch {
    // no hook has run yet: the folder found at the start stands
  }
}

// The approval on the record, where Claude's word cannot stand in for it. Each round is kept,
// and the hooks read a frame's words against them all. What it could not keep is said.
const remember = async ($: any, held: Proposal): Promise<string> => {
  const path = switchPath.replace(/switch$/, 'approved.json')
  let kept: { version: number; rounds: unknown[] } = { version: 1, rounds: [] }
  try {
    const found = JSON.parse(await $.fs.read(path))
    if (Array.isArray(found?.rounds)) kept = found
  } catch {
    // no record yet
  }
  const words = (isChecked: boolean) => held.items.filter((x: Item) => x.isChecked === isChecked).map((x: Item) => x.text)
  kept.rounds.push({
    frame: held.node ?? 'frame 0',
    title: held.title,
    approved: words(true),
    not_approved: words(false),
    at: (await $.clock.now()) / 1000,
  })
  try {
    await $.fs.write(path, `${JSON.stringify(kept, null, 1)}\n`)
    return ''
  } catch {
    return '\n\nframe-loop could not keep this answer on its record, so these words read as not approved.'
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const home = (await $.env.get('HOME')) || (await $.env.get('USERPROFILE')) // Windows may set only the latter
    // Where the hooks write it: FRAME_LOOP_LIVE when the settings name a folder, as the hook reads it.
    const folder = (await $.env.get('FRAME_LOOP_LIVE')) || `${home}/.claude/frame-loop/live`
    liveFolder = folder
    // The project's switch, where the hooks read it: CLAUDE_PROJECT_DIR when it names a
    // folder that is there, else the directory the session started in.
    const project = await $.env.get('CLAUDE_PROJECT_DIR')
    const isThere = project ? await $.fs.exists(project).catch(() => false) : false
    switchPath = `${isThere ? project : e.cwd}/.frame-loop/switch`
    await $.command.register({
      name: 'frame-loop',
      description: 'Switch frame-loop on or off for this project: /frame-loop, /frame-loop on, /frame-loop off',
    })
    try {
      await $.tool.register({
        name: 'approve',
        description:
          'Ask the person to approve a decomposition item by item, in a picker with every item checked. ' +
          'End your turn after calling it: their answer arrives as their next message.',
        inputSchema: APPROVE_SCHEMA,
        isDeferred: false,
      })
    } catch {
      // no picker here: the band still runs, and Claude asks in chat
    }
    let seen = 0
    let shownFor = ''
    $.clock.every(250, async () => {
      await followTheHooks($)
      try {
        const isOff = (await $.fs.read(switchPath)).trim().toLowerCase() === 'off'
        if (isOff !== (await read($, off))) await update($, off, () => isOff)
      } catch {
        // no switch file: on
      }
      // The session's id at each tick: after /clear or a resume the hooks write the new
      // session's file, and the last session's outcome is no longer this one's.
      const id = await $.session.id()
      if (id !== shownFor) {
        shownFor = id
        seen = 0
        if ((await read($, live)) !== null) await update($, live, () => null)
      }
      const path = `${folder}/${id}.json`
      let now: Live | null = null
      try {
        now = JSON.parse(await $.fs.read(path)) as Live
      } catch {
        return // no reading yet, or a write in flight
      }
      if (now.at !== seen) {
        seen = now.at
        await update($, live, () => now)
      }
      if (now.state === 'reading') {
        await update($, frame, f => (f + 1) % 1000) // the spinner and the clock move
      }
    })

    return next(e)
  })

  on('command.run', { command: 'frame-loop' }, async ($, e) => {
    await followTheHooks($)
    const now = await read($, off)
    const args = e.args.trim().toLowerCase()
    const want = args === 'on' ? false : args === 'off' ? true : !now
    await $.fs.write(switchPath, want ? 'off\n' : 'on\n')
    await update($, off, () => want)
    return { text: want ? 'frame-loop is off for this project: nothing is checked or read.' : 'frame-loop is on for this project.' }
  })

  on('tool.call', { tool: APPROVE }, async ($, e) => {
    const given = e as unknown as { title?: string; node?: string; items?: Omit<Item, 'isChecked'>[]; leftOut?: string[] }
    const items = (given.items ?? []).map(x => ({ text: x.text, detail: x.detail, isChecked: true }))
    if (items.length === 0) return { deny: 'approve needs at least one item.' }
    const leftOut = given.leftOut ?? []
    const title = given.title ?? 'Approve'
    await update($, proposal, () => ({ title, node: given.node, items, leftOut }))
    const details = items.filter(x => x.detail).length
    const opened = await $.ui.open({
      id: PICKER,
      title,
      focus: true,
      closeOnEscape: true,
      holdToasts: true,
      rows: Math.min(30, items.length + details + leftOut.length + 7),
    })
    if (!opened.isPlaced) {
      await update($, proposal, () => null)
      return { deny: `The picker could not be shown (${opened.reason}). Ask in chat instead.` }
    }
    return { result: 'The picker is open. End your turn now: the answer arrives as the next message.' }
  })

  // Closed with Escape: nothing is approved, and Claude must not be left waiting in silence.
  on('ui.close', async ($, e, next) => {
    const held = e.id === PICKER && e.origin.kind === 'person' ? await read($, proposal) : null
    const closed = await next(e)
    if (held) {
      await update($, proposal, () => null)
      await $.prompt.fill({ text: 'I closed the picker without approving anything.' })
    }
    return closed
  })

  on('ui.render', { component: 'Pane', requestId: PICKER }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const now = await read($, proposal)
    if (now === null) return <Text color="inactive">Nothing to approve.</Text>
    const toggle = (index: number) =>
      update($, proposal, p =>
        p && { ...p, items: p.items.map((x, i) => (i === index ? { ...x, isChecked: !x.isChecked } : x)) },
      )
    const finish = async (send: (said: string) => Promise<unknown>) => {
      await followTheHooks($)
      const held = await read($, proposal)
      await update($, proposal, () => null)
      await $.ui.close({ id: PICKER })
      if (held) await send(answer(held) + (await remember($, held)))
    }
    return (
      <Box flexDirection="column">
        {now.items.map((item, index) => (
          <Box flexDirection="column">
            <Button key={`item-${index}`} plain autoFocus={index === 0 ? true : undefined} onPress={() => toggle(index)}>
              {`[${item.isChecked ? 'x' : ' '}] ${item.text}`}
            </Button>
            {item.detail ? <Text color="inactive">{`    ${item.detail}`}</Text> : null}
          </Box>
        ))}
        {now.leftOut.length > 0 ? (
          <Box flexDirection="column" marginTop={1}>
            <Text color="inactive">Left out, on purpose:</Text>
            {now.leftOut.map(line => (
              <Text color="inactive">{` - ${line}`}</Text>
            ))}
          </Box>
        ) : null}
        <Box marginTop={1} gap={2}>
          <Button key="approve" variant="primary" onPress={() => finish(text => $.prompt.submit({ text }))}>
            Approve checked
          </Button>
          <Button key="missing" onPress={() => finish(text => $.prompt.fill({ text: `${text}\n\nMissing: ` }))}>
            Add what's missing
          </Button>
        </Box>
      </Box>
    )
  })

  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if (!(await read($, off))) return next(e)
    return next({ ...e, props: { ...e.props, modes: [...e.props.modes, 'frame-loop off'] } })
  })

  on('prompt.submit', async ($, e, next) => {
    try {
      const t = (await $.clock.now()) / 1000
      await update($, dismissedAt, () => t) // what the last turn found was seen
    } catch {
      // the band never holds up a prompt
    }
    return next(e)
  }).catch(($, e, next) => next(e)) // a throw or an overrun, too: the prompt goes on

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const now = await read($, live)
    if (e.props.hasSurvey || now === null || (await read($, off))) {
      return next(e)
    }
    const t = (await $.clock.now()) / 1000
    const { Box, Button, Text } = $.ui.resolve(e)

    if (now.state === 'reading') {
      if (t - now.at > STALE) {
        return next(e)
      }
      const f = await read($, frame)
      const spent = now.started ? clock(t - now.started) : ''
      const inStep = now.step_started ? t - now.step_started : 0
      const answers = now.answers ?? 0
      // How much more: the reader's answers so far against what the same step took last time.
      const left =
        now.expected && answers > 0 ? (inStep / answers) * Math.max(now.expected - answers, 0)
          : now.expected_seconds ? now.expected_seconds - inStep : null
      // Past what the same step took last time, the band says so and never "almost done":
      // the count alone can't tell why, so it claims nothing about the answers.
      const over = (now.expected ? answers >= now.expected : false)
        || (!now.expected && now.expected_seconds ? inStep > now.expected_seconds : false)
      const said = over ? 'still asking' : now.what ?? 'checking'
      const when = over || left === null ? spent : left > 5 ? `about ${clock(left)} left` : 'almost done'
      return (
        <Box>
          <Text color="permission">{SPIN[f % SPIN.length]} </Text>
          <Text bold>frame-loop </Text>
          <Text>{said}</Text>
          <Text color="inactive"> · {when}{spentTokens(now.tokens)}</Text>
        </Box>
      )
    }

    const shown = outcome(now.decision)
    if (shown === null || now.at < (await read($, dismissedAt))) {
      return next(e)
    }
    const { mark, color, word, wordColor } = shown
    const spent = now.started ? ` · ${clock(now.at - now.started)}` : ''
    // The hook's own line, after its mark: "needs you: <why>" or an act, in the author's words.
    // A rise shows the line that needs the author, which may follow a check mark.
    const line = (now.decision === 'rise' && now.lines?.find(x => x.includes('▲'))) || now.lines?.[0]
    const said = line?.trim().replace(/^frame-loop /, '').replace(/^[✓▲■·] ?/, '') || word
    const isOpen = (await read($, openedAt)) === now.at
    const detail = now.detail ?? []
    return (
      <Box flexDirection="column">
        <Box>
          <Text color={color}>{mark} </Text>
          <Text bold>frame-loop </Text>
          {wordColor ? <Text color={wordColor} bold>{said}</Text> : <Text bold>{said}</Text>}
          <Text color="inactive">{spent}{spentTokens(now.tokens)} </Text>
          {detail.length > 0 ? (
            <Button
              key="details"
              label={isOpen ? 'hide details' : 'details'}
              onPress={() => update($, openedAt, () => (isOpen ? 0 : now.at))}
            />
          ) : null}
        </Box>
        {isOpen ? detail.map((line, i) => <Text key={`d${i}`}>{'  ' + line}</Text>) : null}
      </Box>
    )
  })
}
