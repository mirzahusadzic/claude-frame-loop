// Every fixed word the band shows or says. Every other sentence is the Python side's, shown as given;
// these are the picker's words, the line's counts and its tool's own words, in one place so a script can
// gather them into the page of everything said.
export const LABELS = {
  name: 'frame-loop',
  // The picker's header: the state, then the rows counted and what is left for the person.
  pick: 'pick',
  checked: 'checked',
  checkOff: 'check off',
  checkFailed: 'check failed',
  checking: 'checking',
  rows: ['row', 'rows'],
  toReview: 'to review',
  allAnswered: 'all answered',
  options: ['option', 'options'],
  pickOne: 'pick one',
  picked: 'picked',
  // The last line while the pane does not hold the keys, which the person gives it with ctrl+x tab: how to give them,
  // and the keys they will be; what a line typed in the host's prompt is, and what enter there sends.
  toAnswer: 'ctrl+x tab to answer:',
  hintAll: 'What do you want to change?',
  sendsAll: 'enter sends it as your change to the whole proposal',
  // The last line while the check runs.
  pleaseWait: 'Please wait while frame-loop checks what you asked',
  // The line enter opens under a row or his sentence, dim while empty.
  inputHint: 'enter to confirm · or write your change here',
  // His sentence, the mismatch that brought a proposal back, and the table's heading.
  youSaid: 'You said: ',
  // His sentence in one line: its first line, cut where it does not fit, and how many lines more.
  cutLead: '… +',
  cut: '…',
  lines: ['line', 'lines'],
  // The lines of a list out of view above and below its window, in a pane shorter than the whole.
  more: 'more',
  above: '↑',
  below: '↓',
  again: 'Asked again because: ',
  build: 'I\'d build',
  buildIn: 'I\'d build it in',
  numbers: ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'],
  parts: ['part', 'parts'],
  pickHead: 'Pick one',
  check: 'Check',
  // The heading over a place's holds that a command checks, each one row with its command after it.
  byCommand: 'checked by a command',
  // The status words at the right edge, and the marks of the path, the note and the cursor.
  clear: 'Clear',
  review: 'Review',
  yes: 'Yes',
  note: '↳ ',
  cursor: '❯',
  down: ' → ',
  shared: ' ↔ ',
  ok: 'OK, build it',
  retry: 'Check again',
  // A note the band puts under a row itself, as a question, or plainly where the row could not be checked.
  unchecked: 'could not be checked: no step was made for it.',
  notOurs: 'could not be checked: the check kept here is not this tool’s own.',
  noCheckYet: 'nothing checks this yet. Build it with no check for now?',
  contractUnsure: ['the check did not say whether ', ' keep this. Is it fine as it is?'],
  and: 'and',
  replaces: 'this replaces “',
  replacesTail: '”. Is the new wording right?',
  costs: 'costs',
  // A check that could not run, said in one plain line.
  checkFailedLead: 'The check could not run:',
  checkSilent: 'The check ended without a word.',
  // A line the person sends at the host's prompt while the picker is open: his change, to the row he chose or to the
  // whole proposal, as the session is told it beside his line, which reaches it as he typed it.
  changeRow: 'frame-loop: the person’s message is a change to this row of proposal',
  changeWhole: 'frame-loop: the person’s message is a change to the whole of proposal',
  changeTold:
    'Nothing of it is approved: propose it again with this change, through the propose tool, and build nothing ' +
    'until the person approves it in the picker. If the message is not about the proposal at all, answer it, and ' +
    'the same proposal opens again unchanged. If the person asks to drop the proposal altogether, withdraw it ' +
    'through the withdraw tool.',
  writing: 'writing…',
  writerFailed: 'Nothing was approved:',
  // The details of a row.
  detailStep: 'step: ',
  detailTurned: 'turned around: ',
  detailNoStep: 'no step',
  detailCommand: 'command: ',
  // The last line while the pane holds the keys: each key that applies now, and its meaning; and the full list.
  keys: {
    y: 'yes, fine',
    enter: 'enter',
    choose: 'confirm or change',
    change: 'change this row',
    changeAll: 'change it all',
    confirm: 'confirm',
    send: 'send your change',
    build: 'build it',
    tab: 'tab',
    next: 'next',
    page: 'pgup pgdn',
    pageMeans: 'a page',
    d: 'details',
    whole: 'show it whole',
    help: 'h',
    helpMeans: 'help',
    listClose: 'close it',
    esc: 'esc',
    close: 'close it for now',
    r: 'retry',
    back: 'back, nothing sent',
  },
  help: [
    '↑ ↓, tab, shift+tab  move between You said, the rows and OK, build it, round again at either end',
    'pgup pgdn  move a page up or down the list',
    'y  yes, fine: answers the row under the cursor and goes to the next under review',
    'enter  open a line under the row, or under You said for the whole; enter in the empty line confirms a row ' +
      'under review, words send your change, and on OK it builds it',
    'o  build it, once nothing is left to review',
    'd  the details of the row: its step, its reversal and what else the check found; on You said, all of it',
    'h  this list; h again closes it',
    'esc  close this list, or the picker for now, nothing approved; /frame-loop reopens the picker as you left it',
  ],
  // The picker closed by esc, waiting undrawn where the terminal is too narrow for a pane nobody asked for, or open
  // without the keyboard; closed while the session answers his change; and the one line that tells what was approved.
  waiting: 'a proposal waits',
  reopens: '/frame-loop reopens it',
  opens: '/frame-loop opens it',
  answers: 'ctrl+x tab answers it',
  changeSent: 'your change went to the session',
  opensAgain: 'the picker opens again after its answer',
  approved: 'approved',
  in: 'in',
  // The propose call's one quiet line in the transcript.
  proposed: 'proposed',
  inPicker: 'in the picker',
  counts: { open: 'open', fulfilled: 'passed', rest: 'closed by you', refused: 'refused' },
  // The band at rest: the tree's tension with its total, "1 of 6 passed", then what needs the person's eye, each
  // counted, as one and as many, then what the checks of this session spent.
  of: 'of',
  flags: {
    nostep: ['not checked: no step', 'not checked: no step'],
    off: ['not checked: the check is off', 'not checked: the check is off'],
    opened: ['changed since their last check', 'changed since their last check'],
    outside: ['file nobody asked for', 'files nobody asked for'],
    unchecked: ['contract with no check', 'contracts with no check'],
    failing: ['check that failed', 'checks that failed'],
  },
  // While a run goes on: a frame of the spinner each second, how long it has run, and what it spends.
  spinner: ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
  seconds: 's',
  minutes: 'm',
  spend: { tokens: 'tokens', calls: ['model call', 'model calls'] },
  thousands: 'k',
  millions: 'm',
  ended: 'ended without a word',
  usage: '/frame-loop · /frame-loop on · /frame-loop off',
  personOnly: 'Only the person switches frame-loop, typing /frame-loop on or /frame-loop off.',
  cannotRun: 'frame-loop could not run:',
  exitCode: 'exit code',
  command: 'The frame here and its tension; on or off switches the check',
  // What the session is told of the picker, which it alone reads.
  opened:
    'The picker is open in a pane of its own with this proposal. Say one sentence that points the person ' +
    'to the picker, and do not retell the proposal; then end your turn: the answer arrives as the person’s next ' +
    'message.',
  checkingTold: 'frame-loop checks it now, itself, and the picker shows its rows once the check is done.',
  waitsBehind: 'Another picker is open: this proposal waits behind proposal',
  waits: 'It opens by itself, and is checked, when those before it close. Say so in one sentence, then end your turn.',
  replaced: 'It takes the place of proposal',
  replacedTail: ', kept for the same place and kind, which is dropped from the picker with nothing of it written.',
  asked:
    'Each prompt tells you the picker as the person sees it: say what is open or waiting from that alone, never ' +
    'from memory.',
  pickerNow: 'frame-loop, the picker as the person sees it now:',
  pickerHolds: 'the picker holds proposal',
  pickerAside: 'closed for now by the person, who reopens it with /frame-loop',
  pickerChanged: 'closed while you answer the person’s change to it, and open again once your turn ends',
  pickerChecking: 'being checked',
  pickerWaiting: 'waiting behind it:',
  pickerEmpty: 'the picker holds no proposal, and none waits',
  unapprovedTold:
    'Nothing of it is approved: build nothing toward it until the person approves it in the picker. A message of ' +
    'the person’s that answers the proposal means: propose it again with that change, through the propose tool.',
  proposal: 'frame-loop: the picker of proposal',
  closedUnwritten: 'closed with nothing written, so nothing of it is approved.',
  unplaced: 'The picker could not be shown here:',
  // The withdraw tool: the session's way to close a proposal at the person's word, and only there.
  withdrawTool:
    'Withdraw the proposal open in frame-loop’s picker, at the person’s word: only while their change to it, sent ' +
    'from the picker or typed at the prompt, stands unanswered, and only where they asked to drop it altogether. ' +
    'Nothing of it is approved or written. Otherwise propose it again with their change.',
  withdrawId: 'the id of the proposal to withdraw, as the picker holds it',
  withdrawn: 'is withdrawn at the person’s word, with nothing of it approved or written.',
  withdrawRefused:
    'frame-loop withdraws a proposal only at the person’s word: no change of theirs to it stands now, so the picker ' +
    'keeps proposal',
  cannotLook:
    'frame-loop could not hold the person’s ticks and switch on this machine to their word, so what another hand ' +
    'wrote there may count until the band looks again:',
  tool:
    'Put a proposal to the person in frame-loop’s picker, for four uses: `frame`, his sentence as claims; ' +
    '`split`, one crossing whole: items the claims above owned by "parts", each part under `split` as { place, ' +
    'items, holds } narrowing one above, holes naming each claim above by words with waiting parts, and contracts ' +
    'as { id, words, provides, depends, command }, command null if unchecked; `reframe`, new words with `old` and ' +
    'the mismatch as `reason`; `options`, a choice with what each costs. One claim a row: a sentence saying several ' +
    'things becomes rows sharing `of`. Each takes one of two roads. What a person using or running the software ' +
    'could see for themselves is an item, seen in the work. What only a run can show is a hold, its command failing ' +
    'while it is not so: how the software is made, what it is built from, a number inside it, a published test ' +
    'vector. What neither can show here, such as another operating system, stays an item predicting "open", its ' +
    '`ask` saying so. Fields, one each: `place` the folder, "" for root, never "."; `of` his sentence, in his ' +
    'words; `narrows` null at root, else the claim above as { place, words }; `owner` "work", or "parts" for a claim ' +
    'a split takes apart; `step` null, or { maker, lines } with maybe `reversal` as { words, lines }: the check makes ' +
    'the pair written; `predicts` what a reading of the finished work is expected to say, written before any ' +
    'reading: "fulfilled" where it carries the claim, "open" where it would not, never what stands today; `old` ' +
    'null, or the replaced words in a reframe; `ask`, optional, your own question to the person where the claim says ' +
    'more, less or other than his words, one line, such as "You said numbered; I start at 1. OK?"; ask too where you ' +
    'picked one meaning of a word of theirs that could mean two things, such as "You said suit; I take it as cards. ' +
    'OK?". One sentence becomes one item and two holds. A frame at the root, in full: ' +
    '{"kind":"frame","place":"","title":"Notes","items":[{"words":"List prints the notes sorted by date.","of":' +
    '"List prints the notes sorted by date, with its own sort, checked by tests.","narrows":null,"owner":"work","step":null,"predicts":"fulfilled",' +
    '"old":null}],"holds":[{"words":"No sort library.","command":"python3 check.py"},{"words":"The sort tests ' +
    'pass.","command":"python3 -m unittest test_sort"}],"split":null,"options":null,"reason":null}. A crossing of ' +
    'the root into store and cli, in full: {"kind":"split","place":"","title":"Notes","items":[{"words":"A note ' +
    'added is listed.","of":"Add and list.","narrows":null,"owner":"parts","step":null,"predicts":"fulfilled",' +
    '"old":null}],"holds":[],"split":{"parts":[{"place":"store","items":[{"words":"Store keeps notes.","of":' +
    '"Add and list.","narrows":{"place":"","words":"A note added is listed."},"owner":"work","step":null,' +
    '"predicts":"fulfilled","old":null}],"holds":[]},{"place":"cli","items":[{"words":"List prints notes.","of":' +
    '"Add and list.","narrows":{"place":"","words":"A note added is listed."},"owner":"work","step":null,' +
    '"predicts":"fulfilled","old":null}],"holds":[]}],"holes":[{"claim":"A note added is listed.","from":' +
    '["store","cli"],"kind":"fulfils"}],"contracts":[{"id":"NOTES-V1","words":"Notes stay ordered.","provides":' +
    '"store","depends":["cli"],"command":null}]},"options":null,"reason":null}. A crossing is checked and approved ' +
    'whole. frame-loop checks its form: faults come back as this tool’s error saying expected and got, to mend and ' +
    'propose again. A row looking like several claims comes back once the same way: split it, or send the same ' +
    'proposal again to keep it as written. With no faults and the check on, it checks the proposal itself and the ' +
    'picker opens in a pane of its own, rows shown once done; run nothing. Say one sentence that points the person ' +
    'there, and never retell the proposal. Frame files are written by frame-loop at the person’s approval, never by ' +
    'you; the approval stays on their machine, never in a frame file.',
} as const

