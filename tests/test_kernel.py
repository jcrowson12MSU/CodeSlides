import pytest

from codeslides import App, cs, ui
from codeslides.kernel import Kernel
from codeslides.session import Session


def _build_deck():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    return app


def test_run_all_executes_in_dependency_order():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.namespace["base"] == 5
    assert session.namespace["result"] == 15
    assert session.instances["setup"].status == "idle"
    assert session.instances["live_demo"].status == "idle"


def test_element_value_change_triggers_minimal_rerun():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_element_changed("live_demo", "speed", 7, session)

    assert session.namespace["result"] == 35
    assert session.instances["live_demo"].elements["speed"].value == 7


def test_editing_upstream_cell_propagates_to_dependents():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_cell_edited("setup", "def setup():\n    base = 100\n    return base\n", session)

    assert session.namespace["base"] == 100
    assert session.namespace["result"] == 300  # base(100) * speed(default 3)


def test_exception_is_captured_without_crashing_kernel():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_cell_edited("setup", "def setup():\n    base = 1 / 0\n    return base\n", session)

    assert session.instances["setup"].status == "error"
    assert "ZeroDivisionError" in session.instances["setup"].error
    # the kernel itself must still be usable after a cell error
    kernel.on_cell_edited("setup", "def setup():\n    base = 9\n    return base\n", session)
    assert session.namespace["base"] == 9
    assert session.instances["setup"].status == "idle"


def test_viewer_elements_are_not_passed_as_kwargs():
    app = App()

    @app.cell(
        elements=[
            ui.turtle_canvas("canvas"),
            ui.notes("notes"),
        ]
    )
    def draw():
        picture = "a square"
        return picture

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["draw"].status == "idle", session.instances["draw"].error
    assert session.namespace["picture"] == "a square"


def test_a_cell_local_import_turtle_is_a_no_op_and_the_framework_turtle_still_works():
    """A real `import turtle` executing for real would rebind the name to
    the actual stdlib module (which the browser's turtle canvas can't
    see at all, and which crashes outright on a machine without tkinter
    -- reproduced by hand). It must be a silent no-op: codeslides.turtle
    stays bound, and turtle.forward(...) still records a real command."""
    app = App()

    @app.cell(elements=[ui.turtle_canvas("canvas")])
    def draw():
        import turtle

        turtle.forward(50)
        result = 1
        return result

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["draw"].status == "idle", session.instances["draw"].error
    commands = session.instances["draw"].elements["canvas"].content
    assert commands == [
        {"op": "goto", "x": 50.0, "y": 0.0, "pen_down": True, "color": "black", "width": 1.0}
    ]


def test_import_turtle_as_something_else_is_not_treated_as_a_no_op():
    """Deliberately narrow: only a bare `import turtle` is a no-op. `import
    turtle as t` is a real import under a different name that the
    framework's own turtle has no reason to intercept -- it isn't the
    name every cell's globals already provide `codeslides.turtle` under,
    so there's nothing to protect it from shadowing."""
    import ast

    from codeslides.kernel import strip_noop_turtle_imports

    tree = ast.parse("import turtle as t\n")
    assert strip_noop_turtle_imports(tree.body) == tree.body


def test_multi_value_return_unpacks_by_name():
    app = App()

    @app.cell
    def pair():
        a = 1
        b = 2
        return a, b

    @app.cell
    def total():
        c = a + b  # noqa: F821
        return c

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.namespace["a"] == 1
    assert session.namespace["b"] == 2
    assert session.namespace["c"] == 3


def test_ordinary_local_reads_before_assignment_raise_unboundlocalerror():
    """A plain local (no `global` declaration) that's read before its
    own assignment must behave exactly like real Python: the whole
    function treats it as local from the first assignment onward, so
    reading it earlier is an UnboundLocalError, not a silent read of
    some outer/previous value. Regression guard for
    examples/marchingSquares.py's cell_1, which does exactly this on
    purpose to document the expected failure."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(name="cell_1", source="def cell_1():\n    print(x)\n    x = 5\n    print(x)\n")
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    session.namespace["x"] = 4
    kernel.run_all(session)

    assert session.instances["cell_1"].status == "error"
    assert "UnboundLocalError" in session.instances["cell_1"].error
    assert session.namespace["x"] == 4  # untouched -- the cell never got past its own error


def test_global_declared_write_mutates_and_syncs_back_to_the_namespace():
    """A cell that declares `global x` and mutates it must have that
    mutation actually reach session.namespace directly -- the cell's
    real __globals__ is session.namespace itself, not a copy. Regression
    guard for examples/marchingSquares.py's cell_2."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(
            name="cell_2",
            source="def cell_2():\n    global x\n    x += 5\n",
        )
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    session.namespace["x"] = 4
    kernel.run_all(session)

    assert session.instances["cell_2"].status == "idle"
    assert session.namespace["x"] == 9


def test_default_argument_values_still_evaluate_correctly():
    """Regression guard for _compile_cell_function's two-step compile
    (exec into a scratch copy just to evaluate defaults, then rebuild
    the function with session.namespace as its real __globals__):
    default argument values must still work exactly as before, since
    they're computed by exec's own bytecode as a side effect of
    defining the function -- a naive "build the function object by
    hand" approach would silently drop them."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(name="with_defaults", source="def with_defaults(rows=2, cols=5):\n    return rows, cols\n")
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["with_defaults"].status == "idle"
    assert session.instances["with_defaults"].output["value"] == [2, 5]


def test_a_cells_own_function_is_never_bound_under_its_literal_def_name_on_a_failed_call():
    """A renamed instance="editable" cell's literal `def` name can
    differ from its Deck key (cell.name) -- _compile_cell_function's
    scratch-copy step must never leak that literal def-name into
    session.namespace as a side effect, even on a call that later
    fails, or a stale/wrongly-named callable would appear there."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(name="cell_a", source="def renamed_def():\n    raise ValueError('boom')\n")
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["cell_a"].status == "error"
    assert "renamed_def" not in session.namespace
    assert "cell_a" not in session.namespace  # only bound after a successful call


def test_is_main_cell_gets_a_real_dunder_main_guard():
    """A cell tagged is_main whose body has `if __name__ == "__main__":`
    must see that guard actually fire -- otherwise the block is
    permanently dead code (real Python: __name__ is never "__main__"
    for a plain function's own namespace unless something sets it)."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(
            name="entry",
            source='def entry():\n    if __name__ == "__main__":\n        print("ran")\n',
            is_main=True,
        )
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["entry"].status == "idle"
    assert session.instances["entry"].output["stdout"] == "ran\n"


def test_a_cell_with_a_main_guard_in_its_own_source_gets_treated_as_main_too():
    """Even without the is_main checkbox, a cell whose own source
    contains `if __name__ == "__main__":` should have that block fire
    -- the pattern itself is a strong enough signal of intent (per the
    user's own explicit request), not just the is_main tag."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(
            name="untagged",
            source='def untagged():\n    if __name__ == "__main__":\n        print("fired")\n',
            is_main=False,
        )
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["untagged"].output["stdout"] == "fired\n"


