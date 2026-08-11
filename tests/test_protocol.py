import pytest

from codeslides.protocol import (
    AddSlide,
    CloneSession,
    EditCell,
    NavigateSlide,
    RunAll,
    SetElementValue,
    SetTestSource,
    SetUiState,
    decode_client_message,
    encode,
)


@pytest.mark.parametrize(
    "message",
    [
        EditCell(session_id="s1", cell_id="c1", source="x = 1"),
        RunAll(session_id="s1"),
        SetElementValue(session_id="s1", cell_id="c1", element_id="speed", value=7),
        SetUiState(session_id="s1", cell_id="c1", collapsed=True),
        SetUiState(session_id="s1", cell_id="c1", element_id="speed", minimized=True),
        SetTestSource(session_id="s1", cell_id="c1", element_id="unit", source="assert True"),
        CloneSession(source_session_id="s1"),
        NavigateSlide(session_id="s1", slide_id="slide_1"),
        AddSlide(session_id="s1", title="Intro", cell_names=["c1", "c2"]),
        AddSlide(session_id="s1", title="Intro", cell_names=["c1"], reveal_code=True),
    ],
)
def test_client_message_roundtrips(message):
    assert decode_client_message(encode(message)) == message


def test_encode_includes_type_tag():
    encoded = encode(RunAll(session_id="s1"))
    assert encoded["type"] == "run_all"
    assert encoded["session_id"] == "s1"


def test_decode_rejects_missing_type():
    with pytest.raises(ValueError, match="missing required 'type'"):
        decode_client_message({"session_id": "s1"})


def test_decode_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown client message type"):
        decode_client_message({"type": "not_a_real_type"})


def test_decode_rejects_malformed_payload():
    with pytest.raises(ValueError, match="malformed 'edit_cell' message"):
        decode_client_message({"type": "edit_cell", "session_id": "s1"})