// The tool's input, as the session reads it: the proposal's fields, less the id the Python side gives. Every field
// of a proposal's form is asked for, since `propose` keeps no proposal with one missing; null stands for none. An
// item's `ask` alone may be left out.
const text = { type: 'string' }
export const SCHEMA = {
  type: 'object',
  properties: {
    kind: { enum: ['frame', 'split', 'reframe', 'options'] },
    place: { type: 'string', description: 'the folder the claims govern: "" for the root, never "."' },
    title: text,
    items: {
      type: 'array',
      description: 'the claims, one a row, each a thing a person using or running the software could see for themselves',
      items: {
        type: 'object',
        properties: {
          words: text,
          of: { type: 'string', description: 'his sentence the claim comes from, in his words' },
          narrows: {
            type: ['object', 'null'],
            description: 'the claim above, quoted by its place and its words; null at the root',
            properties: { place: text, words: text },
            required: ['place', 'words'],
          },
          owner: { enum: ['work', 'parts'], description: 'work, or parts' },
          step: {
            type: ['object', 'null'],
            description: 'the claim taken apart, where there is a step: its maker, its lines, and maybe its reversal; else null',
            properties: {
              maker: text,
              lines: { type: 'array', items: text },
              reversal: {
                type: 'object',
                description: 'the claim reversed, as the check keeps it: its words and its own lines',
                properties: { words: text, lines: { type: 'array', items: text } },
                required: ['words', 'lines'],
              },
            },
            required: ['maker', 'lines'],
          },
          predicts: { enum: ['fulfilled', 'open'], description: 'what a reading of the finished work is expected to say, written before any reading; ' +
            '"open" for a claim neither the work nor a command can show on this machine' },
          old: { type: ['string', 'null'], description: 'in a reframe, the words this claim replaces; else null' },
          ask: { type: ['string', 'null'], description: 'your own question to the person, one line, where the claim says more, ' +
            'less or other than their words, where you picked one meaning of a word of theirs that could mean two ' +
            'things, or where nothing on this machine can show it; else leave it out' },
        },
        required: ['words', 'of', 'narrows', 'owner', 'step', 'predicts', 'old'],
      },
    },
    holds: { type: 'array', description: 'what only a run can show, one a row, as { words, command }, the command failing ' +
      'while it is not so; or paths a change must not touch, as { words, untouched }' },
    split: {
      type: ['object', 'null'],
      description:
        '{ parts, holes, contracts }, for a split, the whole crossing: a part is { place, items, holds }, its items ' +
        'claims as above, each narrowing a claim above; a hole is { claim, from, kind }, naming its claim by the ' +
        'claim’s words and the parts it waits for; a contract is { id, words, provides, depends, command }, its ' +
        'command null for no check yet; else null',
    },
    options: {
      type: ['array', 'null'],
      description: 'for options, each option with what it costs; else null',
      items: { type: 'object', properties: { words: text, cost: text }, required: ['words', 'cost'] },
    },
    reason: { type: ['object', 'null'], description: '{ words, about }: the mismatch that brought a reframe, and the words of the claim it is about; else null' },
  },
  required: ['kind', 'place', 'title', 'items', 'holds', 'split', 'options', 'reason'],
} as const
