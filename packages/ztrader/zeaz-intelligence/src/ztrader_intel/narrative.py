from __future__ import annotations

from .models import AttentionVelocity, NarrativeStage, SocialSnapshot


def attention_velocity(social: SocialSnapshot | None) -> AttentionVelocity:
    if social is None:
        return AttentionVelocity(
            acceleration_score=-100,
            organic_score=0,
            stage=NarrativeStage.DEAD,
            reasons=["social data unavailable"],
        )

    m5 = social.mention_growth_5m or 0
    h1 = social.mention_growth_1h or 0
    h24 = social.mention_growth_24h or 0
    unique = social.unique_author_growth_pct or 0

    acceleration = (m5 * 0.5) + ((m5 - h1) * 0.25) + ((h1 - h24) * 0.15) + (unique * 0.1)
    acceleration = max(-100.0, min(100.0, acceleration))

    organic = (social.organic_score if social.organic_score is not None else 0.5) * 100
    organic -= (social.repeated_content_score or 0) * 35
    organic -= (social.bot_score or 0) * 35
    organic -= (social.influencer_concentration or 0) * 20
    organic = max(0.0, min(100.0, organic))

    reasons: list[str] = []
    if m5 > h1 > h24:
        reasons.append("mention velocity is accelerating across 24h→1h→5m")
    if unique > 0:
        reasons.append("unique-author growth is positive")
    if organic >= 65:
        reasons.append("attention appears mostly organic")
    elif organic < 35:
        reasons.append("attention shows coordinated/shill characteristics")

    if m5 >= 75 and organic < 55:
        stage = NarrativeStage.CROWDED
    elif acceleration >= 35 and organic >= 60:
        stage = NarrativeStage.EARLY
    elif acceleration >= 15 and organic >= 35:
        stage = NarrativeStage.HEATING_UP
    elif acceleration < -10:
        stage = NarrativeStage.FADING
    else:
        stage = NarrativeStage.DEAD

    return AttentionVelocity(
        acceleration_score=round(acceleration, 2),
        organic_score=round(organic, 2),
        stage=stage,
        reasons=reasons,
    )
