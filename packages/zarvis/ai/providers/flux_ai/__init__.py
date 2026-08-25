from ai.providers._unsupported import UnsupportedProvider


class FluxAiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("flux_ai")
