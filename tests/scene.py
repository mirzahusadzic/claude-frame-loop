"""A made-up project for a test: a git repository in a temporary folder, frame files written into it, the person's
ticks made through machine.approve as the band will make them, readings kept through machine's own writer, and
the hooks driven in this process.
"""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from frameloop import approval, claims, hooks, machine, reading, recoil, words, work

ROOT = Path(__file__).resolve().parent.parent

STEP = {"maker": "a-made-up-maker", "lines": ["Each client has a count of its own.", "A request adds one to it."]}
TURNED = ["A client shares a count with others.", "A request adds nothing to it."]
PAIR = "the pair"  # a claim's step by default: STEP, and the claim reversed with TURNED, made for its own words
OF = "Requests are counted per client and reset each day."
# The made-up shop's claims: two at the root owned by their parts, and one at each of three parts.
C = "Requests are counted per client."
D = "Each client is shown its count."
L = "Requests are counted for each client."
A = "Each request names its client by one id."
W = "A page shows a client its count."
PARTS = ("", "limits", "auth", "web")
# The levels a stand-in run is kept with, by the outcome the fixed rules read them to.
LEVELS = {
    "rests": {"baseline": "yes", "repeat": "yes", "ablation": "unclear", "input-inversion": "no"},
    "gap": {"baseline": "no", "repeat": "no", "ablation": "unclear"},
    "doubt": {"baseline": "yes", "repeat": "yes", "ablation": "yes"},
}
FILES = ("limits/count.py", "auth/client.py", "web/page.py", "README.md")


def _pattern(template):
    """A template of words.py as a pattern: a count is digits, any other slot is anything but the separator of a
    turn's line and the characters no line of the tool's holds, so that no slot swallows the pieces after it or hides
    a line inside itself."""
    slot = f"(?:(?!{re.escape(words.SEP)})[^{words.UNSHOWN}])*"
    pieces = re.split(r"(\{[a-z]+\})", template)
    return re.compile("".join(r"\d+" if p == "{n}" else slot if p.startswith("{") else re.escape(p) for p in pieces))


PATTERNS = [_pattern(template) for _, said in words.TOLD for template in said]


BLOCK = words.BLOCK_HEAD.split("{")[0]  # how the person's block at a turn's end begins


def unmade(text):
    """The lines of a text that no template of words.py makes, whole or as the pieces of a turn's line. A line is cut
    at a line feed alone, so a line that hides another separator is one no template makes."""

    def made(piece):
        return any(pattern.fullmatch(piece) for pattern in PATTERNS)

    return [line for line in text.split("\n") if not made(line) and not all(map(made, line.split(words.SEP)))]


def timeless(text):
    """A text with how long each run's spend took said as 0 s, so a test can hold the rest of it exactly."""
    took = r"\d+ m \d+ s|\d+ m|\d+ s"
    for template in (words.TOOK_EXAMINED, words.TOOK_READING):
        head, tail = template.split("{took}")[0], template.split("{took}")[1].split("{")[0]
        text = re.sub(f"({re.escape(head)})(?:{took})({re.escape(tail)})", r"\g<1>0 s\g<2>", text)
    return text


def texts(out):
    """Every text a hook's answer hands the session or the person."""
    return [
        text
        for text in (out.get("systemMessage"), out.get("hookSpecificOutput", {}).get("additionalContext"))
        if text is not None
    ]


def pair(said, step=STEP):
    """A step with the claim reversed kept beside it, as an examination keeps one: the reversal's words made from the
    claim's, and its own lines."""
    return {**step, "reversal": {"words": words.NOT_SO.format(words=said), "lines": list(TURNED)}}


def claim(said, owner="work", narrows=None, predicts="fulfilled", state="open", step=PAIR, **more):
    step = pair(said) if step == PAIR else step
    return {
        "words": said,
        "of": OF,
        "narrows": narrows,
        "owner": owner,
        "step": step,
        "predicts": predicts,
        "state": state,
        **more,
    }


