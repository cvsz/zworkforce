"""tests/test_utils.py"""
import pytest

from wire.utils import format_code_block, sampling_kwargs, wrap_text


@pytest.mark.parametrize("model", [
    "zc-xxx",
    "zc-fable-5",
    "zc-mythos-5",
    "zc-xxx-20260101",
])
def test_sampling_kwargs_omitted_for_no_sampling_models(model):
    assert sampling_kwargs(model, temperature=0.7) == {}


@pytest.mark.parametrize("model", [
    "zc-opus-4-8",
    "zc-haiku-4-5-20251001",
    "zc-3-5-sonnet",
])
def test_sampling_kwargs_included_for_other_models(model):
    result = sampling_kwargs(model, temperature=0.7, top_p=0.9)
    assert result == {"temperature": 0.7, "top_p": 0.9}


def test_sampling_kwargs_only_includes_provided_values():
    result = sampling_kwargs("zc-opus-4-8", temperature=0.5)
    assert result == {"temperature": 0.5}
    assert "top_p" not in result
    assert "top_k" not in result


def test_sampling_kwargs_handles_none_model():
    assert sampling_kwargs(None, temperature=0.5) == {"temperature": 0.5}


def test_format_code_block():
    assert format_code_block("print(1)", "python") == "```python\nprint(1)\n```"


def test_wrap_text_respects_width():
    text = "word " * 40
    wrapped = wrap_text(text, width=20)
    assert all(len(line) <= 20 for line in wrapped.splitlines())
