# CodeSlides — Vision

## What this is

A tool for teaching programming through **code slides**: a presentation
format where the "slides" are live, runnable Python code instead of static
bullet points. It's heavily inspired by [marimo](https://marimo.io), taking
the parts of marimo's design that make it a great teaching tool and building
a presentation layer on top, aimed specifically at live classroom teaching.

## Why

Teaching programming from static slides (PowerPoint, Keynote, even Jupyter
run cell-by-cell) has recurring problems:

- Code shown on a slide and code actually running live drift apart — what
  students see isn't provably what's executing.
- Live-coding in a plain REPL or Jupyter notebook exposes messy notebook
  state: out-of-order execution, stale variables, cells that only work
  because of something run three cells ago and since deleted.
- Switching between "slide mode" (explaining a concept) and "code mode"
  (showing it run) usually means switching windows/tools entirely, which
  breaks the flow of a lecture.

marimo already solves the reproducibility problem for notebooks: cells form
a dependency graph, editing one reactively re-runs everything downstream, and
there's no hidden state — the notebook always reflects what would happen if
run top to bottom. It also stores notebooks as plain `.py` files, so they're
diffable, importable, and version-controllable like normal code.

CodeSlides takes that reactive core and adds an explicit **slideshow mode**:
group cells into slides, hide code by default when presenting, and let an
instructor reveal and live-edit code in front of a class without breaking
the reactive guarantees marimo provides.

## Core principles

1. **Reactive, not sequential.** Editing a cell re-runs it and everything
   that depends on it — never stale state, never "did I run that cell
   already?" confusion in front of a room of students.
2. **Plain Python files.** A deck is a `.py` file. It's git-diffable, can be
   imported as a module, and doesn't hide meaningful content in an opaque
   JSON blob.
3. **One tool, two modes.** The same deck is both an editable notebook and a
   presentable slideshow. No exporting to a different format to present;
   toggle modes in place.
4. **Built for live teaching first.** Slideshow mode assumes an instructor
   presenting to a room: large fonts, a "reveal code" toggle, the ability to
   live-edit and re-run during the talk, and fast keyboard navigation.
5. **Interactive by default.** UI widgets (sliders, dropdowns, etc.) bound
   directly to Python variables let an instructor demonstrate *how a
   parameter affects behavior* live, instead of describing it.

## Non-goals (for now)

- Not trying to be a general-purpose notebook replacement for data science
  workflows — the target user is an instructor building a lesson, not a
  data scientist doing exploratory analysis (though nothing precludes that
  use later).
- Not building collaborative multi-user real-time editing (like Google
  Docs). Single presenter/author per session, at least for v1.
- Not supporting languages other than Python.

## What success looks like

An instructor can write a lesson as a single `.py` file, open it with
`codeslides edit lesson.py` to build and test it cell-by-cell, then run
`codeslides present lesson.py` in front of a class, walk through slides,
reveal and tweak code live, and have every downstream output update
correctly and instantly — with zero notebook-state footguns.

## Relationship to marimo

CodeSlides is not a fork of marimo and doesn't aim for feature parity. It
borrows marimo's reactive-kernel architecture and file-format philosophy as
proven ideas, and builds a distinct product on top: a teaching-first
presentation tool rather than a general-purpose reactive notebook.
