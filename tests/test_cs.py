import pytest

from codeslides import cs


def test_cs_helper_outside_execution_context_raises():
    with pytest.raises(RuntimeError, match="outside of cell execution"):
        cs.image("plot", "/tmp/figure.png")


def test_execution_context_collects_writes():
    with cs.execution_context() as writes:
        cs.image("plot", "/tmp/a.png")
        cs.iframe("frame", "https://example.com")

    assert writes == [
        # a one-item list, not a bare string -- an image element's
        # content is always a list, uniform with the multi-image
        # carousel a browser upload can produce (cs.image's own
        # docstring)
        cs.ElementWrite(element_name="plot", kind="image", content=["/tmp/a.png"]),
        cs.ElementWrite(element_name="frame", kind="iframe", content="https://example.com"),
    ]


def test_execution_context_is_isolated_per_call():
    with cs.execution_context() as writes_a:
        cs.image("a", "1.png")

    with cs.execution_context() as writes_b:
        cs.image("b", "2.png")

    assert len(writes_a) == 1
    assert len(writes_b) == 1
    assert writes_a[0].element_name == "a"
    assert writes_b[0].element_name == "b"


def test_calls_outside_context_after_it_closes_raise_again():
    with cs.execution_context():
        cs.image("a", "1.png")  # fine, inside context

    with pytest.raises(RuntimeError):
        cs.image("a", "1.png")  # context has exited
