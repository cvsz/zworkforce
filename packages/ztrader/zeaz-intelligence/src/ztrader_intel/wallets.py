from __future__ import annotations

from collections import defaultdict

from .models import SmartMoneyRequest, SmartMoneyResponse, WhaleState


def analyze_wallet_flows(payload: SmartMoneyRequest) -> SmartMoneyResponse:
    net = 0.0
    smart_net = 0.0
    buyers: set[str] = set()
    sellers: set[str] = set()
    new_smart: set[str] = set()
    clusters: dict[str, float] = defaultdict(float)

    for transfer in payload.transfers:
        direction = transfer.direction.strip().lower()
        signed = transfer.usd_value if direction in {"buy", "in", "inflow"} else -transfer.usd_value
        net += signed

        if signed > 0:
            buyers.add(transfer.wallet)
        else:
            sellers.add(transfer.wallet)

        if transfer.is_known_smart_money:
            smart_net += signed
            if signed > 0 and transfer.is_new_wallet:
                new_smart.add(transfer.wallet)

        if transfer.linked_cluster:
            clusters[transfer.linked_cluster] += signed

    cluster_abs = sum(abs(v) for v in clusters.values())
    concentration = max((abs(v) for v in clusters.values()), default=0) / max(cluster_abs, 1)
    manipulation = min(100.0, concentration * 80 + max(0, len(sellers) - len(buyers)) * 2)

    if smart_net > 0 and len(buyers) > len(sellers):
        state = WhaleState.ACCUMULATING
    elif smart_net < 0 and len(sellers) >= len(buyers):
        state = WhaleState.DISTRIBUTING
    else:
        state = WhaleState.NEUTRAL

    return SmartMoneyResponse(
        state=state,
        net_flow_usd=round(net, 2),
        smart_money_net_usd=round(smart_net, 2),
        accumulation_wallets=len(buyers),
        distribution_wallets=len(sellers),
        new_smart_money_entries=len(new_smart),
        manipulation_risk=round(manipulation, 2),
        clusters={key: round(value, 2) for key, value in clusters.items()},
    )