def under(place, said):
    """What a part's claim quotes of the claim above it."""
    return {"place": place, "words": said}


def frame(place, held, holds=(), split=None, opens=()):
    return {
        "version": 1,
        "place": place,
        "claims": list(held),
        "holds": list(holds),
        "split": split,
        "open": list(opens),
    }


def split(parts, holes=(), contracts=(), carried=True):
    return {
        "parts": list(parts),
        "holes": list(holes),
        "contracts": list(contracts),
        "examined": {"carried": carried, "marks": []},
    }


def hole(place, said, parts):
    return {"claim": claims.claim_id(place, said), "from": list(parts), "kind": "fulfils"}


def contract(provides, depends, command="exit 0", name="CLIENT-ID-V1"):
    return {
        "id": name,
        "words": "A client is named by one id.",
        "provides": provides,
        "depends": list(depends),
        "command": command,
    }


def item(said, owner="work", narrows=None, predicts="fulfilled", step=PAIR, old=None):
    """A claim as a proposal holds it, by default with the pair made for its own words."""
    step = pair(said) if step == PAIR else step
    return {"words": said, "of": OF, "narrows": narrows, "owner": owner, "step": step, "predicts": predicts, "old": old}


def proposal(kind, place, items, holds=(), split_=None, options=None, reason=None):
    return {
        "kind": kind,
        "place": place,
        "title": "A made-up proposal",
        "items": list(items),
        "holds": list(holds),
        "split": split_,
        "options": options,
        "reason": reason,
    }


def part(place, *items, holds=()):
    """A part of a crossing as a proposal lays it down: its place, its own claims and what must hold there."""
    return {"place": place, "items": list(items), "holds": list(holds)}


def shop_split(contracts=None):
    """The made-up shop's crossing as a proposal lays it down: each part with its own claim, limits and auth under C
    and web under D, each hole naming its claim by its words, and auth providing limits a contract."""
    holes = [
        {"claim": C, "from": ["limits", "auth"], "kind": "fulfils"},
        {"claim": D, "from": ["web"], "kind": "fulfils"},
    ]
    parts = [
        part("limits", item(L, narrows=under("", C))),
        part("auth", item(A, narrows=under("", C))),
        part("web", item(W, narrows=under("", D))),
    ]
    return {
        "parts": parts,
        "holes": holes,
        "contracts": [contract("auth", ["limits"])] if contracts is None else list(contracts),
    }


def shop_crossing(contracts=None, step=PAIR):
    """The made-up shop's root split into its three parts, in one proposal: C and D above, owned by the parts."""
    held = proposal(
        "split",
        "",
        [item(C, owner="parts", step=step), item(D, owner="parts", step=step)],
        split_=shop_split(contracts),
    )
    if step != PAIR:
        for each in held["split"]["parts"]:
            each["items"] = [{**one, "step": step} for one in each["items"]]
    return held


def shop(scene, holds=(), contracts=None, carried=True, approve=True, on=True, opens=()):
    """The made-up shop, committed: the root split into limits, auth and web, auth providing limits a contract;
    every thing in it ticked by the person, and the reading on, unless asked otherwise."""
    holes = [hole("", C, ["limits", "auth"]), hole("", D, ["web"])]
    contracts = [contract("auth", ["limits"])] if contracts is None else contracts
    parts = split(["limits", "auth", "web"], holes, contracts, carried)
    scene.frame(frame("", [claim(C, owner="parts"), claim(D, owner="parts")], holds, parts, opens))
    scene.frame(frame("limits", [claim(L, narrows=under("", C))]))
    scene.frame(frame("auth", [claim(A, narrows=under("", C))]))
    scene.frame(frame("web", [claim(W, narrows=under("", D))]))
    for path in FILES:
        scene.write(path)
    scene.commit()
    if approve:
        scene.approve(*PARTS)
    machine.set_switch(scene.where, on)
    return scene


_SESSIONS = itertools.count(1)


