from ai.providers._unsupported import UnsupportedProvider


class RunwayProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("runway")
