"""Resolves a cell's returned value into the tagged output union from
ARCHITECTURE.md section 6, so the frontend can render plain text,
markdown, images (including matplotlib figures), and DataFrames
differently instead of just JSON-stringifying whatever Python repr comes
back.

Optional libraries (matplotlib, pandas) are detected by class name rather
than imported at module load time, so `codeslides` doesn't gain a hard
dependency on either just to support them when a lesson author has them
installed -- see `_looks_like` below.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any


@dataclass
class Markdown:
    """Wraps a string as markdown for output display, matching marimo's
    `mo.md()`. Distinct from a `notes` element (ARCHITECTURE.md section
    3a), which is authored ahead of time and toggled, not returned from a
    cell's execution."""

    text: str


def md(text: str) -> Markdown:
    """Wrap `text` as markdown; return it from a cell to render it as
    formatted markdown instead of a plain repr."""
    return Markdown(text)


@dataclass
class ResolvedOutput:
    """The tagged output union itself: `kind` matches one of
    ARCHITECTURE.md section 6's cases, `data` is kind-specific payload
    ready to serialize over the websocket."""

    kind: str  # "text" | "markdown" | "image" | "dataframe"
    data: Any


def _looks_like(value: Any, module_prefix: str, class_name: str) -> bool:
    """Duck-type by class name/module rather than importing the library
    -- lets codeslides recognize a matplotlib Figure or pandas DataFrame
    without requiring either as a dependency."""
    cls = type(value)
    return cls.__name__ == class_name and cls.__module__.startswith(module_prefix)


def _figure_to_data_uri(figure: Any) -> str:
    buf = io.BytesIO()
    figure.savefig(buf, format="png", bbox_inches="tight")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def _dataframe_to_table(df: Any) -> dict[str, Any]:
    return {
        "columns": [str(c) for c in df.columns],
        "rows": df.astype(object).where(df.notna(), None).values.tolist(),
    }


def resolve_output(value: Any) -> ResolvedOutput:
    """Classify a cell's returned value into the tagged output union.
    Falls through to plain text (`repr`/`str`) for anything not
    recognized -- every existing cell's output keeps working exactly as
    before this task, just wrapped in a `kind`/`data` shape."""
    if value is None:
        return ResolvedOutput(kind="text", data="")
    if isinstance(value, Markdown):
        return ResolvedOutput(kind="markdown", data=value.text)
    if _looks_like(value, "matplotlib", "Figure"):
        return ResolvedOutput(kind="image", data=_figure_to_data_uri(value))
    if _looks_like(value, "pandas", "DataFrame"):
        return ResolvedOutput(kind="dataframe", data=_dataframe_to_table(value))
    if isinstance(value, (str, int, float, bool)):
        return ResolvedOutput(kind="text", data=str(value))
    return ResolvedOutput(kind="text", data=repr(value))


def wire_safe_value(value: Any) -> Any:
    """A JSON-safe rendition of a cell's raw returned value, for the
    `value` field alongside `kind`/`data` in the outgoing message.

    Most cell return values (numbers, strings, lists/dicts of those,
    None) already serialize fine and are kept as-is, since existing
    consumers of the wire format's `value` field (and JSON.stringify(...)
    call sites still being migrated to `kind`/`data` dispatch) shouldn't
    regress. Anything `resolve_output` had to fall back to `repr()` for --
    a matplotlib Figure, a pandas DataFrame, or any other non-primitive
    object -- is not JSON-serializable (a raw Figure crashes
    `websocket.send_json` outright, confirmed by hand), so it's replaced
    with that same repr() here too, matching what a reader would see
    either way.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Markdown):
        return value.text
    if isinstance(value, (list, tuple)):
        return [wire_safe_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): wire_safe_value(v) for k, v in value.items()}
    return repr(value)
