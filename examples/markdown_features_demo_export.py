    """# Live Notes Editor

A tour of every markdown construct the live-preview Notes editor
currently supports -- click into any line below to see its raw
syntax, click away to see it render again.

Use the **Slides** view (top of the page) to step through one
feature group per slide."""


    """# Heading 1
## Heading 2
### Heading 3

Plain paragraph text with **bold**, *italic*, and `inline code`.

You can mix **bold and *nested italic*** together, and create a hyperline to reference another webpage
[link to the CodeSlides repo](https://github.com/jcrowson12MSU/CodeSlides)
inline."""


    """## Images, autolinks, and breaks

An image, replaced with a real `<img>`:

![a small placeholder image](https://placehold.co/120x80.png)

An autolink, shown as its own URL text: <https://example.com>

A hard line break (two trailing spaces) forces a line to end here.
This text starts on its own new line because of that break.

---

The horizontal rule above is a real `<hr>`, not literal dashes."""


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
