from codeslides.cli import _build_urls


def test_build_urls_solo_edit():
    """`codeslides edit` with no --collaborative: a single URL, no
    ?document= or ?mode= query param, and no viewer link -- unchanged
    from before TODO.md #46e existed."""
    url, viewer_url = _build_urls(
        "http://127.0.0.1:8000/", present_mode=False, collaborative=False
    )
    assert url == "http://127.0.0.1:8000/"
    assert viewer_url is None


def test_build_urls_solo_present():
    """`codeslides present` with no --collaborative: ?mode=slides only."""
    url, viewer_url = _build_urls(
        "http://127.0.0.1:8000/", present_mode=True, collaborative=False
    )
    assert url == "http://127.0.0.1:8000/?mode=slides"
    assert viewer_url is None


def test_build_urls_collaborative_edit():
    """TODO.md #46e-i/#46e-ii: --collaborative on `edit` produces an
    editor link (bare ?document=<id>) and a separate viewer link
    (&role=viewer appended) -- both pointing at the same document id, and
    neither carrying ?mode=slides (that's `present`-only)."""
    url, viewer_url = _build_urls(
        "http://127.0.0.1:8000/", present_mode=False, collaborative=True, document_id="abc123"
    )
    assert url == "http://127.0.0.1:8000/?document=abc123"
    assert viewer_url == "http://127.0.0.1:8000/?document=abc123&role=viewer"


def test_build_urls_collaborative_present():
    """TODO.md #46e-i: --collaborative on `present` composes with
    ?mode=slides correctly -- both the editor and viewer links open
    directly into the Slides view, not the flat Cells view."""
    url, viewer_url = _build_urls(
        "http://127.0.0.1:8000/", present_mode=True, collaborative=True, document_id="abc123"
    )
    assert url == "http://127.0.0.1:8000/?mode=slides&document=abc123"
    assert viewer_url == "http://127.0.0.1:8000/?mode=slides&document=abc123&role=viewer"


def test_build_urls_editor_link_is_the_one_opened():
    """TODO.md #46e-i: `main()` always opens the *editor* link in the
    browser for the person who ran the CLI command -- confirmed here at
    the _build_urls level: the first returned URL (what `main` passes to
    `webbrowser.open`) never carries &role=viewer."""
    url, _ = _build_urls(
        "http://127.0.0.1:8000/", present_mode=False, collaborative=True, document_id="xyz789"
    )
    assert "role=viewer" not in url
