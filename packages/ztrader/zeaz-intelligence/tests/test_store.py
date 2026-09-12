from ztrader_intel.models import (
    Action,
    IntelligenceResponse,
    NarrativeStage,
    RugRisk,
    Scores,
    TokenRef,
    WhaleState,
    WatchlistEntry,
)
from ztrader_intel.store import AnalysisStore


def test_store_history_and_watchlist(tmp_path):
    store = AnalysisStore(str(tmp_path / "intel.db"))
    response = IntelligenceResponse(
        token=TokenRef(symbol="ABC", chain="base", address="0x1"),
        narrative=NarrativeStage.HEATING_UP,
        whales=WhaleState.NEUTRAL,
        rug_risk=RugRisk.MEDIUM,
        action=Action.WAIT,
        scores=Scores(opportunity=50, risk=40, confidence=60),
        reasons=[],
        red_flags=[],
        invalidations=[],
        watch_next=[],
    )
    store.save(response)
    assert len(store.history("ABC")) == 1

    store.upsert_watchlist(WatchlistEntry(token=response.token, note="watch"))
    items = store.list_watchlist()
    assert len(items) == 1
    assert items[0].note == "watch"
