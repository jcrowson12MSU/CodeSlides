"""Demo deck for the live Notes editor (frontend/src/widgets/NotesEditor.tsx)
-- one slide per group of implemented markdown constructs, so every
feature listed as "implemented" in NOTES_MARKDOWN_TODO.md has a working
example here. Click into any notes panel and then click a rendered line
to see its raw markdown reappear (the editor's cursor-aware reveal);
click elsewhere to see it render again.

Each cell exists solely to host a `notes` element -- there's nothing to
run, so every cell body is a no-op `pass`.
"""

from codeslides import App, ui

app = App()


@app.cell(hide_def=True, is_main=True, elements=[ui.notes("notes")])
def intro():
    """# Live Notes Editor

A tour of every markdown construct the live-preview Notes editor
currently supports -- click into any line below to see its raw
syntax, click away to see it render again.

Use the **Slides** view (top of the page) to step through one
feature group per slide."""


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def headings_and_text():
    """# Heading 1
## Heading 2
### Heading 3

Plain paragraph text with **bold**, *italic*, and `inline code`.

You can mix **bold and *nested italic*** together, and reference a
[link to the CodeSlides repo](https://github.com/jcrowson12MSU/CodeSlides)
inline."""


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def images_and_links():
    """## Images, autolinks, and breaks

An image, replaced with a real `<img>`:

![a small placeholder image](https://placehold.co/120x80.png)

An autolink, shown as its own URL text: <https://example.com>

A hard line break (two trailing spaces) forces a line to end here.
This text starts on its own new line because of that break.

---

The horizontal rule above is a real `<hr>`, not literal dashes."""


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def quotes_and_code():
    """## Blockquotes and fenced code

> Blockquote content is set off with a left border and dimmed text,
> spanning every line of the quote, not just the `>` marker.

A fenced code block keeps its fence lines and language tag visible
even when rendered (unlike inline code, which hides its backticks):

```python
def marching_squares(cells, t):
    for row in cells:
        print(row)
```

Compare that to `inline code`, whose backticks disappear."""


@app.cell(hide_def=True, elements=[ui.notes("notes")])
def tables_and_tasks():
    """## Tables, task lists, sub/superscript

| Feature | Status |
| ------- | ------ |
| Tables | done |
| Task lists | done |
| Subscript | done |

A short todo list:

- [x] Enable the Table and TaskList parser extensions
- [x] Enable Subscript and Superscript
- [ ] Enable Strikethrough (not yet requested)

Chemistry and math both read naturally: water is H~2~O, and
Einstein's E = mc^2^."""


@app.slide("Title", cells=[])
def slide_title():
    """"""


@app.slide("Headings & Inline Styles", cells=["headings_and_text"])
def slide_headings():
    """"""


@app.slide("Images, Links & Breaks", cells=["images_and_links"])
def slide_images():
    """"""


@app.slide("Blockquotes & Code Blocks", cells=["quotes_and_code"])
def slide_quotes():
    """"""


@app.slide("Tables, Tasks & Sub/Superscript", cells=["tables_and_tasks"])
def slide_tables():
    """"""
