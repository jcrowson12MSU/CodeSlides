"""Dedicated verification deck -- NOT a teaching example.

Every time a fix is made in this session, the `last_updated` cell below
gets a new timestamp and (if relevant) a fresh note describing what to
look for. If the timestamp you see in the running app doesn't match
what you were just told to expect, you are looking at STALE content --
the fix hasn't actually reached the server you're running, and you
should re-check `git log --oneline -1` / restart the server rather than
concluding the fix doesn't work.
"""

from codeslides import App, cs, ui

app = App()


@app.cell
def last_updated():
    return cs.md(
        "## Last updated: 2026-08-20 10:01 CDT\n\n"
        "If you don't see this exact timestamp, you're looking at an "
        "old version of this file -- pull again and restart the server.\n\n"
        "**This update fixes:** the whole-column-collapsed \"Drop a tab "
        "here\" strip was missing its right-hand border entirely (a "
        "box-sizing bug -- `width: 100%` plus a `1px` border overflowed "
        "the strip's narrow parent column by 2px, pushing the right "
        "edge outside the visible/clipped area). It now has a complete "
        "border on all four sides."
    )


@app.cell(
    instance="editable",
    elements=[
        ui.slider("volume", min=0, max=10, default=5),
        ui.text_input("label", default="hello"),
        ui.slider("count", min=1, max=20, default=1),
        ui.button("go", label="Go"),
        ui.notes("notes"),
    ],
)
def inputs_merge_check(volume, label, count, go):
    """# Check: merged "Inputs" tab

    Expected: the tab strip should show ONE tab called **Inputs**
    (not three separate tabs for volume/label/count), positioned where
    "volume" used to be. Clicking it should show all three stacked
    vertically, each numbered 1/2/3 in that order. The `go` button
    should be its OWN separate tab, not merged in.

    Also check the Edit panel's element list: volume/label/count should
    each show a matching 1./2./3. next to their name; canvas/notes/go
    should show no number.
    """
    return f"volume={volume} label={label!r} count={count}"


@app.cell(instance="editable")
def output_position_check():
    """# Check: output renders directly below its own code editor

    Expected: the text below (printed by this cell's return value)
    should appear directly under THIS cell's own Code tab content --
    not in a separate block floating above the whole row. Try dragging
    the Code tab to the other column (drag its tab button onto the
    empty "Drop a tab here" strip on the right) and confirm the output
    follows it there.
    """
    return "This text should sit directly under the code editor above it."


@app.cell(hide_def=True)
def hide_def_check():
    x = 1
    y = 2
    return cs.md(
        f"## Check: hide_def checkbox\n\n"
        f"This cell already has `hide_def=True` set (via this file, not "
        f"the UI). Click **Edit** above, and you should see a checkbox "
        f"labeled **Hide function definition**, already checked. The "
        f"code editor for this cell should show just `x = 1` / `y = 2` "
        f"/ etc, with NO `def hide_def_check():` line visible. Try "
        f"unchecking it -- the `def` line should reappear immediately. "
        f"x + y = {x + y}"
    )


@app.cell(
    instance="editable",
    elements=[
        ui.slider("a", min=1, max=5, default=1),
        ui.slider("b", min=1, max=5, default=1),
    ],
)
def empty_column_check(a, b):
    """# Check: empty column / whole-column collapse

    Expected: by default all tabs are on the left, so the right side
    should show a narrow, ROTATED "Drop a tab here" strip running the
    full height of the row (not a short, unrotated box; not cut off
    at the bottom). Drag a tab over to the right and confirm the left
    side correctly expands/contracts to fill the freed or claimed
    space.
    """
    return a + b


@app.cell(instance="editable")
def title_slide():
    return cs.md('# verify_updates\n\n*One-line summary -- edit me.*\n\n## Contents\n\n1. [aaa](#slide-1)\n2. [dddd](#slide-2)')


@app.slide('Title', cells=['title_slide'])
def slide_title():
    """"""


@app.slide('aaa', cells=['inputs_merge_check'])
def slide_aaa():
    """"""


@app.slide('dddd', cells=['output_position_check'])
def slide_dddd():
    """"""
