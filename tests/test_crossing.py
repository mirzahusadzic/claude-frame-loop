"""The whole way through one crossing, with the stand-ins: proposed, examined and ticked whole; the work in one part
read and fulfilled, then the other's; the claims above fulfilled by their parts with no call, and the line for
equilibrium; a change in one part that breaks the contract's check, which opens the part on its other side; and a gap
in a part, confirmed by the person, climbing through the gate to the claim above. Each step holds the sentence told."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import unittest
from unittest import mock

from scene import Scene, item, part, proposal, texts, timeless, under, unmade

from frameloop import claims, hooks, machine, now, reading, recoil, words

ADD = "Running the tool with add and a note saves that note."
LIST = "Running the tool with list prints the saved notes, numbered from 1."
KEEPS = "The store keeps each note it is given, after the notes before it."
HANDS = "The add command hands its note to the store."
PRINTS = "The list command prints each note the store gives back, numbered from 1."
CHECK = "grep -q 'VERSION = 1' store/notes.py"
CONTRACT = {
    "id": "NOTES-V1",
    "words": "The store gives back every note it keeps, oldest first.",
    "provides": "store",
    "depends": ["cli"],
    "command": CHECK,
}
RESIDUAL = "The list command cannot number notes the store gives back unsorted."
STORE_SAID = "1. The tool keeps each note it is given, after the notes kept before it."
CLI_SAID = (
    "1. The add command hands the note it is given on to the store.\n"
    "2. The list command prints each note it gets back, numbered from 1."
)
SERVES = {"hands": "hands its note", "prints": "prints each note"}


def crossing():
    """The person's two root claims split into store and cli, with one contract, as one proposal."""
    holes = [
        {"claim": ADD, "from": ["store", "cli"], "kind": "fulfils"},
        {"claim": LIST, "from": ["cli"], "kind": "fulfils"},
    ]
    parts = [
        part("store", item(KEEPS, narrows=under("", ADD), step=None)),
        part("cli", item(HANDS, narrows=under("", ADD), step=None), item(PRINTS, narrows=under("", LIST), step=None)),
    ]
    return proposal(
        "split",
        "",
        [item(ADD, owner="parts", step=None), item(LIST, owner="parts", step=None)],
        split_={"parts": parts, "holes": holes, "contracts": [CONTRACT]},
    )


