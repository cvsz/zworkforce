import pytest

from zaicoder.streaming import StreamRenderGate


def test_first_delta_renders_immediately():
    gate = StreamRenderGate(interval_seconds=0.1, char_threshold=10)
    assert gate.should_render("a", now=10.0)


def test_small_deltas_are_coalesced_until_frame_interval():
    gate = StreamRenderGate(interval_seconds=0.1, char_threshold=10)
    assert gate.should_render("a", now=0.0)
    assert not gate.should_render("b", now=0.02)
    assert not gate.should_render("c", now=0.09)
    assert gate.should_render("d", now=0.10)


def test_final_flush_renders_pending_text():
    gate = StreamRenderGate(interval_seconds=1.0, char_threshold=96)
    assert gate.should_render("Hi", now=0.0)
    assert not gate.should_render(" there!", now=0.01)
    assert gate.flush(now=0.02)


@pytest.mark.parametrize("kwargs", [{"interval_seconds": 0}, {"char_threshold": 0}])
def test_invalid_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        StreamRenderGate(**kwargs)
