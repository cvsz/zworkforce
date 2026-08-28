import pytest

from wire.restricted_code import RestrictedCodeError, validate_restricted_code
from wire.zc_excel import ExcelSession, pd
from wire.zc_powerpoint import PptxSession


def test_allows_explicit_document_helpers_and_literals() -> None:
    validate_restricted_code(
        'add_slide("Title", bullets=["One", "Two"])',
        allowed_calls={"add_slide"},
    )


@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "open('/etc/passwd')",
        "(1).__class__.__mro__",
        "getattr(slides, name)()",
        "lambda: 1",
        "def hidden():\n    return 1",
    ],
)
def test_rejects_escape_primitives(code: str) -> None:
    with pytest.raises(RestrictedCodeError):
        validate_restricted_code(code, allowed_calls={"add_slide"})


def test_allows_only_named_dataframe_methods() -> None:
    validate_restricted_code(
        'sheets["Sheet1"] = sheets["Sheet1"].dropna()',
        allowed_calls=set(),
        allowed_methods={"dropna"},
    )

    with pytest.raises(RestrictedCodeError, match="method"):
        validate_restricted_code(
            'sheets["Sheet1"].to_pickle("/tmp/leak")',
            allowed_calls=set(),
            allowed_methods={"dropna"},
        )


@pytest.mark.skipif(pd is None, reason="pandas is optional")
def test_excel_session_applies_allowed_transform_and_blocks_file_write() -> None:
    session = ExcelSession.__new__(ExcelSession)
    session.sheets = {"Sheet1": pd.DataFrame({"value": [1, None]})}
    session._history_stack = []
    session._pending_charts = []

    ok, _message = session.apply_code(
        'sheets["Sheet1"] = sheets["Sheet1"].dropna()'
    )
    assert ok is True
    assert len(session.sheets["Sheet1"]) == 1

    ok, message = session.apply_code(
        'sheets["Sheet1"].to_pickle("/tmp/zc-restricted-code-test")'
    )
    assert ok is False
    assert "[blocked]" in message


def test_powerpoint_session_allows_helpers_and_blocks_private_access() -> None:
    session = PptxSession.__new__(PptxSession)
    session.slides = []
    session._history_stack = []
    session._template_path = None

    ok, _message = session.apply_code(
        'add_slide("Security", bullets=["Bounded", "Validated"])'
    )
    assert ok is True
    assert session.slides[0]["title"] == "Security"

    ok, message = session.apply_code("slides.__class__")
    assert ok is False
    assert "[blocked]" in message
