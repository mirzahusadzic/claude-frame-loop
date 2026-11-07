"""Fake readers for the CLI contract tests: no network, no cost.

Each one reads only the prompt Gadfly gives it, as a real reader does, and answers
deterministically, so the gate's reading of Gadfly's real CLI output can be tested.
"""

import json
import re

from midwife.errors import StopRun
from midwife.types import Observation


def _body(prompt: str) -> str:
    return prompt.split("\n\n---\n\n", 1)[0]


def _answer(label: str) -> Observation:
    return Observation(label=label, raw=json.dumps({"label": label, "name": ""}),
                       usage={"output_tokens": 1}, served="fake")


class Ideal:
    """Answers the frame's first anchor while that anchor's span is in the body with
    its own sense, and none once it is cut or inverted: a reader whose answer rests on
    the declared ask and follows what it says."""

    name = "fake-ideal"
    concurrent = True  # pure answers: safe to call at once

    def trains(self, frame):  # as the unified battery says it: the model under trainsOnInputs
        battery = frame.raw.get("battery") or {}
        return battery.get("model") in (battery.get("trainsOnInputs") or [])

    def check(self, frame):
        pass

    def observe(self, frame, prompt, max_output_tokens):
        anchor = frame.raw["anchors"][0]
        body = _body(prompt)
        present = re.search(rf"^{re.escape(anchor)}: ", body, re.M)
        inverted = any(v in body for v in (frame.raw["interventions"].get("inversion") or {}).values())
        return _answer(anchor if present and not inverted else "none")


class Literal:
    """Answers the first anchor while its id is in the body, whatever its text says: a
    reader that follows the label, not the sense."""

    name = "fake-literal"
    concurrent = True  # pure answers: safe to call at once

    def trains(self, frame):  # as the unified battery says it: the model under trainsOnInputs
        battery = frame.raw.get("battery") or {}
        return battery.get("model") in (battery.get("trainsOnInputs") or [])

    def check(self, frame):
        pass

    def observe(self, frame, prompt, max_output_tokens):
        anchor = frame.raw["anchors"][0]
        present = re.search(rf"^{re.escape(anchor)}: ", _body(prompt), re.M)
        return _answer(anchor if present else "none")


class Stuck:
    """Always answers the first anchor, whatever is cut: a reader whose answer rests
    on nothing in the body."""

    name = "fake-stuck"
    concurrent = True  # pure answers: safe to call at once

    def trains(self, frame):  # as the unified battery says it: the model under trainsOnInputs
        battery = frame.raw.get("battery") or {}
        return battery.get("model") in (battery.get("trainsOnInputs") or [])

    def check(self, frame):
        pass

    def observe(self, frame, prompt, max_output_tokens):
        return _answer(frame.raw["anchors"][0])


class Broken:
    """A harness that has failed: every call raises StopRun."""

    name = "fake-broken"
    concurrent = True  # pure answers: safe to call at once

    def trains(self, frame):  # as the unified battery says it: the model under trainsOnInputs
        battery = frame.raw.get("battery") or {}
        return battery.get("model") in (battery.get("trainsOnInputs") or [])

    def check(self, frame):
        pass

    def observe(self, frame, prompt, max_output_tokens):
        raise StopRun("the fake reader's harness is broken")
