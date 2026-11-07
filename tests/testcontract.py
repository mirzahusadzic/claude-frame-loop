"""The CLI contract: the real `gadfly firm` (0.12.0 or later) with fake readers, read
by the gate. No network and no cost. Run folders go under tests/.work/ (ignored),
each one fresh, and nothing is deleted."""

import json
import os
import subprocess
import sys
import unittest
from unittest import mock
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GADFLY = Path(os.environ.get("GADFLY_CHECKOUT", Path.home() / "gadfly"))
sys.path.insert(0, str(ROOT / "frameloop"))
import frames  # noqa: E402
import readers  # noqa: E402
import gate  # noqa: E402

FRAME0 = json.loads((ROOT / "tests/fixtures/greeter-frame0.json").read_text())
STEP = {"id": "contract", "summary": "a step", "claim": {"serves": "A5"},
        "facts": {"files touched": "review notes"}}


NAMES = {"Ideal": "fake-ideal", "Literal": "fake-literal", "Stuck": "fake-stuck",
         "Broken": "fake-broken"}


def _gadfly(args, work):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "tests")}
    return subprocess.run(["uv", "run", "--project", str(GADFLY), "gadfly", *args],
                          capture_output=True, text=True, env=env, cwd=GADFLY)


def stage_one(frame, battery):
    """Stage 1 reads baseline and repeat only: `gadfly run --only`, then `report`.
    (`firm` has no --only, as this contract test found.)"""
    frame = {**frame, "battery": {"kind": NAMES[battery]}}
    work = ROOT / "tests/.work" / uuid.uuid4().hex
    work.mkdir(parents=True)
    path, out = work / "frame.json", work / "records.jsonl"
    path.write_text(json.dumps(frame))
    ran = _gadfly(["run", str(path), "--battery", f"fakebatteries:{battery}", "--out",
                   str(out), "--calls", "6", "--output-tokens", "10", "--token-budget",
                   "1000", "--only", "baseline", "--only", "repeat", "--json"], work)
    if ran.returncode != 0:
        return ran.returncode, json.loads(ran.stdout or ran.stderr)
    read = _gadfly(["report", str(path), str(out), "--json"], work)
    return read.returncode, json.loads(read.stdout or read.stderr)


def firm(frame, battery, only=None):
    # The frame names the battery that serves it; a fake one here, never a model.
    frame = {**frame, "battery": {"kind": NAMES[battery]}}
    work = ROOT / "tests/.work" / uuid.uuid4().hex
    (work / "runs").mkdir(parents=True)
    path = work / "frame.json"
    path.write_text(json.dumps(frame))
    cmd = ["uv", "run", "--project", str(GADFLY), "gadfly", "firm", str(path),
           "--battery", f"fakebatteries:{battery}", "--runs", str(work / "runs"),
           "--calls", "48", "--output-tokens", "10",
           "--token-budget", "2000", "--json"]
    for trial in only or []:
        cmd += ["--only", trial]
    env = {**os.environ, "PYTHONPATH": str(ROOT / "tests")}
    done = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=GADFLY)
    return done.returncode, json.loads(done.stdout or done.stderr)


