import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Contract, Header, Item, Live, Part, PartLine, Proposal } from '../types'

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

// Where the work is in the tree, mirrored from <live folder>/<session>.part.json; none without one.
const part = atom({ plugin: 'frame-loop', key: 'part' } as const, null as PartLine | null)

// The reading that last started a turn, by its time: one wake a reading, across a reload.
const woken = atom({ plugin: 'frame-loop', key: 'woken' } as const, 0)
// What the band starts that turn with; the hooks know a wake by these words (WAKE, turn.py).
const WAKE = 'frame-loop: a reading of the work landed. Deal with what it found.'
const CHECK = 'Run `: frame-loop-check` as a command of its own, and tell me what it says.'
const WAKE_WITHIN = 3600 // seconds: a session resumed later is told at its next prompt instead

const PICKER = 'approve'
const APPROVE = /^mcp__frame-loop__approve$/
const ITEM_SCHEMA = {
  type: 'object',
  properties: {
    text: { type: 'string', description: 'One plain sentence, in the words to be written; never JSON or an id.' },
    detail: { type: 'string', description: 'What it narrows and what it may change, if anything.' },
  },
  required: ['text'],
}
const PART_ITEM_SCHEMA = {
  ...ITEM_SCHEMA,
  properties: {
    ...ITEM_SCHEMA.properties,
    quotes: { type: 'string', description: "The id of the parent's requirement this line narrows; never shown." },
  },
}
const APPROVE_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string', description: 'What is being approved, in plain words.' },
    node: { type: 'string', description: "The node's id, for a node of the tree; left out for frame 0." },
    items: { type: 'array', minItems: 1, items: ITEM_SCHEMA },
    parent: {
      type: 'string',
      description: "For a split: the id of the node being split; left out when frame 0's requirements are split.",
    },
    parts: {
      type: 'array',
      minItems: 1,
      description:
        'A split, whole: every part at once, one page each, approved together; in place of items and node. ' +
        'Nothing of the split is written before its answer.',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: "The part's file name in the tree, lowercase words joined by '-'." },
          name: { type: 'string', description: "The part's name in plain words, as the person reads it." },
          items: { type: 'array', minItems: 1, items: PART_ITEM_SCHEMA },
          scope: {
            type: 'array',
            minItems: 1,
            items: { type: 'string' },
            description: 'The paths the part may change, as its file holds them: shown on its page, and approved.',
          },
        },
        required: ['id', 'name', 'items', 'scope'],
      },
    },
    contracts: {
      type: 'array',
      description:
        "For a split only: what two or more of its parts must each keep, each written once with the parts' ids it binds; " +
        'shown on every page it binds and approved with the split.',
      items: {
        type: 'object',
        properties: {
          text: { type: 'string', description: 'One plain sentence every part it binds must keep.' },
          parts: { type: 'array', minItems: 2, items: { type: 'string' }, description: 'The ids of the parts it binds.' },
        },
        required: ['text', 'parts'],
      },
    },
    leftOut: { type: 'array', items: { type: 'string' }, description: 'What the proposal leaves out on purpose.' },
    removes: {
      type: 'array',
      items: { type: 'string' },
      description: 'Words approved before that this takes out or rewords: each is an item of its own, to approve.',
    },
  },
  required: ['title'],
}

const itemWords = (x: Item) => (x.isRemoval ? `Remove: ${x.text}` : x.text)

const NUMBERS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
const count = (n: number) => NUMBERS[n] ?? String(n)
const lines = (n: number) => `${n} ${n === 1 ? 'line' : 'lines'}`
const PART_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

// The path and the page, the requirement being split, a blank, the part's name and its files;
// then a blank, the principles' heading and the guide's rules, besides the principles themselves.
const HEADER_ROWS = 8

// What keeps a split from being put to the person: told to Claude, which then mends it.
const splitFaults = (given: {
  node?: string
  items?: unknown[]
  removes?: unknown[]
  parent?: string
  parts?: any[]
  contracts?: any[]
}) => {
  const parts = given.parts ?? []
  if (given.node !== undefined || given.items !== undefined || given.removes !== undefined)
    return 'a split holds its parts alone: no node, items or removes beside them.'
  if (parts.length === 0) return 'a split needs at least one part.'
  if (given.parent !== undefined && !PART_ID.test(given.parent)) return `the split's parent ${JSON.stringify(given.parent)} is no node's id.`
  const ids = parts.map(p => p?.id)
  for (const p of parts) {
    if (typeof p?.id !== 'string' || !PART_ID.test(p.id) || p.id === 'root')
      return `each part needs an id of lowercase words joined by '-' (not ${JSON.stringify(p?.id)}).`
    if (typeof p.name !== 'string' || !p.name.trim()) return `part ${p.id} needs a name in plain words.`
    if (!Array.isArray(p.scope) || p.scope.length === 0 || p.scope.some((x: unknown) => typeof x !== 'string' || !x.trim()))
      return `part ${p.id} needs the paths it may change, as its scope.`
    if (!Array.isArray(p.items) || p.items.length === 0 || p.items.some((x: any) => typeof x?.text !== 'string' || !x.text.trim()))
      return `part ${p.id} needs at least one line, each a sentence.`
  }
  if (new Set(ids).size !== ids.length) return 'two parts share an id.'
  return contractFaults(given.contracts, ids)
}