def test_dunder_name_never_leaks_into_the_shared_namespace():
    """__name__ == "__main__" must be true only while the main cell
    itself is running -- never left behind in session.namespace
    afterward, where an unrelated cell's own (hypothetical) `if
    __name__ == "__main__":` would otherwise spuriously fire."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(name="entry", source='def entry():\n    pass\n', is_main=True)
    )
    deck.add_cell(Cell(name="other", source="def other():\n    pass\n"))

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert "__name__" not in session.namespace


def test_input_reads_a_single_text_input_element():
    """Plain `input("prompt")` -- the exact syntax the chapter1 lecture
    deck's own notes samples teach -- reads a ui.text_input element's
    current value instead of hanging on real stdin (which doesn't exist
    here)."""
    app = App()

    @app.cell(elements=[ui.text_input("name", default="Ada")])
    def greet():
        name = input("What is your name? ")
        message = "Hello, " + name
        return message

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["greet"].status == "idle", session.instances["greet"].error
    assert session.namespace["message"] == "Hello, Ada"


def test_input_reads_multiple_text_inputs_in_declaration_order():
    """Two ui.text_input elements, two input() calls -- each call reads
    the next one in the order they're declared in elements=[...], not
    the order input() happens to be called relative to anything else."""
    app = App()

    @app.cell(
        elements=[
            ui.text_input("first_text", default="4"),
            ui.text_input("second_text", default="9"),
        ]
    )
    def add_two():
        first = int(input("First number: "))
        second = int(input("Second number: "))
        total = first + second
        return total

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["add_two"].status == "idle", session.instances["add_two"].error
    assert session.namespace["total"] == 13


def test_input_reflects_a_live_edited_text_input_value():
    """Changing a text_input's value (the same on_element_changed path a
    real textbox edit in the browser goes through) and re-running the
    cell picks up the new value on the next input() call -- confirming
    the shim reads the element's *current* value each run, not a value
    captured once at cell-definition time."""
    app = App()

    @app.cell(elements=[ui.text_input("age_text", default="15")])
    def parse_age():
        age = int(input("Age: "))
        return age

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.namespace["age"] == 15

    kernel.on_element_changed("parse_age", "age_text", "42", session)
    assert session.namespace["age"] == 42
    assert session.instances["parse_age"].status == "idle"


def test_input_raises_a_clear_error_when_called_more_times_than_there_are_text_inputs():
    """Calling input() a second time with only one ui.text_input element
    declared should fail clearly -- not hang, not silently return an
    empty string, not raise a bare unexplained EOFError."""
    app = App()

    @app.cell(elements=[ui.text_input("age_text", default="15")])
    def parse_two():
        first = input("First: ")
        second = input("Second: ")  # no second text_input declared
        return first, second

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["parse_two"].status == "error"
    assert "only has 1 ui.text_input" in session.instances["parse_two"].error


def test_input_shim_never_leaks_into_a_cell_with_no_text_inputs():
    """Same "never leaks into the shared namespace" guarantee
    __name__/is_main already has (see
    test_dunder_name_never_leaks_into_the_shared_namespace above) --
    input() must behave as the real builtin (raise, not silently
    succeed with someone else's cached value) for a cell that never
    declared any ui.text_input of its own, even after a different cell
    with one has already run in the same Session."""
    app = App()

    @app.cell(elements=[ui.text_input("name", default="Ada")])
    def with_input():
        who = input("Name: ")
        return who

    @app.cell
    def without_input():
        # No ui.text_input declared on this cell at all -- input() here
        # must behave like the real builtin (fail, since there's no
        # stdin), never silently reuse with_input's own text_input.
        try:
            input("should not work here")
            called_ok = True
        except (EOFError, OSError):
            called_ok = False
        return called_ok

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["with_input"].status == "idle", session.instances["with_input"].error
    assert session.namespace["who"] == "Ada"
    assert session.instances["without_input"].status == "idle", session.instances["without_input"].error
    assert session.namespace["called_ok"] is False


def test_input_also_works_inside_a_tests_element():
    """`ui.tests` boxes run as ordinary Python against the owning cell's
    own namespace (run_tests's own docstring) -- input() should be just
    as readable there as inside the cell's own body, reading from the
    same cell's text_input elements."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(
            name="greet",
            source=(
                "def greet():\n"
                "    name = input('Name: ')\n"
                "    return name\n"
            ),
            elements=[ui.text_input("name", default="Ada"), ui.tests("unit", default="assert input('Name: ') == 'Ada'")],
        )
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["greet"].status == "idle", session.instances["greet"].error
    result = kernel.on_tests_edited("greet", "unit", "assert input('Name: ') == 'Ada'", session)
    assert result["status"] == "pass", result["message"]


def test_input_reads_a_slider_element():
    """input() can pull a value from a ui.slider, not just a
    ui.text_input -- returned as a str, matching input()'s own real
    contract, even though a slider's underlying value is a float."""
    app = App()

    @app.cell(elements=[ui.slider("speed", min=1, max=10, default=3)])
    def show_speed():
        speed_text = input("Speed: ")
        return speed_text

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["show_speed"].status == "idle", session.instances["show_speed"].error
    assert session.namespace["speed_text"] == "3"
    assert isinstance(session.namespace["speed_text"], str)


def test_input_from_a_slider_formats_a_whole_number_without_a_trailing_dot_zero():
    """A slider's value is a JS Number -> Python float even when it's a
    whole number (SliderWidget.tsx's own onChange(Number(...))) --
    str(3.0) is "3.0", and int("3.0") raises ValueError (unlike
    int(3.0), which works fine) -- exactly the kind of thing
    `int(input(...))` around a slider-backed prompt would hit. Confirm
    a whole-number slider value renders without the decimal, so
    int(input(...)) still works the same way it would for a typed
    whole number."""
    app = App()

    @app.cell(elements=[ui.slider("age", min=1, max=100, default=15)])
    def parse_slider_age():
        age = int(input("Age: "))
        return age

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["parse_slider_age"].status == "idle", session.instances["parse_slider_age"].error
    assert session.namespace["age"] == 15


def test_input_from_a_slider_keeps_a_fractional_value_intact():
    """A genuinely fractional slider value (not a whole number) must
    still come through with its decimal part -- the whole-number
    special case above must not truncate a real fraction."""
    app = App()

    @app.cell(elements=[ui.slider("rate", min=0, max=50, default=12.5)])
    def parse_slider_rate():
        rate = float(input("Rate: "))
        return rate

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["parse_slider_rate"].status == "idle", session.instances["parse_slider_rate"].error
    assert session.namespace["rate"] == 12.5


def test_input_reads_a_mix_of_sliders_and_text_inputs_in_declaration_order():
    """Sliders and text_inputs share ONE combined input() sequence, in
    the order they're declared in elements=[...] -- not "drain all
    text_inputs, then all sliders" or vice versa."""
    app = App()

    @app.cell(
        elements=[
            ui.slider("hours", min=1, max=40, default=20),
            ui.text_input("name", default="Sam"),
            ui.slider("rate", min=1, max=100, default=12.5),
        ]
    )
    def pay():
        hours = float(input("Hours: "))
        name = input("Name: ")
        rate = float(input("Rate: "))
        return hours, name, rate

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["pay"].status == "idle", session.instances["pay"].error
    assert session.namespace["hours"] == 20.0
    assert session.namespace["name"] == "Sam"
    assert session.namespace["rate"] == 12.5


def test_input_still_ignores_button_elements():
    """ui.button is deliberately still not readable via input() -- a
    click count isn't text a student would type at a prompt. A cell
    with only a button and no text_input/slider should still get the
    clear "no readable elements" error, not silently read the button's
    click count."""
    app = App()

    @app.cell(elements=[ui.button("go")])
    def only_a_button():
        return input("value: ")

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["only_a_button"].status == "error"
    assert "only has 0 ui.text_input/ui.slider" in session.instances["only_a_button"].error


def test_two_cells_with_unrelated_same_named_locals_both_load_and_run():
    """Regression guard for the exact examples/marchingSquares.py bug
    report: a cell with a `for x in range(...)` loop and an unrelated
    cell with a plain local `x` used to fail to even load the deck
    (MultipleDefinitionError), even though in real Python two such
    functions never interact."""
    app = App()

    @app.cell
    def loop_cell():
        total = 0
        for x in range(3):
            total += x
        return total

    @app.cell
    def other_cell():
        x = "unrelated"
        return x

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["loop_cell"].status == "idle"
    assert session.instances["other_cell"].status == "idle"
    assert session.namespace["total"] == 3
    assert session.namespace["x"] == "unrelated"


def test_return_of_a_computed_expression_runs_fine_with_no_extra_namespace_binding():
    """A `return`ed computed expression (not a bare name/tuple-of-names)
    is not an error -- there's simply no existing name to publish it
    under, so it's treated like a bare `return` with no value: nothing
    extra is bound into session.namespace. The cell's own displayed
    output still carries the real computed value regardless."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(Cell(name="ok", source="def ok():\n    x = 1\n    return x + 1\n"))

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["ok"].status == "idle"
    assert session.instances["ok"].output["value"] == 2
    assert "x" not in session.namespace


def test_return_of_a_computed_tuple_expression_is_still_directly_callable_by_another_cell():
    """The exact shape from the user's own report: a `midpoint`-style
    helper cell returns a computed tuple with no intermediate named
    variables to expose. It publishes no implicit graph-level name, but
    another cell can still call it directly and get the real value --
    same as any two ordinary Python functions.

    `midpoint` needs its own `tests` element (empty default is fine) so
    it's only ever *defined*, not auto-called with no arguments
    (TODO.md #43/`_run_cells`) -- `p1`/`p2` have no defaults, so an
    auto-call would fail before `result` ever got a chance to call it
    itself with real arguments."""
    from codeslides.deck import Cell, Deck

    deck = Deck()
    deck.add_cell(
        Cell(
            name="midpoint",
            source=(
                "def midpoint(p1, p2):\n"
                "    x1, y1 = p1\n"
                "    x2, y2 = p2\n"
                "    return (x1 + x2) / 2, (y1 + y2) / 2\n"
            ),
            elements=[ui.tests("unit")],
        )
    )
    deck.add_cell(
        Cell(
            name="result",
            source="def result():\n    mx, my = midpoint((2, 6), (10, 8))\n    return mx, my\n",
        )
    )

    kernel = Kernel(deck)
    session = Session(deck=deck)
    kernel.run_all(session)

    assert session.instances["midpoint"].status == "idle"
    assert session.instances["result"].status == "idle"
    assert session.namespace["mx"] == 6
    assert session.namespace["my"] == 7


def test_clone_isolation_holds_under_real_execution():
    """Regression test for the marimo cloned-editor bug described in
    VISION.md: cloning a Session and editing one clone's cell source (or
    an element's value) must never affect the other clone, or the shared
    Deck/Kernel baseline."""
    app = _build_deck()
    kernel = Kernel(app.deck)

    session_a = Session(deck=app.deck)
    kernel.run_all(session_a)
    session_b = session_a.clone()

    kernel.on_element_changed("live_demo", "speed", 999, session_b)
    assert session_a.namespace["result"] == 15
    assert session_b.namespace["result"] == 4995

    kernel.on_cell_edited(
        "live_demo",
        "def live_demo(speed):\n    result = base + speed\n    return result\n",
        session_b,
    )
    assert session_b.namespace["result"] == 1004

    # session_a must still use the ORIGINAL multiply logic
    kernel.on_element_changed("live_demo", "speed", 10, session_a)
    assert session_a.namespace["result"] == 50

    # the shared Deck/Kernel baseline must be untouched by session_b's edit
    assert "live_demo" not in session_a.source_overrides
    assert "result = base * speed" in kernel.deck.cells["live_demo"].source


def _build_viewer_deck():
    app = App()

    @app.cell(elements=[ui.image("plot")])
    def make_plot():
        cs.image("plot", "/tmp/figure.png")
        x = 1
        return x

    return app


def test_cs_image_writes_element_content():
    app = _build_viewer_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    results = kernel.run_all(session)

    assert session.instances["make_plot"].status == "idle"
    assert session.instances["make_plot"].elements["plot"].content == ["/tmp/figure.png"]
    assert results["make_plot"].element_writes == [
        cs.ElementWrite(element_name="plot", kind="image", content=["/tmp/figure.png"])
    ]


def test_cs_write_to_unknown_element_is_a_cell_error():
    app = App()

    @app.cell(elements=[ui.image("plot")])
    def bad_target():
        cs.image("does_not_exist", "/tmp/figure.png")
        x = 1
        return x

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["bad_target"].status == "error"
    assert "does_not_exist" in session.instances["bad_target"].error
    # nothing partially applied on error
    assert session.instances["bad_target"].elements["plot"].content is None


def test_cs_write_is_not_applied_when_a_later_write_in_the_same_cell_fails():
    app = App()

    @app.cell(elements=[ui.image("a"), ui.image("b")])
    def two_targets():
        cs.image("a", "1.png")
        cs.image("does_not_exist", "2.png")
        x = 1
        return x

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["two_targets"].status == "error"
    # the earlier, valid write must not have been applied either --
    # all-or-nothing, matching namespace write semantics
    assert session.instances["two_targets"].elements["a"].content is None


def test_notes_element_content_seeded_from_docstring():
    app = App()

    @app.cell(elements=[ui.notes("n")])
    def cell_with_notes():
        """# Title\nBody"""
        x = 1
        return x

    session = Session(deck=app.deck)
    assert session.instances["cell_with_notes"].elements["n"].content == "# Title\nBody"


_NOTES_DECK_SOURCE = (
    "from codeslides import App, ui\n\n"
    "app = App()\n\n"
    '@app.cell(elements=[ui.notes("n")])\n'
    "def cell_with_notes():\n"
    "    base = 5\n"
    "    return base\n"
)


def test_on_notes_edited_updates_content_immediately(tmp_path):
    path = _write_deck_file(tmp_path, _NOTES_DECK_SOURCE)
    from codeslides.loader import load_deck

    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    kernel.on_notes_edited("cell_with_notes", "n", "edited notes", session)

    assert session.instances["cell_with_notes"].elements["n"].content == "edited notes"
    # pure UI state -- no re-run, no ExecutionResults, matching
    # on_notes_edited's `-> None` (unlike on_cell_edited/on_element_changed)
    assert session.namespace == {}


def test_on_notes_edited_folds_the_edit_into_source_overrides_and_it_saves(tmp_path):
    path = _write_deck_file(tmp_path, _NOTES_DECK_SOURCE)
    from codeslides.loader import load_deck
    from codeslides.serialization import display_docstring, save_edits

    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    kernel.on_notes_edited("cell_with_notes", "n", "new notes", session)

    assert "cell_with_notes" in session.source_overrides
    assert display_docstring(session.source_overrides["cell_with_notes"]) == "new notes"
    # the code body is untouched by a notes-only edit
    assert "base = 5" in session.source_overrides["cell_with_notes"]

    save_edits(str(path), session.source_overrides)
    reloaded = load_deck(str(path))
    assert reloaded.cells["cell_with_notes"].docstring == "new notes"


def test_on_notes_edited_skips_source_overrides_if_the_cells_code_is_unparseable(tmp_path):
    path = _write_deck_file(tmp_path, _NOTES_DECK_SOURCE)
    from codeslides.loader import load_deck

    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    # simulate mid-keystroke invalid code sitting in this cell's own
    # override, from a concurrent code edit in the same session
    session.source_overrides["cell_with_notes"] = "def cell_with_notes(:\n    base = 5\n"

    kernel.on_notes_edited("cell_with_notes", "n", "new notes", session)

    # the in-memory content still updates (the notes viewer keeps showing
    # what was typed)...
    assert session.instances["cell_with_notes"].elements["n"].content == "new notes"
    # ...but the unparseable override is left alone rather than crashing
    # or silently discarding the pending (invalid) code edit
    assert session.source_overrides["cell_with_notes"] == "def cell_with_notes(:\n    base = 5\n"


_NOTES_DECK_WITH_DOCSTRING_SOURCE = (
    "from codeslides import App, ui\n\n"
    "app = App()\n\n"
    '@app.cell(elements=[ui.notes("n")])\n'
    "def cell_with_notes():\n"
    '    "Some notes."\n'
    "    base = 5\n"
    "    return base\n"
)


def test_on_cell_edited_preserves_the_docstring_across_a_code_only_edit(tmp_path):
    """A plain code edit only ever sends display_source's output (no
    decorator, no docstring) -- on_cell_edited must reattach both,
    exactly the same round trip the real edit_cell websocket handler
    relies on, or a code-only edit would silently delete the cell's
    notes just because the editor never showed that line."""
    path = _write_deck_file(tmp_path, _NOTES_DECK_WITH_DOCSTRING_SOURCE)
    from codeslides.loader import load_deck
    from codeslides.serialization import display_docstring, display_source, save_edits

    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    edited = display_source(deck.cells["cell_with_notes"].source).replace("base = 5", "base = 6")
    kernel.on_cell_edited("cell_with_notes", edited, session)

    assert display_docstring(session.source_overrides["cell_with_notes"]) == "Some notes."
    assert "base = 6" in session.source_overrides["cell_with_notes"]

    save_edits(str(path), session.source_overrides)
    reloaded = load_deck(str(path))
    assert reloaded.cells["cell_with_notes"].docstring == "Some notes."


def test_element_writes_isolated_across_cloned_sessions():
    app = _build_viewer_deck()
    kernel = Kernel(app.deck)

    session_a = Session(deck=app.deck)
    kernel.run_all(session_a)
    session_b = session_a.clone()

    # mutate b's element content directly (simulating a later write) and
    # confirm a is untouched -- same isolation guarantee as namespace/value
    session_b.instances["make_plot"].elements["plot"].content = ["/tmp/different.png"]

    assert session_a.instances["make_plot"].elements["plot"].content == ["/tmp/figure.png"]
    assert session_b.instances["make_plot"].elements["plot"].content == ["/tmp/different.png"]


def test_reload_deck_affects_new_sessions():
    """CLI file-watcher reload (TODO.md #10): a new Session created after
    reload_deck() must run against the new deck's code, not the original."""
    app = _build_deck()
    kernel = Kernel(app.deck)

    new_app = App()

    @new_app.cell
    def setup():
        base = 100
        return base

    @new_app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    kernel.reload_deck(new_app.deck)

    session = Session(deck=new_app.deck)
    kernel.run_all(session)

    assert session.namespace["base"] == 100
    assert session.namespace["result"] == 300


def test_reload_deck_does_not_disturb_an_existing_sessions_namespace():
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.namespace["result"] == 15

    new_app = App()

    @new_app.cell
    def setup():
        base = 999
        return base

    @new_app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    kernel.reload_deck(new_app.deck)

    # the existing session's namespace is untouched until it next runs
    assert session.namespace["result"] == 15

    # but running it again now picks up the reloaded baseline
    kernel.run_all(session)
    assert session.namespace["base"] == 999
    assert session.namespace["result"] == 2997


def test_on_cell_edited_with_a_syntax_error_reports_a_cell_error_not_a_crash():
    """An instructor live-typing code passes through invalid intermediate
    syntax constantly (e.g. an unclosed paren mid-edit) -- this must
    surface as this cell's own error, not raise out of on_cell_edited and
    take down the caller (the websocket handler has no try/except around
    this call; previously an uncaught SyntaxError here crashed the whole
    connection)."""
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    results = kernel.on_cell_edited("live_demo", "def live_demo(speed):\n    result = (\n", session)

    assert results["live_demo"].status == "error"
    # `source` is the browser's decorator-free display shape -- on_cell_edited
    # reattaches live_demo's existing decorator before recording the override,
    # so a later save_deck doesn't silently drop it from the file.
    assert session.source_overrides["live_demo"] == (
        '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        "def live_demo(speed):\n    result = (\n"
    )
    # other cells/namespace are untouched
    assert session.namespace["base"] == 5


def test_on_element_changed_tolerates_an_unrelated_cells_broken_override():
    """A different cell in the same Session may currently have an invalid
    (mid-edit) source override sitting around -- changing some other
    element's value rebuilds the *whole* effective graph and must not
    crash just because of that unrelated broken cell."""
    app = _build_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    kernel.on_cell_edited("live_demo", "def live_demo(speed):\n    result = (\n", session)
    assert session.source_overrides["live_demo"] == (
        '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        "def live_demo(speed):\n    result = (\n"
    )

    results = kernel.on_element_changed("live_demo", "speed", 7, session)

    assert results["live_demo"].status == "error"


def _build_cross_cell_call_deck():
    """`drawSquares` calls `drawSquare` directly, same as any two plain
    Python functions in one module -- the use case examples/live_demo1.py
    hit when a user wanted one cell to call another's function.

    `step` has a default so `drawSquare` can also still run standalone as
    its own cell (e.g. bound to a slider via `run_all`), same as the real
    example: a cell meant to be both directly runnable *and* callable from
    another cell needs its parameters to work either way -- called with an
    explicit argument, or falling back to its default when run alone.
    """
    app = App()

    @app.cell
    def drawSquare(step=1):
        result = step * 2
        return result

    @app.cell
    def drawSquares():
        results = [drawSquare(step) for step in (1, 2, 3)]
        return results

    return app


def test_a_cell_can_call_another_cells_function_directly():
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    kernel.run_all(session)

    assert session.namespace["results"] == [2, 4, 6]
    # the callee's own function object is bound into the namespace under
    # its cell name, exactly like any other cell's return-named values
    assert callable(session.namespace["drawSquare"])
    assert session.instances["drawSquare"].status == "idle"
    assert session.instances["drawSquares"].status == "idle"


def test_a_cells_own_name_is_a_graph_write_creating_a_real_dependency_edge():
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)

    assert kernel.graph.topological_order() == ["drawSquare", "drawSquares"]
    assert kernel.graph.affected_by("drawSquare") == ["drawSquare", "drawSquares"]
    assert app.deck.cells["drawSquare"].writes == frozenset({"drawSquare", "result"})
    assert "drawSquare" in app.deck.cells["drawSquares"].reads


def test_editing_the_called_cell_reruns_the_caller_too():
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    assert session.namespace["results"] == [2, 4, 6]

    results = kernel.on_cell_edited(
        "drawSquare",
        "def drawSquare(step=1):\n    result = step * 10\n    return result\n",
        session,
    )

    assert set(results) == {"drawSquare", "drawSquares"}
    assert session.namespace["results"] == [10, 20, 30]


def test_a_callee_cells_failed_run_does_not_update_its_bound_callable():
    """Same all-or-nothing guarantee that already applies to return-named
    values (a failed cell never partially updates the namespace) must also
    hold for the cell's own callable binding: if `drawSquare` fails to run
    standalone (e.g. an edit makes its own body raise), `session.namespace
    ["drawSquare"]` must keep the last *successful* version rather than
    being cleared or left half-updated -- otherwise a caller like
    `drawSquares` would see a stale-but-consistent function, or worse, no
    function at all."""
    app = _build_cross_cell_call_deck()
    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)
    original_fn = session.namespace["drawSquare"]

    # `step` keeps its default (still auto-called standalone), but the
    # body now raises at call time -- a genuine runtime failure, not
    # just an unbound-required-parameter case that would otherwise be
    # safely define-only'd instead of erroring.
    results = kernel.on_cell_edited(
        "drawSquare", "def drawSquare(step=1):\n    result = 1 / 0\n    return result\n", session
    )

    assert results["drawSquare"].status == "error"
    # the stale-but-working callable is still there, untouched
    assert session.namespace["drawSquare"] is original_fn
    assert session.namespace["results"] == [2, 4, 6]