@unittest.skipUnless((GADFLY / "pyproject.toml").exists(), "no Gadfly checkout")
class ContractTests(unittest.TestCase):
    def test_each_answer_has_room_for_high_reasoning(self):
        # Try 3: at high reasoning, 4 of 42 calls ended incomplete at a 4,000-token cap.
        import reader
        self.assertGreaterEqual(reader.CAP, 16000)

    def test_gadfly_reads_the_frames_most_and_refuses_another(self):
        work = ROOT / "tests/.work" / uuid.uuid4().hex
        (work / "runs").mkdir(parents=True)
        path = work / "frame.json"
        path.write_text(json.dumps({**frames.which_ask(FRAME0, STEP, "anthropic"), "battery": {"kind": NAMES["Ideal"]}}))
        done = subprocess.run(["uv", "run", "--project", str(GADFLY), "gadfly", "firm", str(path),
                               "--battery", "fakebatteries:Ideal", "--runs", str(work / "runs"), "--most", "3",
                               "--calls", "48", "--output-tokens", "10", "--json"],
                              capture_output=True, text=True, cwd=GADFLY,
                              env={**os.environ, "PYTHONPATH": str(ROOT / "tests")})
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("declares most 2", done.stderr)

    def test_the_reader_leaves_the_most_runs_to_the_frame(self):
        import reader
        seen = []
        with mock.patch.object(reader, "_gadfly", lambda args, watch=None: seen.append(args) or
                               subprocess.CompletedProcess(args, 0, "{}", "")), \
             mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(ROOT / "tests/.work")}):
            reader.run(frames.which_ask(FRAME0, STEP, "anthropic"))
        self.assertNotIn("--most", seen[0])

    def test_the_pinned_gadfly_is_at_least_0_12(self):
        done = _gadfly(["--version"], ROOT)
        version = tuple(int(x) for x in done.stdout.split()[-1].split(".")[:2])
        self.assertGreaterEqual(version, (0, 12), done.stdout)

    def test_an_ideal_reader_on_the_declared_ask_passes(self):
        code, result = firm(frames.which_ask(FRAME0, STEP, "anthropic"), "Ideal")
        self.assertEqual(code, 0)
        self.assertEqual(result["category"], "carried")
        self.assertEqual(gate.which_ask(result, ["A5"])[0], gate.PASS)

    def test_a_frame_declaring_every_ask_is_accepted_by_gadfly(self):
        everything = [a["id"] for a in FRAME0["asks"]]
        frame = frames.which_ask(FRAME0, {**STEP, "claim": {"serves": everything}}, "anthropic")
        path = ROOT / "tests/.work/every-ask.json"
        path.write_text(json.dumps({**frame, "battery": {"kind": "fake-ideal"}}))
        done = subprocess.run(["uv", "run", "--project", str(GADFLY), "gadfly", "check-frame", str(path)],
                              capture_output=True, text=True, cwd=GADFLY)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_completion_frame_is_accepted_by_gadfly(self):
        sys.path.insert(0, str(ROOT / "tests"))
        from testframes import ASK0, STEPS
        for with_diffs in (True, False):
            frame = frames.completion(ASK0, "A1", STEPS, "public", with_diffs=with_diffs)
            path = ROOT / f"tests/.work/completion-{with_diffs}.json"
            path.write_text(json.dumps(frame))
            done = subprocess.run(["uv", "run", "--project", str(GADFLY), "gadfly", "check-frame", str(path)],
                                  capture_output=True, text=True, cwd=GADFLY)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_reader_that_ignores_the_body_rises(self):
        code, result = firm(frames.which_ask(FRAME0, STEP, "anthropic"), "Stuck")
        self.assertEqual(code, 0)
        decision, reason = gate.which_ask(result, ["A5"])
        self.assertEqual(decision, gate.RISE, reason)

    def test_a_broken_harness_blocks_and_is_never_read(self):
        code, result = firm(frames.which_ask(FRAME0, STEP, "anthropic"), "Broken")
        self.assertEqual(code, 3)
        self.assertEqual(gate.which_ask(result, ["A5"])[0], gate.BLOCK)

    def test_a_reader_that_follows_the_label_not_the_sense_rises(self):
        code, result = firm(frames.which_ask(FRAME0, STEP, "anthropic"), "Literal")
        self.assertEqual(code, 0)
        self.assertEqual(result["category"], "coupled but misaligned")
        self.assertEqual(gate.which_ask(result, ["A5"])[0], gate.RISE)

    def test_stage_one_reads_baseline_and_repeat(self):
        code, result = stage_one(frames.violation(FRAME0, STEP, "anthropic"), "Stuck")
        self.assertEqual(code, 0)
        decision, reason = gate.violation_stage_one(result)
        self.assertEqual(decision, gate.RISE, reason)  # the stuck reader names P1 twice
        self.assertIn("P1", reason)


