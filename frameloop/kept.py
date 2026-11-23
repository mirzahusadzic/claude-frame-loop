"""The battery Gadfly loads for every reading that holds a page against a kept step: Gadfly's own branch, with the steps
the maker made at the examination standing where the maker would be, as Gadfly's examples/branch/kept_step.py has
it. The reader is the one in the battery's own line: the private pair's or the contributor tier's.

Gadfly's own Python imports this module, from the plugin's root as its working folder:

    gadfly firm <frame> --battery frameloop.kept:Kept ...

So this module alone imports Gadfly's midwife. The steps reach it in the frame file the tool's own call passes to
Gadfly, under the maker's line, and so the frame's hash names them and the reader beside them: no setting a person or
a project can set moves them. Each input has a step of its own, kept under its own question: the claim as worded, and
the claim reversed as the frame's input inversion asks it. That is the branch's own rule, that an input a trial renames
is another input with a step of its own, so the words it changed cannot come back through the first. A question the
line holds no step for is an opening, never another question's step and never a guess.
"""

from __future__ import annotations

from midwife.batteries.branch import Branch
from midwife.batteries.crossing import Made
from midwife.batteries.unified import Unified
from midwife.errors import BatteryError

from frameloop import words

NAME = "kept-step"


class KeptStep:
    """A maker that makes nothing: it gives back the step kept for the question, from its own line."""

    name = NAME
    concurrent = True  # it keeps no state, so calls may run at once

    def trains(self, line: dict) -> bool:
        return False  # it calls nothing

    def check(self, line: dict) -> None:
        steps = line.get("steps")
        sound = (
            set(line) <= {"kind", "steps"}
            and isinstance(steps, dict)
            and steps
            and all(isinstance(q, str) and isinstance(s, str) and q and s for q, s in steps.items())
        )
        if not sound:
            raise BatteryError(words.KEPT_LINE)

    def make(self, line: dict, text: str, max_output_tokens: int) -> Made:
        step = line["steps"].get(text)
        if step is None:
            return Made(None, opening=words.KEPT_NONE, usage={"output_tokens": 0})
        return Made(step, usage={"output_tokens": 0})


class Kept(Branch):
    """`--battery frameloop.kept:Kept`: the branch, the kept step as its maker and the unified reader."""

    def __init__(self) -> None:
        super().__init__(KeptStep(), Unified())
