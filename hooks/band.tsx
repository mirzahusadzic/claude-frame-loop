import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Live } from '../types'

// frame-loop's hooks write what they ask now to FRAME_LOOP_LIVE/<session>.json
// (one small file, rewritten whole); this band draws it above the prompt.
const live = atom({ plugin: 'frame-loop', key: 'live' } as const, null as Live | null)
const frame = atom({ plugin: 'frame-loop', key: 'frame' } as const, 0)
const dismissedAt = atom({ plugin: 'frame-loop', key: 'dismissedAt' } as const, 0)
// The fold: the outcome whose details are open, by its time; a new outcome starts closed.
const openedAt = atom({ plugin: 'frame-loop', key: 'openedAt' } as const, 0)
// The author's switch, mirrored from <project>/.frame-loop/switch, which the hooks read.
const off = atom({ plugin: 'frame-loop', key: 'off' } as const, false)

const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
const STALE = 180 // seconds without an update: the read was interrupted, not running

const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

// Colours by measured contrast (WCAG) in Claude Code's four themes (light, light
// colour-blind, dark, dark colour-blind), against white or black:
//   success 5.3 6.2 6.8 5.7 · error 6.7 5.9 6.1 5.8 · inactive 5.7 5.7 5.9 5.9 (text, ≥ 4.5)
//   permission 4.4 4.7 8.9 9.9 (marks only, ≥ 3)
// Never subtle (2.1-2.2), claude (2.1 in light colour-blind) or warning (2.1 there),
// and never dimColor, whose contrast the terminal decides. Words are the theme's text.
export const COLOURS = { text: ['success', 'error', 'inactive'], mark: ['success', 'error', 'inactive', 'permission'] }

// A check mark only for what was checked: an act reported, an interrupted check or an
// outcome this band does not know is never shown as fine.
const outcome = (decision: string | undefined) =>
  decision === 'pass'
    ? { mark: '✓', color: 'success', word: 'fits what you asked', wordColor: 'success' }
    : decision === 'quiet'
      ? { mark: '✓', color: 'success', word: 'checked: nothing needed a closer look', wordColor: 'success' }
      : decision === 'rise'
        ? { mark: '▲', color: 'permission', word: 'needs you', wordColor: undefined }
        : decision === 'block'
          ? { mark: '■', color: 'error', word: 'not read', wordColor: 'error' }
          : decision === 'noted'
            ? { mark: '·', color: 'inactive', word: 'noted', wordColor: undefined }
            : { mark: '·', color: 'inactive', word: 'not checked', wordColor: 'inactive' }

let switchPath = ''

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const home = (await $.env.get('HOME')) || (await $.env.get('USERPROFILE')) // Windows may set only the latter
    const id = await $.session.id()
    // Where the hooks write it: FRAME_LOOP_LIVE when the settings name a folder, as the hook reads it.
    const folder = (await $.env.get('FRAME_LOOP_LIVE')) || `${home}/.claude/frame-loop/live`
    const path = `${folder}/${id}.json`
    switchPath = `${e.cwd}/.frame-loop/switch`
    await $.command.register({
      name: 'frame-loop',
      description: 'Switch frame-loop on or off for this project: /frame-loop, /frame-loop on, /frame-loop off',
    })
    let seen = 0
    $.clock.every(250, async () => {
      try {
        const isOff = (await $.fs.read(switchPath)).trim().toLowerCase() === 'off'
        if (isOff !== (await read($, off))) await update($, off, () => isOff)
      } catch {
        // no switch file: on
      }
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
    const now = await read($, off)
    const args = e.args.trim().toLowerCase()
    const want = args === 'on' ? false : args === 'off' ? true : !now
    await $.fs.write(switchPath, want ? 'off\n' : 'on\n')
    await update($, off, () => want)
    return { text: want ? 'frame-loop is off for this project: nothing is checked or read.' : 'frame-loop is on for this project.' }
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
      // the reader's answers disagree, and Gadfly asks again until they settle.
      const over = (now.expected ? answers >= now.expected : false)
        || (!now.expected && now.expected_seconds ? inStep > now.expected_seconds : false)
      const count = over ? `${answers} answers, more than usual`
        : now.expected ? `${answers} of about ${now.expected} answers`
        : answers > 0 ? `${answers} answers in` : 'waiting for the first answer'
      const eta = over ? ' · longer than usual: asked again until the answers agree'
        : left === null ? '' : left > 5 ? ` · about ${clock(left)} left` : ' · almost done'
      const step = now.of && now.of > 1 ? `step ${now.n} of ${now.of}: ` : ''
      return (
        <Box flexDirection="column">
          <Box>
            <Text color="permission">{SPIN[f % SPIN.length]} </Text>
            <Text bold>frame-loop </Text>
            <Text>{now.what ?? 'checking'}</Text>
            <Text color="inactive">{now.why ? `, because ${now.why}` : ''} · {spent}</Text>
          </Box>
          <Box>
            <Text>{'  '}</Text>
            <Text>{step}{now.step ?? ''}</Text>
            <Text color="inactive"> · {count}{eta}</Text>
          </Box>
        </Box>
      )
    }

    if (now.at < (await read($, dismissedAt))) {
      return next(e)
    }
    const { mark, color, word, wordColor } = outcome(now.decision)
    const spent = now.started ? ` · ${clock(now.at - now.started)}` : ''
    // The hook's own line, after its mark: "needs you: <why>", in the author's words.
    // A rise shows the line that needs the author, which may follow a check mark.
    const line = (now.decision === 'rise' && now.lines?.find(x => x.includes('needs you'))) || now.lines?.[0]
    const said = line?.trim().replace(/^frame-loop /, '').replace(/^[✓▲■·] ?/, '') || word
    const isOpen = (await read($, openedAt)) === now.at
    const detail = now.detail ?? []
    return (
      <Box flexDirection="column">
        <Box>
          <Text color={color}>{mark} </Text>
          <Text bold>frame-loop </Text>
          {wordColor ? <Text color={wordColor} bold>{said}</Text> : <Text bold>{said}</Text>}
          <Text color="inactive">{spent} </Text>
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
