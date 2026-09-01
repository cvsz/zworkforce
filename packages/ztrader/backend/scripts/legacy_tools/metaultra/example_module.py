"""Example Strategy Module for MetaUltra"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ExampleStrategy:
    name: str
    params: Dict[str, Any]

    def __init__(self, config: Dict[str, Any]):
        self.name = config.get("name", "example")
        self.params = config.get("params", {})

    def on_tick(self, tick: Dict[str, Any]) -> None:
        # simple placeholder processing
        print(f"{self.name} received tick {tick.get('price')}")

    def generate_signals(self) -> List[Dict[str, Any]]:
        # deterministic dummy signals
        return [{"signal": "hold", "strategy": self.name}]


if __name__ == "__main__":
    s = ExampleStrategy({"name": "demo"})
    s.on_tick({"price": 123.45})
    print(s.generate_signals())
