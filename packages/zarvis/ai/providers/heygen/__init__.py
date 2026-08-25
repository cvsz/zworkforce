from ai.providers._unsupported import UnsupportedProvider


class HeygenProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("heygen")