@unittest.skipUnless((GADFLY / "pyproject.toml").exists(), "no Gadfly checkout")
class LiveReaderTests(unittest.TestCase):
    """reader.run, the live path the hook uses, against the real CLI with fake batteries."""

    def setUp(self):
        self.saved = dict(os.environ)
        os.environ["PYTHONPATH"] = str(ROOT / "tests")
        os.environ["FRAME_LOOP_WORK"] = str(ROOT / "tests/.work")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_reader_runs_which_ask_to_a_firm_verdict(self):
        import reader

        os.environ["FRAME_LOOP_BATTERY"] = "fakebatteries:Ideal"
        frame = {**frames.which_ask(FRAME0, STEP, "anthropic"), "battery": {"kind": "fake-ideal"}}
        result = reader.run(frame)
        self.assertEqual(gate.which_ask(result, ["A5"])[0], gate.PASS, result)

    def test_reader_in_parallel_reaches_the_same_verdicts(self):
        # Until firm takes --parallel: runs side by side, then firm reads the kept runs.
        import reader

        os.environ["FRAME_LOOP_PARALLEL"] = "3"
        for battery, kind, expected in (("Ideal", "fake-ideal", gate.PASS),
                                        ("Literal", "fake-literal", gate.RISE),
                                        ("Broken", "fake-broken", gate.BLOCK)):
            os.environ["FRAME_LOOP_BATTERY"] = f"fakebatteries:{battery}"
            frame = {**frames.which_ask(FRAME0, STEP, "anthropic"), "battery": {"kind": kind}}
            result = reader.run(frame)
            self.assertEqual(gate.which_ask(result, ["A5"])[0], expected, (battery, result))
            self.assertEqual(result["reader"]["parallel"], 3, battery)

    def test_reader_reports_the_calls_and_tokens_it_made(self):
        # the gate's line shows the readers' tokens. firm --json gives `usage` and
        # `made` (Gadfly 2c09a1a); stage one's run/report do not, so its records are
        # summed by name the same way.
        import reader

        os.environ["FRAME_LOOP_BATTERY"] = "fakebatteries:Ideal"
        frame = {**frames.which_ask(FRAME0, STEP, "anthropic"), "battery": {"kind": "fake-ideal"}}
        for parallel in ("1", "3"):
            os.environ["FRAME_LOOP_PARALLEL"] = parallel
            result = reader.run(frame)
            self.assertGreater(result["made"], 0, parallel)
            self.assertEqual(result["usage"]["output_tokens"], result["made"], parallel)
        os.environ["FRAME_LOOP_BATTERY"] = "fakebatteries:Stuck"
        frame = {**frames.violation(FRAME0, STEP, "anthropic"), "battery": {"kind": "fake-stuck"}}
        result = reader.run(frame, only=("baseline", "repeat"))
        self.assertEqual(result["made"], 6)
        self.assertEqual(result["usage"]["output_tokens"], 6)

    def test_a_private_name_in_a_path_is_masked_and_gadfly_lets_it_through(self):
        """Seen on the loop's release: the mod's folder carried the project's private name,
        so every turn touching it was refused unread. Masked, it is read; the name never goes."""
        import reader
        import hook
        names = ROOT / "tests/.work/private-names.txt"
        names.write_text("secret-project\n")
        os.environ["FRAME_LOOP_PRIVATE_NAMES"] = str(names)
        os.environ["FRAME_LOOP_BATTERY"] = "fakebatteries:Ideal"
        text = "Files: modified mods/Secret-Project-live/hooks/register.tsx, secret-projects.md\nadds a band"
        masked = hook.mask_private(text)
        self.assertNotIn("secret-project", masked.casefold().replace("secret-projects", ""))
        self.assertIn("mods/[private]-live/", masked)
        self.assertIn("secret-projects.md", masked)  # never inside a longer word, as Gadfly reads it
        frame = {**frames.which_ask(FRAME0, {**STEP, "summary": masked}, "public"),
                 "battery": {**frames.READERS["public"], "kind": "fake-ideal"}}
        self.assertNotIn("withheld", json.dumps(reader.run(frame)))

    def test_a_training_reader_never_gets_a_private_name(self):
        # The audit: the scratch fixture's own text carried "frame-loop" to Contributor in
        # 116 frames, through battery runs that bypass the hook's channel guard.
        import reader
        names = ROOT / "tests/.work/private-names.txt"
        names.write_text("# one name per line\nsecret-project\n")
        os.environ["FRAME_LOOP_PRIVATE_NAMES"] = str(names)
        os.environ["FRAME_LOOP_BATTERY"] = "fakebatteries:Ideal"
        frame = {**frames.which_ask(FRAME0, {**STEP, "summary": "touches Secret-Project code"}, "public"),
                 "battery": {**frames.READERS["public"], "kind": "fake-ideal"}}
        result = reader.run(frame)
        self.assertEqual(gate.which_ask(result, ["A5"])[0], gate.BLOCK, result)
        self.assertIn("withheld", json.dumps(result))  # Gadfly refuses it (29fe18c), before any call
        frame["battery"] = {**frames.READERS["anthropic"], "kind": "fake-ideal"}
        self.assertNotIn("withheld", json.dumps(reader.run(frame)))  # a non-training reader may read it

    def test_frameloops_line_hash_is_gadflys(self):
        sys.path.insert(0, str(ROOT / "frameloop"))
        import hook
        line = "   def private_algorithm(x):    return sum(v for v in x)  "
        done = subprocess.run(["uv", "run", "--project", str(GADFLY), "python", "-c",
                               f"from midwife.withhold import line_sha256; print(line_sha256({line!r}))"],
                              capture_output=True, text=True, cwd=GADFLY)
        self.assertEqual(done.stdout.strip(), hook._hash(hook._norm(line)))

    def test_reader_runs_stage_one_as_run_then_report(self):
        import reader

        os.environ["FRAME_LOOP_BATTERY"] = "fakebatteries:Stuck"
        frame = {**frames.violation(FRAME0, STEP, "anthropic"), "battery": {"kind": "fake-stuck"}}
        result = reader.run(frame, only=("baseline", "repeat"))
        self.assertEqual(gate.violation_stage_one(result)[0], gate.RISE, result)
        os.environ["FRAME_LOOP_PARALLEL"] = "3"
        result = reader.run(frame, only=("baseline", "repeat"))
        self.assertEqual(gate.violation_stage_one(result)[0], gate.RISE, result)



