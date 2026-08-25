from ai.providers._unsupported import UnsupportedProvider


class CerebrasProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("cerebras")