def test_a_cell_with_no_default_parameters_and_no_tests_element_is_never_auto_called():
    """The user's own request: `def drawLineSegment(t, p1, p2, p3, p4):`
    (no defaults on any parameter, no ui.tests(...) element either)
    should not have to fake `=None` defaults or add a tests element it
    doesn't want, purely to avoid a guaranteed TypeError -- it's safely
    defined-but-not-called instead, exactly like a tested cell already
    was (TODO.md #43), and remains directly callable by another cell."""
    app = App()

    @app.cell(elements=[ui.turtle_canvas("Canvas")])
    def drawLineSegment(t, p1, p2, p3, p4):
        t.goto(p1[0], p1[1])
        t.goto(p4[0], p4[1])

    @app.cell(elements=[ui.turtle_canvas("Canvas2")])
    def caller():
        import codeslides.turtle as turtle_module

        t = turtle_module.Turtle()
        drawLineSegment(t, (0, 0), (1, 1), (2, 2), (3, 3))
        done = True
        return done

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    # never auto-called with missing arguments -- defined, not errored
    assert session.instances["drawLineSegment"].status == "idle"
    assert callable(session.namespace["drawLineSegment"])
    # and genuinely usable by another cell's real call
    assert session.instances["caller"].status == "idle"
    assert session.namespace["done"] is True