// What keeps a split's contracts from being put to the person: each is one statement, written
// once, binding two or more of the split's own parts.
const contractFaults = (contracts: unknown, ids: string[]): string => {
  if (contracts === undefined) return ''
  if (!Array.isArray(contracts)) return 'contracts are a list, each a statement and the parts it binds.'
  const seen = new Set<string>()
  for (const c of contracts as any[]) {
    if (typeof c?.text !== 'string' || !c.text.trim()) return 'each contract needs a statement, one plain sentence.'
    const bound = Array.isArray(c.parts) ? c.parts : []
    const stranger = bound.find((p: unknown) => typeof p !== 'string' || !ids.includes(p))
    if (stranger !== undefined) return `the contract "${c.text}" names ${JSON.stringify(stranger)}, not a part of this split.`
    if (new Set(bound).size < 2) return `the contract "${c.text}" must bind two or more of the split's parts.`
    if (seen.has(words(c.text))) return `the contract "${c.text}" is written once, not twice.`
    seen.add(words(c.text))
  }
  return ''
}

// The contracts that bind a part, in the split's order.
const bindingOf = (contracts: Contract[] | undefined, id: string) => (contracts ?? []).filter(c => c.parts.includes(id))
// The other parts a contract binds, by their names.
const sharers = (c: Contract, parts: Part[], id?: string) =>
  c.parts.filter(p => p !== id).map(p => parts.find(x => x.id === p)?.name ?? p)