class WholeWayTests(unittest.TestCase):
    def told(self, scene, out):
        """What a hook told, whole; every line of it made by words.py."""
        said = "\n".join(texts(out)) if isinstance(out, dict) else out
        self.assertEqual(unmade(said.replace(words.PROPOSE, "")), [], said)
        return said

    def turn(self, scene, change, writer, **gadfly):
        """A prompt, the change, and the turn's end, with the writer and the readers it is read by."""
        scene.fakes(
            claude={"result": writer},
            gadfly={
                "readers": {"reading-": "rests", "which-": "first", "gate-": "piece", **gadfly.pop("readers", {})},
                **gadfly,
            },
        )
        return self.told(scene, scene.turn(change)).splitlines()

    def test_a_crossing_proposed_examined_ticked_worked_fulfilled_broken_and_climbed(self):
        scene = Scene(self)
        scene.git("commit", "-q", "--allow-empty", "-m", "Nothing built yet")
        machine.set_switch(scene.where, True)

        # Proposed whole, and examined whole: each claim taken apart, each claim above read with its parts.
        said = scene.propose(crossing())
        self.assertEqual(said["said"], words.proposed("1"))
        scene.fakes(gadfly={"readers": {"alone-": "worded", "split-": "all", "contract-": "all"}})
        scene.hook("UserPromptSubmit", prompt="Examine it.")
        out = scene.shell(": frame-loop examine 1", call="examine-1")
        path = scene.where / "proposals" / "1.examined.json"
        result = json.loads(path.read_text("utf-8"))
        held = json.loads((scene.where / "proposals" / "1.json").read_text("utf-8"))
        # Five claims and their reversals made by the maker; the contract's maker call is no record of the stand-in's,
        # whose firm keeps no step, so a real run counts one more.
        spent = now.Spent(
            0,
            0,
            10,
            sum(len(each.read_text("utf-8").splitlines()) for each in (scene.where / "runs").rglob("*.jsonl")),
            None,
        )
        said = f"{words.examined_crossing('1', result, held, True, str(path))} {words.took_examined(spent)}"
        self.assertEqual(timeless(self.told(scene, out)), "\n".join([said] * 2))
        self.assertEqual(
            result["above"],
            {
                "0": {"carried": True, "carry": ["cli", "store"], "idle": []},
                "1": {"carried": True, "carry": ["cli"], "idle": []},
            },
        )
        self.assertEqual(
            (result["validated"], result["contracts"], sorted(result["steps"])),
            (True, {"0": True}, ["0", "1", "2", "3", "4"]),
        )

        # Ticked whole, as a person would: show, then approve with what was shown.
        code, approved = scene.approving("1", "--ticked", "0,1")
        self.assertEqual(code, 0, approved)
        tree = claims.load(scene.project)
        self.assertEqual(sorted(tree.frames), ["", "cli", "store"])
        handles = reading.handles(tree)
        pairs = [
            (said_, handles[(at, claims.claim_id(at, said_))])
            for at, said_ in (("store", KEEPS), ("cli", HANDS), ("cli", PRINTS))
        ]
        parts = (("store", [(KEEPS, None)], []), ("cli", [(HANDS, None), (PRINTS, None)], []))
        self.assertEqual(
            approved["said"], words.written([(ADD, None), (LIST, None)], [], tree.frames[""]["split"], pairs, parts)
        )
        first = self.told(scene, scene.hook("UserPromptSubmit", prompt=approved["said"]))
        named = sorted(
            ((at, claims.claim_id(at, said_)), said_)
            for at, said_ in (("store", KEEPS), ("cli", HANDS), ("cli", PRINTS))
        )
        self.assertIn(
            words.handles_now([(said_, handles[key]) for key, said_ in sorted(named, key=lambda e: e[0][1])]),
            first.splitlines(),
        )
        scene.hook("Stop", stop_hook_active=False)

        # The store's work, read and fulfilled; the claims above wait for cli.
        store = self.turn(scene, lambda: scene.write("store/notes.py", "VERSION = 1\nNOTES = []\n"), STORE_SAID)
        self.assertEqual(store[0].split(words.SEP)[:2], [words.TURN.format(places="store"), words.HELD.format(n=1)])
        rested = words.rests(["baseline", "repeat", "ablation", "input-inversion"])
        self.assertIn(words.read_line(KEEPS, "rests", "fulfilled", rested), store)
        self.assertEqual(scene.standing("store", KEEPS).tension, "fulfilled")
        self.assertEqual(scene.standing("", ADD).tension, "open")

        # The cli's work, read and fulfilled: the store's claim stands, as the contract's check held.
        cli = self.turn(scene, lambda: scene.write("cli/main.py", "import sys\n"), CLI_SAID, serves=SERVES)
        line = cli[0].split(words.SEP)
        self.assertEqual(line[:2], [words.TURN.format(places="cli"), words.HELD.format(n=1)])
        shammed = words.rests(["baseline", "repeat", "ablation", "sham-1", "input-inversion"])  # each line harmless to
        for said_ in (HANDS, PRINTS):  # the other's claim, so cut in its stead
            self.assertIn(words.read_line(said_, "rests", "fulfilled", shammed), cli)
        self.assertEqual(scene.standing("store", KEEPS).tension, "fulfilled")

        # The claims above, fulfilled by their parts with no call; and the line for equilibrium.
        tree, trees = claims.load(scene.project), scene.trees()
        seen = hooks.see(scene.project)
        with mock.patch("subprocess.Popen", side_effect=AssertionError("a call was made")):
            shown = recoil.standings(
                tree, seen.ticks, machine.readings(scene.where), trees, True, seen.sets, seen.failing
            )
        self.assertEqual(
            {said_: shown[("", claims.claim_id("", said_))].tension for said_ in (ADD, LIST)},
            {ADD: "fulfilled", LIST: "fulfilled"},
        )
        self.assertEqual(line[-1], words.AT_REST)
        self.assertIn(words.READY, hooks.frame_told(scene.project).splitlines())

        # A change in store that breaks the contract's check opens cli, the part on its other side.
        broke = self.turn(scene, lambda: scene.write("store/notes.py", "VERSION = 2\nNOTES = []\n"), STORE_SAID)
        pieces = broke[0].split(words.SEP)
        for piece in (
            words.CONTRACT_BROKE.format(id="NOTES-V1"),
            words.OPENED_ACROSS.format(places="cli", id="NOTES-V1"),
            words.SIDEWAYS.format(n=2),
        ):
            self.assertIn(piece, pieces)
        self.assertNotIn(words.AT_REST, pieces)
        self.assertEqual(
            {said_: scene.standing("cli", said_).tension for said_ in (HANDS, PRINTS)}, {HANDS: "open", PRINTS: "open"}
        )
        self.assertIn(
            words.last_failed("failed", "NOTES-V1", True, ("cli",)), hooks.frame_told(scene.project).splitlines()
        )

        # Mended, the check holds again: cli's readings stand as they were, and the frame is at rest once more.
        mended = self.turn(scene, lambda: scene.write("store/notes.py", "VERSION = 1\nNOTES = []\n"), STORE_SAID)
        self.assertEqual(mended[0].split(words.SEP)[-1], words.AT_REST)

        # A gap in cli, which the person confirms; it climbs through the gate to the claim above.
        printing = f"reading-{claims.claim_id('cli', PRINTS)[:16]}"
        gap = self.turn(
            scene,
            lambda: scene.write("cli/main.py", "import sys\nprint(sys.argv)\n"),
            CLI_SAID,
            serves=SERVES,
            readers={printing: "gap"},
        )
        self.assertIn(words.read_line(PRINTS, "gap", "fulfilled"), gap)
        frame = claims.load(scene.project).frames["cli"]
        frame["open"] = [{"words": RESIDUAL, "claim": claims.claim_id("cli", PRINTS), "tree": scene.trees()["cli"]}]
        scene.frame(frame)  # the person confirms the gap as a residual, and ticks it
        scene.commit("The gap, confirmed")
        scene.approve("cli")
        climbed = self.turn(
            scene,
            lambda: scene.write("cli/main.py", "import sys\nprint(sys.argv[1:])\n"),
            CLI_SAID,
            serves=SERVES,
            readers={printing: "gap"},
        )
        self.assertIn(words.step(RESIDUAL, "climbs", LIST, "claim", None), climbed)
        gates = [c for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("gate-")]
        self.assertEqual([c["argv"][0] for c in gates], ["successor", "firm", "gate"])
        self.assertEqual(gates[0]["frame"]["inputs"][0]["text"], reading.question(LIST))


if __name__ == "__main__":
    unittest.main()
