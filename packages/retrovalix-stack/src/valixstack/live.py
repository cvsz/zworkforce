from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LiveGate:
    enable_live: bool
    acknowledge_loss: bool
    reviewed_adapter: bool
    kill_switch_ready: bool

    @classmethod
    def from_environment(cls) -> "LiveGate":
        enabled = lambda key: os.getenv(key, "").strip() == "I_UNDERSTAND"
        return cls(
            enabled("VALIX_ENABLE_LIVE"),
            enabled("VALIX_ACKNOWLEDGE_TOTAL_LOSS"),
            enabled("VALIX_ADAPTER_REVIEWED"),
            enabled("VALIX_KILL_SWITCH_READY"),
        )

    def validate(self) -> None:
        if not all((self.enable_live, self.acknowledge_loss, self.reviewed_adapter, self.kill_switch_ready)):
            raise RuntimeError("live trading locked: all four explicit safety acknowledgements are required")
        raise NotImplementedError("no real-money venue adapter is shipped; implement and independently review one")