const andList = (names: string[]) =>
  names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`

const words = (text: string) => text.split(/\s+/).filter(Boolean).join(' ')

// The words approved for a frame, round by round, a later round overruling an earlier one, as
// the hooks read them (framezero.approved_words); null when the frame has had no answer.
const approvedWords = (record: any, frame: string): Set<string> | null => {
  const rounds = Array.isArray(record?.rounds) ? record.rounds.filter((r: any) => r?.frame === frame) : []
  if (rounds.length === 0) return null
  const kept = new Set<string>()
  for (const r of rounds) {
    for (const x of Array.isArray(r.approved) ? r.approved : []) kept.add(words(String(x)))
    for (const x of Array.isArray(r.not_approved) ? r.not_approved : []) kept.delete(words(String(x)))
  }
  return kept
}

// Where a split sits, from the files the hooks read: frame 0, the tree's nodes up from the one
// split, the approvals, and the guide's rules index. What cannot be read is said, never filled in.
const ROOT_NAMES = ['root', 'frame 0', 'frame0', 'frame-0']
// What a split's reading was a reading of, rebuilt from the split about to be shown, as the hooks
// build it (splitcheck.shape_of): a split revised after its reading is another split.
const shapeOf = (given: any): string[] => {
  const out: string[] = []
  for (const part of Array.isArray(given?.parts) ? given.parts : []) {
    const id = String(part?.id)
    out.push(['files', id, ...(Array.isArray(part?.scope) ? part.scope.map(String) : []).sort()].join('|'))
    for (const item of Array.isArray(part?.items) ? part.items : [])
      out.push(['line', id, String(item?.quotes ?? ''), String(item?.text ?? ''), String(item?.detail ?? '')].join('|'))
  }
  for (const c of Array.isArray(given?.contracts) ? given.contracts : [])
    if (c && typeof c === 'object')
      out.push(['contract', String(c.text ?? ''), ...(Array.isArray(c.parts) ? c.parts.map(String) : []).sort()].join('|'))
  return out.sort()
}
const readHeader = async ($: any, parent: string | undefined, given?: any): Promise<Header> => {
  const home = switchPath.replace(/[\\/]switch$/, '')
  const set = async (value: Promise<string | undefined>) => (await Promise.resolve(value).catch(() => '')) || ''
  const json = async (path: string) => JSON.parse(await $.fs.read(path))
  const header: Header = { path: ['frame 0'], requirements: {}, principles: [], guideRules: 0 }
  let record: any = null
  try {
    record = await json(`${home}/approved.json`)
  } catch {
    // no answer yet: every frame's words are read as before
  }
  const asks = (frame: any, name: string) => {
    const kept = approvedWords(record, name)
    for (const a of Array.isArray(frame?.asks) ? frame.asks : []) {
      if (typeof a?.id === 'string' && typeof a?.text === 'string')
        header.requirements[a.id] = { text: a.text, isApproved: kept === null || kept.has(words(a.text)) }
    }
  }
  const rules = (frame: any, from: string) => {
    for (const r of Array.isArray(frame?.principles) ? frame.principles : []) {
      if (typeof r?.text === 'string' && !r.indexed && !header.principles.some(x => x.text === r.text))
        header.principles.push({ text: r.text, from })
    }
  }
  let frame0: any
  try {
    frame0 = await json((await set($.env.get('FRAME_LOOP_FRAME0'))) || `${home}/frame0.json`)
  } catch {
    return { ...header, unread: 'frame 0 could not be read' }
  }
  // The frames from the one split up to frame 0, each read once: a circle stops the walk.
  const chain: any[] = []
  const tree = (await set($.env.get('FRAME_LOOP_TREE'))) || `${home}/tree`
  for (let at = parent, seen = new Set<string>(); at && at !== 'root'; ) {
    if (seen.has(at) || !PART_ID.test(at)) return { ...header, unread: 'the parts above this split do not lead to frame 0' }
    seen.add(at)
    let node: any
    try {
      node = await json(`${tree}/${at}.json`)
    } catch {
      return { ...header, unread: 'the part being split is not in the tree' }
    }
    chain.unshift({ ...node, id: at })
    // Frame 0 is the root, however the part's file words it (tree.parent_of).
    at = typeof node?.parent === 'string' && !ROOT_NAMES.includes(node.parent.trim().toLowerCase()) ? node.parent : undefined
  }
  rules(frame0, 'frame 0')
  for (const node of chain) rules(node, typeof node.name === 'string' ? node.name : 'a part')
  header.path.push(...chain.map(n => (typeof n.name === 'string' ? n.name : 'a part')))
  const split = chain.length ? chain[chain.length - 1] : frame0
  asks(split, chain.length ? split.id : 'frame 0')
  try {
    const index = await json((await set($.env.get('FRAME_LOOP_RULES'))) || `${home}/rules.json`)
    header.guideRules = (Array.isArray(index?.rules) ? index.rules : []).filter(
      (r: any) => r?.kind === 'principle' && r?.accepted !== false,
    ).length
  } catch {
    // no rules index: no guide's rules to count
  }
  try {
    // What the hooks read of this split on its way here (splitcheck.py), kept beside their work.
    const work = (await set($.env.get('FRAME_LOOP_WORK'))) || `${home}/work`
    const read = await json(`${work}/split-read.json`)
    // Only this split's own reading: one made for other lines, files or contracts says nothing here.
    const isThisSplit = Array.isArray(read?.of) && JSON.stringify(read.of) === JSON.stringify(shapeOf(given))
    if (read?.parent === (parent ?? 'frame 0') && isThisSplit && read.requirements && read.lines)
      header.check = {
        requirements: read.requirements,
        lines: read.lines,
        thin: Array.isArray(read.thin) ? read.thin : [],
        parts: read.parts && typeof read.parts === 'object' ? read.parts : {},
        contracts: read.contracts && typeof read.contracts === 'object' ? read.contracts : {},
      }
  } catch {
    // the split was not read: its pages say nothing of a reading
  }
  return header
}

// What the split's reading found of one line, in the author's words, or nothing.
const ROLE: Record<string, string> = {
  needed: 'needed: without it the requirement is not met',
  overlaps: 'the other lines already cover this one',
}
// What it found of each requirement split, a line each: only what the author should look at.
// What the reading found of one part against the rules that hold for its files, or nothing.
const breaksOf = (header: Header | undefined, part: Part): string | null => {
  const said = header?.check?.parts?.[part.id]?.breaks
  if (!said) return null
  return said === 'not settled'
    ? `Read before you: not settled whether ${part.name} breaks a rule.`
    : `Read before you: ${part.name} may break your rule "${said}".`
}
// What the reading found of one contract, as its pages show it under the contract: kept, not
// kept, not settled, or not read when the reading never saw it. A reading that did not finish
// is never shown as kept.
const contractRead = (header: Header | undefined, c: Contract): string | null => {
  if (!header?.check) return null // the review says the split was not read
  const said = header.check.contracts?.[c.text]
  if (said === 'kept') return 'Read before you: their lines keep it.'
  if (said === 'not kept') return 'Read before you: their lines do not keep it.'
  if (said === undefined) return 'Not read before you.'
  return 'Read before you: not settled whether their lines keep it.'
}
// The review's line for a contract the author should look at, or nothing when it was kept.
const contractReview = (header: Header | undefined, c: Contract, parts: Part[]): string | null => {
  if (!header?.check) return null
  const said = header.check.contracts?.[c.text]
  const whose = `the lines of ${andList(sharers(c, parts))}`
  if (said === 'kept') return null
  if (said === 'not kept') return `Read before you: ${whose} do not keep "${c.text}".`
  if (said === undefined) return `Not read before you: whether ${whose} keep "${c.text}".`
  return `Read before you: not settled whether ${whose} keep "${c.text}".`
}
const readingOf = (header: Header | undefined, parts: Part[] = [], contracts: Contract[] = []): string[] => {
  const found = header?.check?.requirements
  if (!found) return ['Not read before you: this split was not read against what it splits.']
  const rules = [
    ...parts.map(p => breaksOf(header, p)),
    ...contracts.map(c => contractReview(header, c, parts)),
  ].filter((x): x is string => x !== null)
  const open = Object.entries(found).filter(([, said]) => said !== 'covered')
  if (open.length === 0) return ['Read before you: the parts make what they split true.', ...rules]
  return [
    ...open.map(([id, said]) => {
      const text = header?.requirements[id]?.text ?? 'a requirement'
      return said === 'not covered'
        ? `Read before you: the parts do not make "${text}" true. Something is missing.`
        : `Read before you: not settled whether the parts make "${text}" true.`
    }),
    ...rules,
  ]
}

// The requirements a part's lines narrow, in the frame's words, or what is wrong with them.
const splitting = (header: Header | undefined, items: Item[]): string[] => {
  if (!header) return []
  if (header.unread) return [`(not shown: ${header.unread})`]
  const quoted = [...new Set(items.map(x => x.quotes ?? ''))]
  return quoted.map(id => {
    const found = header.requirements[id]
    if (!found) return `(a line narrows no requirement of ${header.path[header.path.length - 1]})`
    return found.isApproved ? `"${found.text}"` : `"${found.text}"  (not in the words you approved)`
  })
}

// A split's answer: every part named, and each line not approved with the part it is in; a
// contract is named once, with the parts it binds, however many pages showed it.
const splitAnswer = (parts: Part[], contracts: Contract[] = []): string => {
  const names = parts.map(p => p.name).join(', ')
  const all = [
    ...parts.flatMap(p => p.items.map(x => ({ part: p.name, x: { text: itemWords(x), isChecked: x.isChecked } }))),
    ...contracts.map(c => ({ part: `the contract between ${andList(sharers(c, parts))}`, x: c })),
  ]
  const not = all.filter(({ x }) => !x.isChecked)
  const between = contracts.length
    ? `, and the ${count(contracts.length)} ${contracts.length === 1 ? 'contract' : 'contracts'} between them`
    : ''
  if (not.length === 0)
    return `Approved, all ${count(parts.length)} ${parts.length === 1 ? 'part' : 'parts'}: ${names}${between}.`
  const yes = all.filter(({ x }) => x.isChecked)
  const listed = (xs: typeof all) => xs.map(({ part, x }) => `- ${part}: ${x.text}`).join('\n')
  return [
    yes.length ? `Approved:\n${listed(yes)}` : 'Nothing approved.',
    `Not approved:\n${listed(not)}`,
    'Ask me what is wrong with each one I did not approve, before anything of the split is written.',
  ].join('\n\n')
}

// What the next turn reads: plain sentences, as the person would say them.
const answer = ({ items, parts, contracts }: Proposal): string => {
  if (parts) return splitAnswer(parts, contracts)
  const not = items.filter(x => !x.isChecked)
  if (not.length === 0) return items.length === 1 ? 'Approved.' : `Approved, all ${items.length}.`
  const yes = items.filter(x => x.isChecked)
  return [
    yes.length ? `Approved:\n${yes.map(x => `- ${itemWords(x)}`).join('\n')}` : 'Nothing approved.',
    `Not approved:\n${not.map(x => `- ${itemWords(x)}`).join('\n')}`,
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

// Where the work is, as held; a store that has never held it (a session before trees) has none.
const partNow = async ($: any): Promise<PartLine | null> => {
  try {
    return (await read($, part)) ?? null
  } catch {
    return null
  }
}

let switchPath = ''
let busy = false // Claude is working, or a survey holds the prompt: as the band was last drawn
let waking = false
let checkWanted = false // `/frame-loop check` was asked, and Claude not yet told
let checkRetried = false
let closing = false // the picker has an answer on its way, which starts the next turn itself
let retried = 0
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
  const notKept = '\n\nframe-loop could not keep this answer on its record, so these words read as not approved.'
  let kept: { version: number; rounds: unknown[] } = { version: 1, rounds: [] }
  let text: string | undefined
  try {
    text = await $.fs.read(path)
  } catch {
    // no record yet
  }
  if (text !== undefined) {
    try {
      kept = JSON.parse(text)
      if (kept?.version !== 1 || !Array.isArray(kept?.rounds)) return notKept
    } catch {
      return notKept // a record that cannot be read is never written over: the answers in it stay
    }
  }
  // A removal approved takes its words out; one not approved leaves them as they were.
  const texts = (items: Item[], keep: (x: Item) => boolean) => items.filter(keep).map((x: Item) => x.text)
  const at = (await $.clock.now()) / 1000
  // A split is one answer and a round for each part, as each part's file is checked by its own.
  // Each part's round holds what its file is checked against: what each line narrows, by the
  // parent's requirement's id, and the files it may change, as its page showed them.
  const narrows = (items: Item[]) => Object.fromEntries(items.filter(x => x.isChecked).map(x => [x.text, x.quotes ?? null]))
  // A split with contracts keeps, in each part's round, the approved ones that bind it and the
  // other parts each binds; a split with none records as before.
  const bound = (id: string) =>
    held.contracts
      ? {
          contracts: bindingOf(held.contracts, id)
            .filter(c => c.isChecked)
            .map(c => ({ text: c.text, with: c.parts.filter(p => p !== id) })),
        }
      : {}
  for (const { frame, items, split } of held.parts
    ? held.parts.map(p => ({
        frame: p.id,
        items: p.items,
        split: { split: held.parent ?? 'frame 0', name: p.name, scope: p.scope, narrows: narrows(p.items), ...bound(p.id) },
      }))
    : [{ frame: held.node ?? 'frame 0', items: held.items, split: {} }]) {
    kept.rounds.push({
      frame,
      title: held.title,
      ...split,
      approved: texts(items, x => x.isChecked && !x.isRemoval),
      not_approved: texts(items, x => x.isChecked === !!x.isRemoval),
      at,
    })
  }
  try {
    await $.fs.write(path, `${JSON.stringify(kept, null, 1)}\n`)
    return ''
  } catch {
    return notKept
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
      description:
        'Switch frame-loop on or off for this project, or check its install: /frame-loop, /frame-loop on, /frame-loop off, /frame-loop check',
    })
    try {
      await $.tool.register({
        name: 'approve',
        description:
          'Ask the person to approve a decomposition item by item, in a picker with every item checked; ' +
          'a split goes whole, every part at once in `parts`, one page each and one approval. ' +
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
      // Before any file is read: an install with no reading yet is who asks this.
      if (checkWanted && !busy && !closing && !(await $.prompt.read()).text.trim()) {
        checkWanted = false
        // As a wake: what did not go is tried once more, and then the person can ask again.
        void Promise.resolve($.prompt.submit({ text: CHECK })).catch(() => {
          checkWanted = !checkRetried
          checkRetried = true
        })
      }
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
        if ((await partNow($)) !== null) await update($, part, () => null)
      }
      // Where the work is: its own file, so a reading's outcome and the part never overwrite.
      try {
        const where = JSON.parse(await $.fs.read(`${folder}/${id}.part.json`)) as PartLine
        const held = await partNow($)
        if (where?.at !== held?.at) await update($, part, () => where)
      } catch {
        // no tree, or no part engaged yet in this session
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
      // A reading that landed with something to deal with starts a turn, once the session is
      // free: never over the person's words or Claude's work, and it waits until they are done.
      // A prompt they sent since has told Claude already.
      if (
        now.wake && !busy && !waking && !closing && (await $.clock.now()) / 1000 - now.at < WAKE_WITHIN
        && now.at > (await read($, dismissedAt)) && now.at !== (await read($, woken))
        && !(await read($, off)) && (await read($, proposal)) === null
        && !(await $.prompt.read()).text.trim()
      ) {
        // Marked here too: two ticks overlapping must not both start a turn.
        waking = true
        const at = now.at
        await update($, woken, () => at)
        waking = false
        // A wake that did not go is tried once more, and then its ▲ or the next prompt must do.
        void Promise.resolve($.prompt.submit({ text: WAKE })).catch(async () => {
          if (retried === at) return
          retried = at
          await update($, woken, () => 0)
        })
      }
    })

    return next(e)
  })

  on('command.run', { command: 'frame-loop' }, async ($, e) => {
    await followTheHooks($)
    const now = await read($, off)
    const args = e.args.trim().toLowerCase()
    if (args === 'check') {
      checkWanted = true // the tick asks, once the session is free
      checkRetried = false
      return { text: 'frame-loop: checking what a first reading needs.' }
    }
    const want = args === 'on' ? false : args === 'off' ? true : !now
    await $.fs.write(switchPath, want ? 'off\n' : 'on\n')
    await update($, off, () => want)
    return { text: want ? 'frame-loop is off for this project: nothing is checked or read.' : 'frame-loop is on for this project.' }
  })

  on('tool.call', { tool: APPROVE }, async ($, e) => {
    const given = e as unknown as {
      title?: string
      node?: string
      items?: Omit<Item, 'isChecked'>[]
      leftOut?: string[]
      removes?: string[]
      parent?: string
      parts?: { id?: string; name?: string; items?: Omit<Item, 'isChecked'>[]; scope?: string[] }[]
      contracts?: { text: string; parts: string[] }[]
    }
    const leftOut = given.leftOut ?? []
    const title = given.title ?? 'Approve'
    let rows: number
    if (given.parts !== undefined) {
      const refused = splitFaults(given)
      if (refused) return { deny: refused }
      const parts: Part[] = given.parts.map((p, i) => ({
        id: p.id as string,
        name: p.name as string,
        scope: p.scope as string[],
        isSeen: i === 0, // the first page is shown as the picker opens
        items: (p.items ?? []).map(x => ({ text: x.text, detail: x.detail, quotes: x.quotes, isChecked: true })),
      }))
      const contracts: Contract[] | undefined = given.contracts?.map(c => ({
        text: c.text,
        parts: [...new Set(c.parts)],
        isChecked: true,
      }))
      await followTheHooks($)
      const header = await readHeader($, given.parent, given)
      await update($, proposal, () => ({
        title,
        parent: given.parent,
        items: [],
        parts,
        ...(contracts ? { contracts } : {}),
        page: 0,
        leftOut,
        header,
      }))
      const tallest = Math.max(
        parts.length + leftOut.length + (contracts?.length ? contracts.length + 1 : 0),
        ...parts.map(
          p =>
            p.items.length +
            p.items.filter(x => x.detail).length +
            new Set(p.items.map(x => x.quotes)).size +
            (bindingOf(contracts, p.id).length ? 3 * bindingOf(contracts, p.id).length + 1 : 0),
        ),
      )
      rows = Math.min(30, tallest + header.principles.length + HEADER_ROWS + 6)
    } else {
      if (given.contracts !== undefined) return { deny: 'contracts are written only between the parts of a split.' }
      const items: Item[] = [
        ...(given.items ?? []).map(x => ({ text: x.text, detail: x.detail, isChecked: true })),
        ...(given.removes ?? []).map(text => ({ text, isChecked: true, isRemoval: true })),
      ]
      if (items.length === 0) return { deny: 'approve needs at least one item.' }
      await update($, proposal, () => ({ title, node: given.node, items, leftOut }))
      const details = items.filter(x => x.detail).length
      rows = Math.min(30, items.length + details + leftOut.length + 7)
    }
    const opened = await $.ui.open({
      id: PICKER,
      title,
      focus: true,
      closeOnEscape: true,
      holdToasts: true,
      rows,
    })
    if (!opened.isPlaced) {
      await update($, proposal, () => null)
      return { deny: `The picker could not be shown (${opened.reason}). Ask in chat instead.` }
    }
    return { result: 'The picker is open. End your turn now: the answer arrives as the next message.' }
  })

  // Closed with Escape: nothing is approved, and Claude must not be left waiting in silence.
  on('ui.close', async ($, e, next) => {
    const held = e.id === PICKER ? await read($, proposal) : null
    const closed = await next(e)
    if (held) {
      await update($, proposal, () => null) // any close: a picker gone must not hold back a wake
      if (e.origin.kind === 'person') await $.prompt.fill({ text: 'I closed the picker without approving anything.' })
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
      closing = true
      try {
        await followTheHooks($)
        const held = await read($, proposal)
        await update($, proposal, () => null)
        await $.ui.close({ id: PICKER })
        if (held) await send(answer(held) + (await remember($, held)))
      } finally {
        closing = false
      }
    }
    const buttons = (approve: string) => (
      <Box marginTop={1} gap={2}>
        <Button key="approve" variant="primary" onPress={() => finish(text => $.prompt.submit({ text }))}>
          {approve}
        </Button>
        <Button key="missing" onPress={() => finish(text => $.prompt.fill({ text: `${text}\n\nMissing: ` }))}>
          Add what's missing
        </Button>
      </Box>
    )
    const leftOutLines =
      now.leftOut.length > 0 ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color="inactive">Left out, on purpose:</Text>
          {now.leftOut.map(line => (
            <Text color="inactive">{` - ${line}`}</Text>
          ))}
        </Box>
      ) : null
    if (now.parts) {
      const parts = now.parts
      const review = parts.length
      const page = Math.min(Math.max(now.page ?? 0, 0), review)
      // A page turned shows that part as seen, and the focus starts on its first line.
      const turn = async (to: number) => {
        await update($, proposal, p => {
          if (!p?.parts) return p
          const at = Math.min(Math.max(to, 0), p.parts.length)
          return { ...p, page: at, parts: p.parts.map((x, i) => (i === at ? { ...x, isSeen: true } : x)) }
        })
        void Promise.resolve($.ui.focus({ requestId: PICKER, key: to >= review ? 'part-0' : `item-${to}-0` })).catch(
          () => undefined,
        )
      }
      const toggleIn = (at: number, index: number) =>
        update($, proposal, p =>
          p?.parts
            ? {
                ...p,
                parts: p.parts.map((x, i) =>
                  i === at
                    ? { ...x, items: x.items.map((y, j) => (j === index ? { ...y, isChecked: !y.isChecked } : y)) }
                    : x,
                ),
              }
            : p,
        )
      // A contract has one check mark, however many pages show it: taken out on one, out on all.
      const contracts = now.contracts ?? []
      const toggleContract = (index: number) =>
        update($, proposal, p =>
          p?.contracts
            ? { ...p, contracts: p.contracts.map((c, i) => (i === index ? { ...c, isChecked: !c.isChecked } : c)) }
            : p,
        )
      // The header is the code's, from the tree: where the split sits, the requirement this page
      // narrows when it is one, and which page of how many. Claude's title is only the tab's.
      const header = now.header
      const shown = splitting(header, page < review ? parts[page].items : parts.flatMap(p => p.items))
      const where = [...(header?.path ?? ['frame 0'])]
      const quoted = [...new Set((page < review ? parts[page].items : parts.flatMap(p => p.items)).map(x => x.quotes))]
      const one = quoted.length === 1 && !header?.unread ? header?.requirements[quoted[0] ?? ''] : undefined
      if (one) where.push(one.text)
      const top = (
        <Box flexDirection="column">
          <Box gap={2}>
            <Text bold>{where.join(' › ')}</Text>
            <Button key="prev" plain label="←" onPress={() => turn(page - 1)} />
            <Text>{page < review ? `${page + 1} / ${review}` : 'review'}</Text>
            <Button key="next" plain label="→" onPress={() => turn(page + 1)} />
          </Box>
          {shown.map((line, i) => (
            <Text>{`${i === 0 ? 'Splitting:  ' : '            '}${line}`}</Text>
          ))}
        </Box>
      )
      const holds =
        header && (header.principles.length > 0 || header.guideRules > 0) ? (
          <Box flexDirection="column" marginTop={1}>
            <Text>Holds for every part:</Text>
            {header.principles.map(r => (
              <Text>{`  · ${r.text}  (${r.from})`}</Text>
            ))}
            {header.guideRules > 0 ? (
              <Text color="inactive">{`  · and the project's ${count(header.guideRules)} rules from its guide`}</Text>
            ) : null}
          </Box>
        ) : null
      if (page === review) {
        const checked = (p: Part) => p.items.filter(x => x.isChecked).length
        const wide = Math.max(...parts.map(p => p.name.length))
        return (
          <Box flexDirection="column">
            {top}
            <Box flexDirection="column" marginTop={1}>
              {parts.map((p, i) => (
                <Button key={`part-${i}`} plain autoFocus={i === 0 ? true : undefined} onPress={() => turn(i)}>
                  {`${p.name.padEnd(wide)}   ${lines(p.items.length).padEnd(9)}`}
                  {checked(p) < p.items.length ? `${p.items.length - checked(p)} not approved   ` : ''}
                  {p.isSeen ? 'seen' : 'not seen yet'}
                </Button>
              ))}
            </Box>
            {contracts.length > 0 ? (
              <Box flexDirection="column" marginTop={1}>
                <Text>Contracts between the parts:</Text>
                {contracts.map(c => (
                  <Text>{`  ${c.isChecked ? '·' : '(not approved)'} ${c.text}  (${sharers(c, parts).join(', ')})`}</Text>
                ))}
              </Box>
            ) : null}
            {readingOf(header, parts, contracts).length > 0 ? (
              <Box flexDirection="column" marginTop={1}>
                {readingOf(header, parts, contracts).map(line => (
                  <Text>{line}</Text>
                ))}
              </Box>
            ) : null}
            {holds}
            {leftOutLines}
            {buttons(
              parts.every(p => checked(p) === p.items.length) && contracts.every(c => c.isChecked)
                ? parts.length === 1
                  ? 'Approve the part'
                  : `Approve all ${count(parts.length)}`
                : 'Approve checked',
            )}
          </Box>
        )
      }
      const part = parts[page]
      return (
        <Box flexDirection="column">
          {top}
          <Box marginTop={1} flexDirection="column">
            <Text bold>{`Part ${page + 1}:  ${part.name}`}</Text>
            <Text color="inactive">{`May change:  ${part.scope.join(', ')}`}</Text>
          </Box>
          {part.items.map((item, index) => (
            <Box flexDirection="column">
              <Button
                key={`item-${page}-${index}`}
                plain
                autoFocus={index === 0 ? true : undefined}
                onPress={() => toggleIn(page, index)}
              >
                {`[${item.isChecked ? 'x' : ' '}] ${item.text}`}
              </Button>
              {item.detail ? <Text color="inactive">{`      ${item.detail}`}</Text> : null}
              {ROLE[header?.check?.lines[item.text] ?? ''] ? (
                <Text color="inactive">{`      ${ROLE[header?.check?.lines[item.text] ?? '']}`}</Text>
              ) : null}
              {header?.check?.thin?.includes(item.text) ? (
                <Text color="inactive">{'      says which words it narrows, not how'}</Text>
              ) : null}
            </Box>
          ))}
          {bindingOf(contracts, part.id).length > 0 ? (
            <Box flexDirection="column" marginTop={1}>
              <Text>Contracts with other parts:</Text>
              {bindingOf(contracts, part.id).map((c, index) => (
                <Box flexDirection="column">
                  <Button key={`contract-${page}-${index}`} plain onPress={() => toggleContract(contracts.indexOf(c))}>
                    {`[${c.isChecked ? 'x' : ' '}] ${c.text}`}
                  </Button>
                  <Text color="inactive">{`      shared with: ${sharers(c, parts, part.id).join(', ')}`}</Text>
                  {contractRead(header, c) ? <Text color="inactive">{`      ${contractRead(header, c)}`}</Text> : null}
                </Box>
              ))}
            </Box>
          ) : null}
          {holds}
          {(header?.check?.parts?.[part.id]?.scoped ?? []).length > 0 ? (
            <Box flexDirection="column">
              <Text>{"For this part's files, from the project's guide:"}</Text>
              {(header?.check?.parts?.[part.id]?.scoped ?? []).map(line => (
                <Text>{`  · ${line}`}</Text>
              ))}
            </Box>
          ) : null}
          {(header?.check?.parts?.[part.id]?.owes ?? []).length > 0 ? (
            <Box flexDirection="column">
              <Text>A change here will owe:</Text>
              {(header?.check?.parts?.[part.id]?.owes ?? []).map(line => (
                <Text>{`  · ${line}`}</Text>
              ))}
            </Box>
          ) : null}
          {breaksOf(header, part) ? <Text>{breaksOf(header, part)}</Text> : null}
          <Box marginTop={1}>
            {parts.map((p, i) => (
              <Box>
                <Button key={`go-${i}`} plain dimColor={i !== page} onPress={() => turn(i)}>
                  {i === page ? `[${p.name}]` : p.name}
                </Button>
                <Text color="inactive">{'  ·  '}</Text>
              </Box>
            ))}
            <Button key="go-review" plain dimColor onPress={() => turn(review)}>
              review
            </Button>
          </Box>
        </Box>
      )
    }
    return (
      <Box flexDirection="column">
        {now.items.map((item, index) => (
          <Box flexDirection="column">
            <Button key={`item-${index}`} plain autoFocus={index === 0 ? true : undefined} onPress={() => toggle(index)}>
              {`[${item.isChecked ? 'x' : ' '}] ${itemWords(item)}`}
            </Button>
            {item.detail ? <Text color="inactive">{`    ${item.detail}`}</Text> : null}
          </Box>
        ))}
        {leftOutLines}
        {buttons('Approve checked')}
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
      // What the last turn found was seen; a wake is no sign of that, so a ▲ stays in the band.
      if (e.text !== WAKE) await update($, dismissedAt, () => t)
    } catch {
      // the band never holds up a prompt
    }
    return next(e)
  }).catch(($, e, next) => next(e)) // a throw or an overrun, too: the prompt goes on

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    busy = e.props.isWorking || e.props.hasSurvey
    const now = await read($, live)
    // A store that has never held a part (a session before trees) reads as none.
    const where = await partNow($)
    if (e.props.hasSurvey || (now === null && !where?.part && !where?.finished) || (await read($, off))) {
      return next(e)
    }
    const t = (await $.clock.now()) / 1000
    const { Box, Button, Text } = $.ui.resolve(e)
    // The part the work is in, after any line: one line always says it, in the author's words.
    const inPart = where?.part ? ` · ${where.part.done ? `${where.part.name} is done` : `in ${where.part.name}`}` : ''
    const partLine = () => {
      const here = where?.part
      const finished = where?.finished && where.finished !== here?.name ? where.finished : null
      const done = here?.done ? here.name : finished
      const said = here
        ? done
          ? `${done} is done${here.done ? '' : ` · now in ${here.name}`}`
          : `in ${here.name}`
        : `${finished} is done`
      return (
        <Box>
          <Text color={done ? 'success' : 'inactive'}>{done ? '✓ ' : '· '}</Text>
          <Text bold>frame-loop </Text>
          <Text>{said}</Text>
          {here ? <Text color="inactive">{` · ${here.where}`}</Text> : null}
        </Box>
      )
    }
    if (now === null) return partLine()

    if (now.state === 'reading') {
      if (t - now.at > STALE) {
        return where?.part || where?.finished ? partLine() : next(e)
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
          <Text color="inactive"> · {when}{spentTokens(now.tokens)}{inPart}</Text>
        </Box>
      )
    }

    const shown = outcome(now.decision)
    if (shown === null || now.at < (await read($, dismissedAt))) {
      return where?.part || where?.finished ? partLine() : next(e)
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
          <Text color="inactive">{spent}{spentTokens(now.tokens)}{inPart} </Text>
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
