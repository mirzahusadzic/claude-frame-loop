"""Builds docs/images/frames-{light,dark}.svg: nested frames filled with one request, each span of the
request in its own hue, its rule beside it in the complementary hue, one shade deeper per
level, every shade chosen by contrast against the box it sits in."""

import colorsys
from pathlib import Path


def lum(h):
    r, g, b = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]

    def f(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def cr(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def shade(hue, sat, fill, target, dark):
    """The colour of this hue whose contrast on `fill` is closest above `target`."""
    best = None
    for i in range(1000):
        lightness = i / 1000
        r, g, b = colorsys.hls_to_rgb(hue / 360, lightness, sat)
        c = "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
        k = cr(c, fill)
        if k >= target and ((dark and lum(c) > lum(fill)) or (not dark and lum(c) < lum(fill))):
            if best is None or k < best[1]:
                best = (c, k)
    return best[0]


THEMES = {
    "light": dict(
        dark=False, ink="#1f2328", line="#1f2328", fills=["#ffffff", "#f6f8fa", "#eaeef2", "#dde2e7", "#d0d7de"]
    ),
    "dark": dict(
        dark=True, ink="#e6edf3", line="#c9d1d9", fills=["#0d1117", "#161b22", "#1c2128", "#262c33", "#30363d"]
    ),
}
HUES = {"a": (212, 0.85), "ar": (36, 0.95), "b": (140, 0.7), "br": (320, 0.75)}
# level: 1 request, 2 confirmed, 3 requirement, 4 label, 5 reader; fill index each sits on
LEVEL_FILL = {1: 0, 2: 0, 3: 2, 4: 3, 5: 4}
TARGETS = {1: 4.8, 2: 5.4, 3: 6.0, 4: 6.6, 5: 7.2}


def svg(theme):
    t = THEMES[theme]
    css = ""
    for k, (h, s) in HUES.items():
        for lv in range(1, 6):
            css += f"    .{k}{lv} {{ fill: {shade(h, s, t['fills'][LEVEL_FILL[lv]], TARGETS[lv], t['dark'])}; }}\n"
    f = t["fills"]

    def box(x, y, w, h, fill, r=12):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" class="box" style="fill: {fill}"/>'

    def column(x, k, req, label):
        return f'''
  {box(x, 304, 290, 392, f[2])}
  <text x="{x + 16}" y="338" class="{k}3"><tspan class="b">Requirement</tspan>: {req[0]}</text>
  <text x="{x + 16}" y="362" class="{k}3">{req[1]}</text>
  <text x="{x + 16}" y="386" class="{k}3">{req[2]}</text>
  <text x="{x + 16}" y="410" class="{k}r3">rule: with a test</text>
  {box(x + 16, 426, 258, 254, f[3])}
  <text x="{x + 32}" y="458"><tspan class="b">Workflow</tspan>: Claude, <tspan class="{k}r4">by rule,</tspan></text>
  <text x="{x + 32}" y="482">recompiles; its turn, labelled</text>
  <text x="{x + 32}" y="506" class="i {k}4">{label[0]}</text>
  <text x="{x + 32}" y="530" class="i"><tspan class="{k}4">{label[1]} </tspan><tspan class="{k}r4">with its test”</tspan></text>
  {box(x + 22, 546, 246, 118, f[4], 10)}
  <text x="{x + 38}" y="576"><tspan class="b">Reader</tspan>, given that label:</text>
  <text x="{x + 38}" y="600" class="{k}5">with the requirement: fits</text>
  <text x="{x + 38}" y="624" class="{k}5">without it: doesn’t ✓</text>
  <text x="{x + 38}" y="648" class="{k}r5">breaks no rule ✓</text>'''

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 812" width="960" height="812" role="img" aria-labelledby="t d">
  <title id="t">The frames, filled in with one request</title>
  <desc id="d">You: "Add rate limiting to the API. Over the limit, return HTTP 429." You confirm: each client is limited per minute, with a test; over the limit, HTTP 429 with a retry time, with a test. Method, frame-loop, breaks the requirements down by crossing. Requests counted per client, each count resets after a minute, with a test: Claude, by rule, recompiles, and its turn is labelled "adds a counter that resets each minute, with its test"; the reader, given that label, finds it fits with the requirement and not without it, and that it breaks no rule. The HTTP 429 carries Retry-After, the seconds left in the window, with a test: Claude, by rule, recompiles, and its turn is labelled "sets Retry-After from the window, with its test"; the reader finds the same. Each part of the request keeps its colour down the frames, a shade deeper at each rewording; its rule sits beside it in the complementary colour, in the work as in the check.</desc>
  <style>
    text {{ font-family: "Latin Modern Roman", "CMU Serif", "Computer Modern", "Times New Roman", Georgia, serif; font-size: 19px; fill: {t["ink"]}; }}
    .b {{ font-weight: 700; }}
    .i {{ font-style: italic; }}
{css}    .box {{ stroke: {t["line"]}; stroke-width: 1.3; }}
    .arrow {{ stroke: {t["line"]}; stroke-width: 1.4; fill: none; }}
    .head {{ fill: {t["line"]}; }}
  </style>
  {box(128, 73, 677, 723, f[0], 16)}
  <text x="149" y="108"><tspan class="b">You</tspan>: <tspan class="i">“<tspan class="a1">Add rate limiting to the API.</tspan> <tspan class="b1">Over the limit, return HTTP 429.</tspan>”</tspan></text>
  <text x="149" y="134">you confirm: <tspan class="a2">each client is limited per minute,</tspan> <tspan class="ar2">with a test (rule);</tspan></text>
  <text x="149" y="160"><tspan class="b2">over the limit, HTTP 429 with a retry time,</tspan> <tspan class="br2">with a test (rule)</tspan></text>

  {box(156, 179, 620, 533, f[1], 14)}
  <text x="178" y="215"><tspan class="b">Method</tspan> (frame-loop): your requirements, by crossing</text>
  <text x="660" y="250" text-anchor="end">labels each change ↓</text>
  <text x="660" y="275" text-anchor="end">an act that is yours ↑</text>
  <line x1="682" y1="236" x2="682" y2="298" class="arrow"/>
  <path d="M676 244 L682 232 L688 244 Z" class="head"/>
  <path d="M676 290 L682 302 L688 290 Z" class="head"/>
{column(172, "a", ["requests", "counted per client, each", "count resets after a minute"], ["“adds a counter that resets", "each minute,"])}
{column(470, "b", ["the HTTP 429", "carries Retry-After, the", "seconds left in the window"], ["“sets Retry-After from the", "window,"])}

  <line x1="101" y1="612" x2="101" y2="104" class="arrow"/>
  <path d="M95 112 L101 98 L107 112 Z" class="head"/>
  <text x="93" y="320" text-anchor="end">informs</text>
  <text x="93" y="345" text-anchor="end">only</text>
  <text x="93" y="370" text-anchor="end">through</text>
  <text x="93" y="395" text-anchor="end">a gate</text>

  <line x1="828" y1="98" x2="828" y2="606" class="arrow"/>
  <path d="M822 598 L828 612 L834 598 Z" class="head"/>
  <text x="838" y="320">declares;</text>
  <text x="838" y="345">never</text>
  <text x="838" y="370">rewritten</text>
  <text x="838" y="395">from inside</text>

  <path d="M594 712 C594 738, 586 750, 568 753" class="arrow" stroke-dasharray="6 5"/>
  <path d="M572 747 L558 754 L572 760 Z" class="head"/>
  <text x="545" y="760" text-anchor="end">▲ a mismatch becomes a change You declare</text>
</svg>
"""


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1])
    for theme in THEMES:
        (out / f"frames-{theme}.svg").write_text(svg(theme))