class GateErrorTests(unittest.TestCase):
    """Any error object or failing exit is never read as a verdict: it blocks."""

    def test_an_error_object_or_a_failing_exit_blocks(self):
        for result in ({"error": {"type": "UsageError", "exit": 2, "message": "the battery stopped the run"}},
                       {"exit": 2}, {"exit": 7}, {"exit": 3}, {"stopped": "StopRun"}):
            self.assertEqual(gate.which_ask(result, ["A5"])[0], gate.BLOCK, result)
            self.assertEqual(gate.violation_stage_one(result)[0], gate.BLOCK, result)

if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless((GADFLY / "pyproject.toml").exists(), "no Gadfly checkout")
class WalkContractTests(unittest.TestCase):
    """The climb routes by Gadfly's walk (one rule in one place). Its --json is
    Gadfly's API; the fields frame-loop reads are pinned here, so a drift fails loudly."""

    FRAME0 = {"id": "root", "asks": [
        {"id": "A1", "text": "users can greet by name", "inversion": {"users can greet by name": "users can never greet by name"}},
        {"id": "A2", "text": "the README says how to run it", "inversion": {"the README says how to run it": "the README says nothing"}}],
        "principles": [{"id": "P1", "text": "No new dependency is added."}], "triggers": []}
    GREETER = {"id": "greeter", "parent": "root", "scope": ["hello.py", "tests/*", "README.md"], "asks": [
        {"id": "N1", "text": "hello.py takes a --name option", "quotes": "A1", "owner": "children",
         "inversion": {"hello.py takes a --name option": "hello.py takes no --name option"}},
        {"id": "N2", "text": "the README has a Usage section", "quotes": "A2", "owner": "leaves",
         "inversion": {"the README has a Usage section": "the README has no Usage section"}}]}
    NAME_FLAG = {"id": "name-flag", "parent": "greeter", "scope": ["hello.py", "tests/*"], "asks": [
        {"id": "M1", "text": "the --name option greets by the name given", "quotes": "N1", "owner": "leaves",
         "inversion": {"the --name option greets by the name given": "the --name option ignores the name"}}]}
    STEPS = [{"id": "S1", "label": "adds --name and its test", "claims": ["M1", "N2"], "diff": "+--name"},
             {"id": "S2", "label": "adds notes", "claims": [], "diff": "+notes"}]

    def setUp(self):
        os.environ["FRAME_LOOP_WORK"] = str(ROOT / "tests/.work" / f"walk-{uuid.uuid4().hex}")
        os.environ.setdefault("FRAME_LOOP_FRAME0", str(ROOT / "tests/fixtures/frame0.json"))

    def test_walk_routes_each_completion_to_its_own_hole_on_a_three_level_tree(self):
        import hook
        import reader
        import tree
        nodes = {"root": {**self.FRAME0, "id": "root"}, "greeter": self.GREETER, "name-flag": self.NAME_FLAG}
        battery = {**readers.READERS["public"], "reasoning": "low", "output": {"label": "/label"}}
        frames = [tree.node_frame(n, battery) for n in nodes.values()]
        for nid, ask, hole in (("name-flag", "M1", "done-M1"), ("greeter", "N2", "done-N2")):
            frame0 = tree.frame0_for(nodes[nid], self.FRAME0, nodes)
            the_ask = next(a for a in frame0["asks"] if a["id"] == ask)
            start = hook.completion_frame(frame0, the_ask, self.STEPS, "public", in_tree=True)
            walked = reader.walk(start, frames)
            for key in ("fits", "frontier", "deferred", "passed"):
                self.assertIn(key, walked, walked)
            self.assertEqual([(f["frame"], f["holes"]) for f in walked["fits"]], [(f"node-{nid}", [hole])], walked)
            self.assertTrue(all(isinstance(f["hash"], str) for f in walked["fits"]))
            self.assertEqual(walked["frontier"], [])
