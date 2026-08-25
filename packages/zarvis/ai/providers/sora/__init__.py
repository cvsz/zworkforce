from ai.providers._unsupported import UnsupportedProvider


class SoraProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("sora")