def test_a_required_parameter_bound_by_a_matching_element_is_still_auto_called():
    """The other half of the same check: a required (no-default)
    parameter that *is* bound by a matching input element (the ordinary
    slider/button case) must still be auto-called normally -- only a
    parameter with genuinely nothing to supply it should be treated as
    unsafe to call."""
    app = App()

    @app.cell(elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = speed * 2
        return result

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)
    kernel.run_all(session)

    assert session.instances["live_demo"].status == "idle"
    assert session.namespace["result"] == 6


def _write_deck_file(tmp_path, source):
    path = tmp_path / "deck.py"
    path.write_text(source)
    return path


_ADD_CELL_DECK_SOURCE = (
    "from codeslides import App\n\napp = App()\n\n@app.cell\ndef setup():\n    base = 5\n    return base\n"
)


def test_add_cell_appends_a_blank_editable_cell_to_disk(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, result = kernel.add_cell(session)

    assert cell.name == "cell_1"
    assert cell.instance == "editable"
    assert result.status == "idle"
    assert "def cell_1():" in path.read_text()
    # the Kernel's own baseline picked up the new cell too, not just the file
    assert "cell_1" in kernel.deck.cells


def test_add_cell_backfills_the_requesting_sessions_instances(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, _ = kernel.add_cell(session)

    # without backfilling, the very next run_all would KeyError on
    # session.instances["cell_1"] -- confirm it doesn't
    assert cell.name in session.instances
    kernel.run_all(session)  # must not raise


def test_add_cell_twice_picks_different_names(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell1, _ = kernel.add_cell(session)
    cell2, _ = kernel.add_cell(session)

    assert cell1.name != cell2.name
    assert {cell1.name, cell2.name} == {"cell_1", "cell_2"}


def test_add_cell_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.add_cell(session)


def test_add_cell_does_not_affect_a_different_sessions_instances(tmp_path):
    """Confirms the agreed scope: adding a cell only guarantees correctness
    for the requesting Session (and any new connection after this) -- an
    unrelated, already-open Session is untouched, matching reload_deck's
    existing, deliberately narrow scope."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session_a = Session(deck=deck)
    session_b = Session(deck=deck)
    kernel.run_all(session_a)
    kernel.run_all(session_b)

    cell, _ = kernel.add_cell(session_a)

    assert cell.name in session_a.instances
    assert cell.name not in session_b.instances


_RENAME_DECK_SOURCE = (
    "from codeslides import App, ui\n\n"
    "app = App()\n\n"
    '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
    "def live_demo(speed):\n"
    "    result = speed * 2\n"
    "    return result\n\n"
    '@app.slide("Live Coding", cells=["live_demo"])\n'
    "def slide_1():\n"
    '    """Notes."""\n'
)


def test_rename_cell_updates_the_kernel_baseline_and_disk(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell = kernel.rename_cell(session, "live_demo", "coding_demo")

    assert cell.name == "coding_demo"
    assert "coding_demo" in kernel.deck.cells
    assert "live_demo" not in kernel.deck.cells
    assert "def coding_demo(speed):" in path.read_text()
    assert kernel.deck.slides[0].cell_names == ["coding_demo"]


def test_set_main_cell_updates_the_kernel_baseline_and_disk(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell = kernel.set_main_cell(session, "live_demo")

    assert cell.is_main is True
    assert kernel.deck.cells["live_demo"].is_main is True
    assert "is_main=True" in path.read_text()


_TWO_CELL_DECK_SOURCE = (
    "from codeslides import App, ui\n\n"
    "app = App()\n\n"
    "@app.cell\n"
    "def setup():\n"
    "    base = 5\n"
    "    return base\n\n"
    '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
    "def live_demo(speed):\n"
    "    result = base * speed\n"
    "    return result\n"
)


def test_set_main_cell_moves_the_designation_between_cells(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _TWO_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.set_main_cell(session, "setup")
    kernel.set_main_cell(session, "live_demo")

    assert kernel.deck.cells["live_demo"].is_main is True
    assert kernel.deck.cells["setup"].is_main is False


def test_set_main_cell_without_a_deck_path_raises():
    app = App()

    @app.cell
    def one():
        pass

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="not started from a deck file"):
        kernel.set_main_cell(session, "one")


def test_set_hide_code_updates_the_kernel_baseline_and_disk(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell = kernel.set_hide_code(session, "live_demo", True)

    assert cell.hide_code is True
    assert kernel.deck.cells["live_demo"].hide_code is True
    assert "hide_code=True" in path.read_text()


def test_set_hide_code_does_not_affect_other_cells(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _TWO_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.set_hide_code(session, "setup", True)
    kernel.set_hide_code(session, "live_demo", True)

    assert kernel.deck.cells["setup"].hide_code is True
    assert kernel.deck.cells["live_demo"].hide_code is True


def test_set_hide_code_without_a_deck_path_raises():
    app = App()

    @app.cell
    def one():
        pass

    kernel = Kernel(app.deck)
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="not started from a deck file"):
        kernel.set_hide_code(session, "one", True)


def test_rename_cell_remaps_the_requesting_sessions_state(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.rename_cell(session, "live_demo", "coding_demo")

    assert "coding_demo" in session.instances
    assert "live_demo" not in session.instances
    # the next run_all must not KeyError on the renamed cell
    kernel.run_all(session)


def test_rename_cell_updates_the_def_line_inside_a_pending_source_override(tmp_path):
    """Regression test: renaming a cell with an unsaved code edit sitting
    in session.source_overrides must not just move the dict key -- the
    override's own `def old_name(...)` text must become `def
    new_name(...)` too, or a later Save would splice the stale text back
    onto the file and silently undo the rename (reported as "renaming a
    cell doesn't work")."""
    from codeslides.loader import load_deck
    from codeslides.serialization import save_edits

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.on_cell_edited(
        "live_demo",
        'def live_demo(speed):\n    result = speed * 3\n    return result\n',
        session,
    )
    assert "def live_demo(speed):" in session.source_overrides["live_demo"]

    kernel.rename_cell(session, "live_demo", "coding_demo")

    assert "coding_demo" in session.source_overrides
    assert "def coding_demo(speed):" in session.source_overrides["coding_demo"]
    assert "def live_demo" not in session.source_overrides["coding_demo"]
    # the edited body itself (speed * 3, not the original speed * 2)
    # must have survived byte-identical through the rename
    assert "speed * 3" in session.source_overrides["coding_demo"]

    save_edits(str(path), session.source_overrides)
    saved = path.read_text()
    assert "def coding_demo(speed):" in saved
    assert "def live_demo" not in saved
    assert "speed * 3" in saved


def test_rename_cell_does_not_affect_a_different_sessions_instances(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session_a = Session(deck=deck)
    session_b = Session(deck=deck)
    kernel.run_all(session_a)
    kernel.run_all(session_b)

    kernel.rename_cell(session_a, "live_demo", "coding_demo")

    assert "coding_demo" in session_a.instances
    assert "live_demo" in session_b.instances
    assert "coding_demo" not in session_b.instances


def test_rename_cell_blocked_when_another_cell_calls_it_directly(tmp_path):
    from codeslides.loader import load_deck

    source = (
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef drawSquare():\n    x = 1\n    return x\n\n"
        "@app.cell\ndef drawSquares():\n    result = drawSquare() + 1\n    return result\n"
    )
    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="drawSquares"):
        kernel.rename_cell(session, "drawSquare", "draw_one_square")

    # nothing was written -- the on-disk name is untouched
    assert "def drawSquare()" in path.read_text()


def test_rename_cell_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.rename_cell(session, "live_demo", "coding_demo")


def test_remove_cell_deletes_it_from_disk_and_kernel_and_cascades_the_slide(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.remove_cell(session, "live_demo")

    assert "live_demo" not in kernel.deck.cells
    assert "def live_demo" not in path.read_text()
    assert kernel.deck.slides[0].cell_names == []


def test_remove_cell_cleans_up_the_requesting_sessions_state(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.on_cell_edited("live_demo", 'def live_demo(speed):\n    result = speed * 3\n    return result\n', session)
    assert "live_demo" in session.instances
    assert "live_demo" in session.source_overrides
    assert "live_demo" in session.namespace

    kernel.remove_cell(session, "live_demo")

    assert "live_demo" not in session.instances
    assert "live_demo" not in session.source_overrides
    assert "live_demo" not in session.namespace


def test_remove_cell_blocked_when_another_cell_calls_it_directly(tmp_path):
    from codeslides.loader import load_deck

    source = (
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef drawSquare():\n    x = 1\n    return x\n\n"
        "@app.cell\ndef drawSquares():\n    result = drawSquare() + 1\n    return result\n"
    )
    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="drawSquares"):
        kernel.remove_cell(session, "drawSquare")

    # nothing was written -- the cell is still on disk
    assert "def drawSquare()" in path.read_text()


def test_remove_cell_blocked_when_another_cell_reads_a_name_only_its_return_binds(tmp_path):
    """Regression test for the gap found by hand this session: a cell
    that only *reads* a name bound by another cell's `return` (never
    calling that cell directly) is just as real a code dependency as a
    direct call, since `Cell.writes` always includes both the cell's
    own name and every name its own `return` binds (graph.py's
    `parse_cell`). The first draft of this check only tested `name in
    cell.reads` (mirroring rename_cell's check), which misses this case
    entirely -- confirmed by hand that it let `producer` be removed out
    from under `consumer` with no error before the fix to `cell.reads &
    removed_names`."""
    from codeslides.loader import load_deck

    source = (
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef producer():\n    shared_value = 42\n    return shared_value\n\n"
        "@app.cell\ndef consumer():\n    result = shared_value * 2  # noqa: F821\n    return result\n"
    )
    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="consumer"):
        kernel.remove_cell(session, "producer")

    # nothing was written -- the cell is still on disk
    assert "def producer()" in path.read_text()


def test_remove_cell_raises_if_the_name_does_not_exist(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="does not exist|no longer exists"):
        kernel.remove_cell(session, "does_not_exist")


def test_remove_cell_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.remove_cell(session, "live_demo")


def test_reorder_cells_updates_the_deck_cells_dict_order(tmp_path):
    from codeslides.loader import load_deck

    source = (
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef a():\n    x = 1\n    return x\n\n"
        "@app.cell\ndef b():\n    y = 2\n    return y\n\n"
        "@app.cell\ndef c():\n    z = 3\n    return z\n"
    )
    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.reorder_cells(session, ["c", "a", "b"])

    assert list(kernel.deck.cells) == ["c", "a", "b"]
    text = path.read_text()
    assert text.index("def c()") < text.index("def a()") < text.index("def b()")


def test_reorder_cells_requires_no_session_side_cleanup(tmp_path):
    from codeslides.loader import load_deck

    source = (
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell\ndef a():\n    x = 1\n    return x\n\n"
        "@app.cell\ndef b():\n    y = 2\n    return y\n"
    )
    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.reorder_cells(session, ["b", "a"])

    # the cells' own instances/namespace entries are untouched -- keyed
    # by name, not position, so nothing goes stale just from a reorder
    assert "a" in session.instances
    assert "b" in session.instances
    # the next run_all must not KeyError on the reordered deck
    kernel.run_all(session)


def test_reorder_cells_raises_on_a_non_permutation(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="permutation"):
        kernel.reorder_cells(session, ["live_demo", "does_not_exist"])


def test_reorder_cells_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.reorder_cells(session, ["live_demo", "setup"])


def test_add_element_updates_disk_kernel_and_session(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, result = kernel.add_element(session, "setup", ui.slider("multiplier", min=1, max=5, default=2))

    assert [e.name for e in cell.elements] == ["multiplier"]
    assert result.status == "idle"
    assert "multiplier" in kernel.deck.cells["setup"].elements[0].name
    assert "multiplier" in session.instances["setup"].elements
    assert "ui.slider('multiplier'" in path.read_text()


def test_add_element_resyncs_a_pending_source_override(tmp_path):
    """Regression test: adding an element writes the new `elements=[...]`
    decorator to disk immediately, but a session's own pending, unsaved
    code edit for the same cell (session.source_overrides) still carried
    the *old* decorator -- left alone, a later Save would splice that
    stale decorator back onto the file, silently reverting the just-
    added element even though the browser had already shown it added."""
    from codeslides.loader import load_deck
    from codeslides.serialization import save_edits

    path = _write_deck_file(tmp_path, _ADD_CELL_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    kernel.on_cell_edited(
        "setup",
        "def setup():\n    base = 9\n    return base\n",
        session,
    )
    assert "elements=" not in session.source_overrides["setup"]

    kernel.add_element(session, "setup", ui.slider("multiplier", min=1, max=5, default=2))

    assert "ui.slider('multiplier'" in session.source_overrides["setup"]
    # the edited body itself must have survived byte-identical
    assert "base = 9" in session.source_overrides["setup"]

    save_edits(str(path), session.source_overrides)
    saved = path.read_text()
    assert "ui.slider('multiplier'" in saved
    assert "base = 9" in saved


def test_add_element_raises_on_a_duplicate_element_name(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="speed"):
        kernel.add_element(session, "live_demo", ui.button("speed"))


def test_remove_element_updates_disk_kernel_and_session(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    cell, result = kernel.remove_element(session, "live_demo", "speed")

    assert cell.elements == []
    # `speed` has no default and, with its slider gone, no matching
    # element either -- an unbound required parameter, so the cell is
    # safely defined-but-not-called (_has_unbound_required_param)
    # rather than auto-called with `speed` missing entirely.
    assert result.status == "idle"
    assert "speed" not in session.instances["live_demo"].elements
    assert "ui.slider" not in path.read_text()


def test_remove_element_raises_if_the_element_does_not_exist(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="does_not_exist"):
        kernel.remove_element(session, "live_demo", "does_not_exist")


def test_reorder_elements_updates_disk_and_kernel_baseline(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.button("go"))

    cell = kernel.reorder_elements(session, "live_demo", ["go", "speed"])

    assert [e.name for e in cell.elements] == ["go", "speed"]
    assert [e.name for e in kernel.deck.cells["live_demo"].elements] == ["go", "speed"]


def test_reorder_elements_does_not_rerun_the_cell(tmp_path):
    """A pure reorder never changes execution -- confirm the cell's own
    status/output are left exactly as they were, since nothing was
    re-run."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.button("go"))
    status_before = session.instances["live_demo"].status
    output_before = session.instances["live_demo"].output

    kernel.reorder_elements(session, "live_demo", ["go", "speed"])

    assert session.instances["live_demo"].status == status_before
    assert session.instances["live_demo"].output == output_before


def test_reorder_elements_raises_on_a_non_permutation(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="permutation"):
        kernel.reorder_elements(session, "live_demo", ["speed", "does_not_exist"])


def test_reorder_elements_without_a_deck_path_raises():
    app = _build_deck()
    kernel = Kernel(app.deck)  # no deck_path
    session = Session(deck=app.deck)

    with pytest.raises(ValueError, match="deck file"):
        kernel.reorder_elements(session, "live_demo", ["speed"])


def test_set_element_config_updates_disk_and_kernel_baseline(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.iframe("preview", src="https://old.example.com"))

    cell = kernel.set_element_config(session, "live_demo", "preview", {"src": "https://new.example.com"})

    # Reloading re-executes the on-disk `ui.iframe(...)` call through the
    # real constructor, which re-applies its own `height=240` default for
    # the kwarg this call omitted -- see test_serialization.py's own
    # version of this assertion for the full explanation.
    preview = next(e for e in cell.elements if e.name == "preview")
    assert preview.config == {"src": "https://new.example.com", "height": 240}
    assert kernel.deck.cells["live_demo"].elements[-1].config == {
        "src": "https://new.example.com",
        "height": 240,
    }


def test_set_element_config_pushes_an_iframes_new_src_into_the_sessions_content(tmp_path):
    """An iframe's rendered content otherwise only ever changes via the
    owning cell's own cs.iframe() call during a run -- confirm editing
    the config here also updates the *live* content directly, since
    otherwise the browser would never see the new URL until the cell
    happened to re-run."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.iframe("preview", src="https://old.example.com"))
    # seed_cell_instance now seeds an iframe/image element's own static
    # `src=` config as its initial content (session.py) -- an author-set
    # default is no longer invisible until the cell happens to run.
    assert session.instances["live_demo"].elements["preview"].content == "https://old.example.com"

    kernel.set_element_config(session, "live_demo", "preview", {"src": "https://new.example.com"})

    assert session.instances["live_demo"].elements["preview"].content == "https://new.example.com"


def test_set_element_config_pushes_an_images_new_src_into_the_sessions_content(tmp_path):
    """The user's own request: uploading an image through the browser's
    file picker must show up immediately -- an image's rendered content
    otherwise only ever changes via the owning cell's own
    cs.image(...) call during a run.

    A data-URI `src` (what the file picker actually sends) is decoded
    and written to a real file in `assets/` next to the deck
    (`_save_data_uri_as_asset`) rather than stored inline -- the
    Session's own `content` (what the browser is told to fetch) is the
    matching `/deck-assets/...` URL, not the data URI itself. An
    image's `src`/`content` is always a list (even one image), so a
    second upload can extend it into a carousel."""
    import base64

    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.image("photo"))
    # no src yet -- seed_cell_instance only seeds content for a truthy
    # src (an empty default has nothing to show, same as "no image yet")
    assert session.instances["live_demo"].elements["photo"].content is None

    kernel.set_element_config(
        session, "live_demo", "photo", {"src": ["data:image/png;base64,iVBORw0KGgo="]}
    )

    content = session.instances["live_demo"].elements["photo"].content
    assert len(content) == 1
    assert content[0].startswith("/deck-assets/")
    assert content[0].endswith(".png")
    # the real file was actually written next to the deck
    asset_path = tmp_path / "assets" / content[0].removeprefix("/deck-assets/")
    assert asset_path.exists()
    assert asset_path.read_bytes() == base64.b64decode("iVBORw0KGgo=")
    # and the .py file's own src= is the small, portable relative path,
    # never the raw data URI
    saved_element = next(e for e in kernel.deck.cells["live_demo"].elements if e.name == "photo")
    assert saved_element.config["src"] == [f"assets/{content[0].removeprefix('/deck-assets/')}"]


def test_set_element_config_appends_a_second_image_into_a_carousel(tmp_path):
    """The user's own request: multiple uploaded images become a
    carousel. Multi-selecting files in the picker sends the *whole*
    list (existing images plus newly-picked ones) in one
    set_element_config call -- confirm the first image's already-
    written file is left untouched (not re-decoded/re-hashed) while the
    second, still a fresh data URI, gets its own new file."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    kernel.add_element(session, "live_demo", ui.image("photo"))
    kernel.set_element_config(session, "live_demo", "photo", {"src": ["data:image/png;base64,iVBORw0KGgo="]})
    first_content = list(session.instances["live_demo"].elements["photo"].content)
    # the .py file's own relative src= list, mirroring what
    # EditCellPanel.tsx echoes back as element.config.src before
    # appending newly-picked files to it
    existing_relative_srcs = next(
        e for e in kernel.deck.cells["live_demo"].elements if e.name == "photo"
    ).config["src"]

    kernel.set_element_config(
        session,
        "live_demo",
        "photo",
        {"src": [*existing_relative_srcs, "data:image/png;base64,aVBORw0KGgo="]},
    )

    content = session.instances["live_demo"].elements["photo"].content
    assert len(content) == 2
    assert content[0] == first_content[0]  # untouched, not re-written
    assert content[1] != content[0]
    assert content[1].startswith("/deck-assets/")
    assert len(list((tmp_path / "assets").iterdir())) == 2


def test_image_element_with_a_static_src_is_seeded_at_construction(tmp_path):
    """Regression test: an image (or iframe) element's own static `src=`
    -- set at construction time, or via the file picker/URL box before
    this Session even existed -- must be visible immediately, not stuck
    at `None` until the owning cell happens to run at least once
    (session.py's seed_cell_instance)."""
    from codeslides.loader import load_deck

    path = _write_deck_file(
        tmp_path,
        "from codeslides import App, ui\n\napp = App()\n\n"
        '@app.cell(elements=[ui.image("photo", src="data:image/png;base64,abc")])\n'
        "def show():\n    pass\n",
    )
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    assert session.instances["show"].elements["photo"].content == ["data:image/png;base64,abc"]


def test_save_data_uri_as_asset_writes_a_real_file(tmp_path):
    import base64

    from codeslides.kernel import _save_data_uri_as_asset

    deck_path = str(tmp_path / "deck.py")
    (tmp_path / "deck.py").write_text("from codeslides import App\n\napp = App()\n")

    relative = _save_data_uri_as_asset(deck_path, "data:image/png;base64,iVBORw0KGgo=")

    assert relative.startswith("assets/")
    assert relative.endswith(".png")
    asset_path = tmp_path / relative
    assert asset_path.exists()
    assert asset_path.read_bytes() == base64.b64decode("iVBORw0KGgo=")


def test_save_data_uri_as_asset_reuses_the_file_for_identical_bytes(tmp_path):
    """Re-uploading the exact same image byte-for-byte must not
    accumulate duplicate files -- same content hashes to the same
    filename, so the second call is a no-op write that reuses the
    first call's file."""
    from codeslides.kernel import _save_data_uri_as_asset

    deck_path = str(tmp_path / "deck.py")
    (tmp_path / "deck.py").write_text("from codeslides import App\n\napp = App()\n")

    first = _save_data_uri_as_asset(deck_path, "data:image/png;base64,iVBORw0KGgo=")
    second = _save_data_uri_as_asset(deck_path, "data:image/png;base64,iVBORw0KGgo=")

    assert first == second
    assert len(list((tmp_path / "assets").iterdir())) == 1


def test_save_data_uri_as_asset_gives_different_images_different_files(tmp_path):
    from codeslides.kernel import _save_data_uri_as_asset

    deck_path = str(tmp_path / "deck.py")
    (tmp_path / "deck.py").write_text("from codeslides import App\n\napp = App()\n")

    first = _save_data_uri_as_asset(deck_path, "data:image/png;base64,iVBORw0KGgo=")
    second = _save_data_uri_as_asset(deck_path, "data:image/png;base64,aVBORw0KGgo=")

    assert first != second
    assert len(list((tmp_path / "assets").iterdir())) == 2


def test_save_data_uri_as_asset_infers_extension_from_mime_type(tmp_path):
    from codeslides.kernel import _save_data_uri_as_asset

    deck_path = str(tmp_path / "deck.py")
    (tmp_path / "deck.py").write_text("from codeslides import App\n\napp = App()\n")

    relative = _save_data_uri_as_asset(deck_path, "data:image/jpeg;base64,/9k=")

    assert relative.endswith(".jpg")


def test_save_data_uri_as_asset_raises_on_a_non_data_uri(tmp_path):
    from codeslides.kernel import _save_data_uri_as_asset

    deck_path = str(tmp_path / "deck.py")
    (tmp_path / "deck.py").write_text("from codeslides import App\n\napp = App()\n")

    with pytest.raises(ValueError, match="not a base64 data URI"):
        _save_data_uri_as_asset(deck_path, "https://example.com/photo.png")


def test_save_data_uri_as_asset_raises_on_an_unsupported_mime_type(tmp_path):
    from codeslides.kernel import _save_data_uri_as_asset

    deck_path = str(tmp_path / "deck.py")
    (tmp_path / "deck.py").write_text("from codeslides import App\n\napp = App()\n")

    with pytest.raises(ValueError, match="unsupported image MIME type"):
        _save_data_uri_as_asset(deck_path, "data:application/pdf;base64,JVBER=")


def test_set_element_config_does_not_touch_a_non_iframe_non_image_elements_content(tmp_path):
    """The content-push is deliberately iframe/image-only -- a slider's
    config change (e.g. min/max) has no analogous "content" to push, and
    must not clobber whatever `value` it's currently holding."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)
    session.instances["live_demo"].elements["speed"].value = 7

    kernel.set_element_config(session, "live_demo", "speed", {"min": 1, "max": 20, "default": 3})

    assert session.instances["live_demo"].elements["speed"].value == 7


def test_set_element_config_raises_if_the_element_does_not_exist(tmp_path):
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _RENAME_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)
    kernel.run_all(session)

    with pytest.raises(ValueError, match="does_not_exist"):
        kernel.set_element_config(session, "live_demo", "does_not_exist", {})


_TOP_LEVEL_IMPORT_DECK_SOURCE = (
    "from codeslides import App\n\n"
    "import math\n\n"
    "app = App()\n\n"
    "@app.cell\n"
    "def uses_math():\n"
    "    value = math.sqrt(16)\n"
    "    return value\n"
)


def test_a_cell_can_use_a_deck_level_top_level_import(tmp_path):
    """A cell body relying on `import math` written once at the top of
    the deck file (never its own repeated `import math`) must resolve
    it -- previously NameError'd, since each cell's globals were seeded
    only from cs/turtle/session.namespace, never the deck module's own
    globals()."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _TOP_LEVEL_IMPORT_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    kernel.run_all(session)

    assert session.instances["uses_math"].status == "idle"
    assert session.namespace["value"] == 4.0


def test_a_cells_own_write_wins_over_a_same_named_deck_level_import(tmp_path):
    # deck_imports is merged in before session.namespace in execute_cell,
    # matching the existing cs/turtle precedent -- a cell's own write
    # (however unlikely the name collision) must still take priority.
    source = (
        "from codeslides import App\n\n"
        "import math\n\n"
        "app = App()\n\n"
        "@app.cell\n"
        "def shadows_math():\n"
        "    math = 'shadowed'\n"
        "    return math\n"
    )
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    kernel.run_all(session)

    assert session.namespace["math"] == "shadowed"


def test_a_tests_element_can_use_a_deck_level_top_level_import(tmp_path):
    source = (
        "from codeslides import App, ui\n\n"
        "import math\n\n"
        "app = App()\n\n"
        '@app.cell(elements=[ui.tests("unit", default="assert math.isclose(uses_math(), 4.0)")])\n'
        "def uses_math():\n"
        "    value = math.sqrt(16)\n"
        "    return value\n"
    )
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, source)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    kernel.run_all(session)

    content = session.instances["uses_math"].elements["unit"].content
    assert content["status"] == "pass", content["message"]


def test_deck_built_directly_via_app_without_load_deck_has_no_imports():
    """A Deck never loaded from a file (e.g. App() used directly, as
    every other test in this file does) has no way to know what a
    top-level import would even be -- imports defaults to {} and
    execution proceeds exactly as it did before this feature."""
    app = _build_deck()
    assert app.deck.imports == {}


_HIDE_DEF_DECK_SOURCE = (
    "from codeslides import App\n\n"
    "app = App()\n\n"
    "@app.cell(instance=\"editable\", hide_def=True)\n"
    "def setup():\n"
    "    base = 5\n"
    "    return base\n"
)


def test_hide_def_cell_source_still_has_the_real_def_line():
    """hide_def only ever affects display/reattachment (serialization.py)
    -- Cell.source, execution, and the dependency graph all still see
    the cell's real, complete function, exactly like a hide_def=False
    cell. Only what the browser is shown/sends back changes."""
    app = App()

    @app.cell(hide_def=True)
    def setup():
        base = 5
        return base

    cell = app.deck.cells["setup"]
    assert cell.hide_def is True
    assert "def setup():" in cell.source


def test_hide_def_survives_a_kernel_construction(tmp_path):
    """Regression guard of the same shape as the Cell.docstring bug this
    session already found once: graph.py's parse_cell reconstructs a
    fresh Cell on every Kernel(), and it's easy to add a new Cell field
    without also carrying it through there."""
    from codeslides.loader import load_deck

    path = _write_deck_file(tmp_path, _HIDE_DEF_DECK_SOURCE)
    deck = load_deck(str(path))
    assert deck.cells["setup"].hide_def is True

    kernel = Kernel(deck, deck_path=str(path))
    assert kernel.deck.cells["setup"].hide_def is True


def test_on_cell_edited_with_hide_def_reattaches_the_def_line_before_saving(tmp_path):
    from codeslides.loader import load_deck
    from codeslides.serialization import save_edits

    path = _write_deck_file(tmp_path, _HIDE_DEF_DECK_SOURCE)
    deck = load_deck(str(path))
    kernel = Kernel(deck, deck_path=str(path))
    session = Session(deck=deck)

    # what the browser's editor actually sends for a hide_def cell: no
    # def line, un-indented -- see display_source(hide_def=True)'s output
    kernel.on_cell_edited("setup", "base = 7\nreturn base\n", session)

    assert session.instances["setup"].status == "idle"
    assert session.namespace["base"] == 7
    assert "def setup():" in session.source_overrides["setup"]

    save_edits(str(path), session.source_overrides)
    reloaded = load_deck(str(path))
    assert reloaded.cells["setup"].hide_def is True
    assert "base = 7" in reloaded.cells["setup"].source


def test_get_deck_api_hides_the_def_line_for_a_hide_def_cell(tmp_path):
    from codeslides.loader import load_deck
    from codeslides.serialization import display_source

    path = _write_deck_file(tmp_path, _HIDE_DEF_DECK_SOURCE)
    deck = load_deck(str(path))
    cell = deck.cells["setup"]

    shown = display_source(cell.source, hide_def=cell.hide_def)

    assert "def setup" not in shown
    assert shown == "base = 5\nreturn base\n"