class Scene:
    def __init__(self, test):
        self.test = test
        held = tempfile.TemporaryDirectory(prefix="project-")
        test.addCleanup(held.cleanup)
        self.outside = Path(held.name).resolve()
        self.project = self.outside / "shop"
        self.project.mkdir()
        self.session = f"a-made-up-session-{next(_SESSIONS)}"  # one a scene, as each real session has its own id
        self.word = {"approved.json": None, "switch": None}  # the band's store: nothing kept yet
        self.git("init", "-q", "-b", "main")

    @property
    def where(self) -> Path:
        return machine.folder(self.project)

    def git(self, *args, cwd=None) -> str:
        done = subprocess.run(["git", *args], cwd=cwd or self.project, check=True, capture_output=True, text=True)
        return done.stdout

    def write(self, path, text="made up\n") -> None:
        file = self.project / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, "utf-8")

    def frame(self, held) -> None:
        self.write(claims.file_of(held["place"]), json.dumps(held, indent=1) + "\n")

    def commit(self, message="Work") -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def cover(self) -> None:
        """The made-up shop's README moved into the web part, so no file of its work lies in no claim's place."""
        self.git("mv", "README.md", "web/README.md")
        self.commit("Every file in a claim's place")

    def approve(self, *places) -> None:
        """The person's ticks of each place, as the writer makes them: every thing in it, and it as a set."""
        tree = claims.load(self.project)
        for place in places:
            frame = tree.frames[place]
            machine.approve(self.where, claims.ticks(place, frame), {place: approval.set_of(frame)})

    def trees(self) -> dict:
        return work.trees(
            self.project, self.where, work.snapshot(self.project, self.where), claims.load(self.project).places()
        )

    def snapped(self, *args) -> str:
        """git, as the tool runs it on its own snapshots, whose objects lie in the machine folder's store."""
        more = work.store(self.project, self.where)
        done = subprocess.run(
            ["git", *args], cwd=self.project, check=True, capture_output=True, text=True, env={**os.environ, **more}
        )
        return done.stdout

    def keep(self, place, said, outcome="rests", step=PAIR) -> dict:
        """A reading of the work as it is now, kept by hand through machine's own writer, with evidence that stands:
        a reading frame of the claim and records whose levels read again to the outcome. Its step is the claim's own
        as the frame holds it, where it holds the claim; else the pair made for its words."""
        tree, trees = claims.load(self.project), self.trees()
        held = next((each for each in tree.frames.get(place, {"claims": []})["claims"] if each["words"] == said), None)
        if step == PAIR:
            step = held["step"] if held is not None and held["step"] is not None else pair(said)
        cid, sides = claims.claim_id(place, said), recoil.across(tree, place, trees)
        predicts = held["predicts"] if held is not None else "fulfilled"
        stepped = claims.step_digest({"step": step})
        spans = [
            reading._span("s", "standing", "Made up before.", "a-made-up-empty-tree..a-made-up-tree"),
            reading._span("a1", "account", "Made up.", f"a-made-up-tree..{trees.get(place)}"),
        ]
        interventions, allowed = {"repeat": True, "ablation": True}, {"ablation": ["no", "unclear"]}
        if reading.inversion(step, said):
            interventions["inputInversion"], allowed["inputInversion"] = reading.inversion(step, said), ["no"]
        asked = reading.frame(
            reading.reading_name(cid, stepped, trees.get(place), sides),
            "read",
            said,
            spans,
            ["a1"],
            interventions,
            allowed,
            reading.kept_line(step, said),
            most=2,
        )
        folder = self.where / "runs" / f"kept-{uuid.uuid4().hex}"
        machine.keep_json(folder / "frame.json", asked)
        (folder / "runs").mkdir()
        levels = LEVELS[outcome]
        (folder / "runs" / "1.jsonl").write_text(
            "".join(json.dumps({"trial": trial, "observation": level}) + "\n" for trial, level in levels.items()),
            "utf-8",
        )
        runs = (folder / "runs").relative_to(self.where).as_posix()
        machine.keep_reading(
            self.where,
            cid,
            stepped,
            predicts,
            trees.get(place),
            sides,
            outcome,
            ["baseline carried"],
            runs,
            reading.evidence(self.where, folder),
        )
        return machine.readings(self.where)[-1]

    def told_unread(self, told, said, why, n=1, predicts="fulfilled") -> None:
        """A claim the change bears on that was not read, as a turn's end tells it: counted with why on the turn's own
        line, n of them for that why; its own line kept from the person, and told to the session alone."""
        lines = told if isinstance(told, list) else told.splitlines()
        own = words.read_line(said, "unread", predicts, why)
        self.test.assertIn(words.not_read("nostep" if why == words.NO_STEP else why, n), lines[0].split(words.SEP))
        self.test.assertNotIn(own, lines)
        turn = [row for row in machine.logged(self.where) if row.get("event") == "turn"][-1]
        self.test.assertIn(own, turn.get("aside") or [])

    def standing(self, place, said) -> recoil.Standing:
        return hooks.see(self.project).shown[(place, claims.claim_id(place, said))]

    def hook(self, name, **more) -> dict:
        event = {"hook_event_name": name, "cwd": str(self.project), "session_id": self.session, **more}
        said = hooks.respond(json.dumps(event))
        return json.loads(said) if said else {}

    def call(self, change, tool="Bash", call="call-1") -> dict:
        """A tool call: the hook before it, the change it makes, and what the hook after it says."""
        self.hook("PreToolUse", tool_name=tool, tool_use_id=call, tool_input={})
        change()
        return self.hook("PostToolUse", tool_name=tool, tool_use_id=call, tool_input={}, tool_response={})

    def turn(self, change) -> str:
        """A prompt, the change, and the turn's end; what the turn's end told in sentences: what the session is told at
        its next prompt, and what the person reads where no check ran, as the person reads the check as a block."""
        self.hook("UserPromptSubmit", prompt="Made up.")
        change()
        before = len(machine.logged(self.where)) if self.where.exists() else 0
        out = self.hook("Stop", stop_hook_active=False).get("systemMessage", "")
        rows = machine.logged(self.where)[before:] if self.where.exists() else []
        turns = [row for row in rows if row.get("event") == "turn"]
        return turns[-1].get("said", "") if turns and out.startswith(BLOCK) else out

    def ended(self, **more) -> str:
        """The turn's end hook alone; what it told in sentences, as `turn` gives them."""
        before = len(machine.logged(self.where)) if self.where.exists() else 0
        out = self.hook("Stop", stop_hook_active=False, **more).get("systemMessage", "")
        rows = machine.logged(self.where)[before:] if self.where.exists() else []
        turns = [row for row in rows if row.get("event") == "turn"]
        return turns[-1].get("said", "") if turns and out.startswith(BLOCK) else out

    def person(self, change) -> str:
        """A prompt, the change, and the turn's end; what the person read of it."""
        self.hook("UserPromptSubmit", prompt="Made up.")
        change()
        return self.hook("Stop", stop_hook_active=False).get("systemMessage", "")

    def by_hand(self, *argv, marked=False, cwd=None, given=""):
        """`python3 -m frameloop`, run from the project as the band or the person runs it, or from `cwd`, with `given`
        on its input: its exit code, and its answer read as JSON where it is JSON. Marked, it runs as a hook's child
        would."""
        env = {**os.environ, "PYTHONPATH": str(ROOT), **({machine.IN_HOOK: "1"} if marked else {})}
        done = subprocess.run(
            [sys.executable, "-m", "frameloop", *argv],
            cwd=cwd or self.project,
            capture_output=True,
            text=True,
            env=env,
            input=given,
        )
        try:
            return done.returncode, json.loads(done.stdout)
        except ValueError:
            return done.returncode, done.stdout.rstrip("\n")

    def propose(self, held) -> dict:
        """A proposal written to a file of the agent's and passed to `propose`; what `propose` answered."""
        file = self.outside / "proposal.json"
        file.write_text(held if isinstance(held, str) else json.dumps(held), "utf-8")
        return self.by_hand("propose", str(file))[1]

    def picked(self, held, *ticked_and_more) -> dict:
        """A proposal kept, and what the person picked of it written by the writer; what `approve` answered, less the
        word it carries for the band."""
        said = self.approving(self.propose(held)["id"], *ticked_and_more)[1]
        return {key: value for key, value in said.items() if key != "word"}

    def approving(self, ref, *rest, marked=False):
        """`approve` as the band runs it at the person's press: with the digests `show` gave the picker of what it
        showed."""
        code, shown = self.by_hand("show", ref)
        return self.by_hand(
            "approve", ref, *rest, "--shown", shown["shown"] if code == 0 else "none:none", marked=marked
        )

    def examine(self, ident, step=None, reversed_step=None, **readers) -> dict:
        """The tool's own examination of a kept proposal, as a session asks for it in a shell call, with the reading
        on as the person switched it and the stand-in maker making `step` and `reversed_step`: the result it kept."""
        given = {"readers": {"alone-": "worded", "split-": "all", "contract-": "all", **readers}}
        given.update({key: value for key, value in (("step", step), ("reversed_step", reversed_step)) if value})
        self.fakes(gadfly=given)
        machine.set_switch(self.where, True)
        self.hook("UserPromptSubmit", prompt="Examine it.")
        self.shell(f": frame-loop examine {ident}", call=f"examine-{ident}-{uuid.uuid4().hex[:6]}")
        return json.loads((self.where / "proposals" / f"{ident}.examined.json").read_text("utf-8"))

    def pressed(self, *argv) -> dict:
        """The band's own write at the person's press: `approve` or `switch` run, and the word it answers kept as the
        band keeps it in the host's store."""
        code, said = self.approving(*argv[1:]) if argv[0] == "approve" else self.by_hand(*argv)
        if code == 0:
            self.word = said.get("word", self.word)
        return said

    def look(self, word=None):
        """The band's look, as it runs at each prompt and before each turn's end: the word it keeps sent to `look`;
        its exit code and answer."""
        held = self.word if word is None else word
        return self.by_hand("look", given=json.dumps(held))

    def fakes(self, claude=None, gadfly=None) -> None:
        """The stand-ins' scenarios for this test (tests/bin), and the file each call they are given is kept in."""
        given = {"FAKE_LOG": str(self.outside / "calls.jsonl")}
        for name, said in (("FAKE_CLAUDE", claude), ("FAKE_GADFLY", gadfly)):
            if said is not None:
                path = self.outside / f"{name.lower()}.json"
                path.write_text(json.dumps(said), "utf-8")
                given[name] = str(path)
        patched = mock.patch.dict(os.environ, given)
        patched.start()
        self.test.addCleanup(patched.stop)

    def calls(self, program=None) -> list:
        """Each call the stand-ins were given, in order, of one program or of both."""
        try:
            lines = (self.outside / "calls.jsonl").read_text("utf-8").splitlines()
        except OSError:
            return []
        return [row for row in map(json.loads, lines) if program is None or row["program"] == program]

    def shell(self, command, call="call-shell") -> dict:
        """A shell call holding a command, as the session makes one: what the hook after it says."""
        given = {"command": command}
        self.hook("PreToolUse", tool_name="Bash", tool_use_id=call, tool_input=given)
        return self.hook("PostToolUse", tool_name="Bash", tool_use_id=call, tool_input=given, tool_response={})

    def declare(self, place, said) -> dict:
        """The session's declaration that its work in this turn carries a claim, by the claim's handle."""
        handle = reading.handles(claims.load(self.project))[(place, claims.claim_id(place, said))]
        return self.shell(f": frame-loop carries {handle}", call=f"declare-{handle}")
