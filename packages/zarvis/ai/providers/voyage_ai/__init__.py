from ai.providers._unsupported import UnsupportedProvider


class VoyageAiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("voyage_ai")
