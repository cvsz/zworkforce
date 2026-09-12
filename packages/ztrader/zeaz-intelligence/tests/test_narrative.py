from ztrader_intel.models import NarrativeStage, SocialSnapshot
from ztrader_intel.narrative import attention_velocity


def test_organic_acceleration_is_early():
    result = attention_velocity(
        SocialSnapshot(
            mention_growth_5m=70,
            mention_growth_1h=35,
            mention_growth_24h=10,
            unique_author_growth_pct=30,
            organic_score=0.9,
            influencer_concentration=0.1,
        )
    )
    assert result.stage == NarrativeStage.EARLY
    assert result.organic_score >= 60


def test_heavily_shilled_spike_is_crowded():
    result = attention_velocity(
        SocialSnapshot(
            mention_growth_5m=95,
            mention_growth_1h=70,
            mention_growth_24h=15,
            organic_score=0.45,
            influencer_concentration=0.8,
            repeated_content_score=0.8,
            bot_score=0.6,
        )
    )
    assert result.stage == NarrativeStage.CROWDED
