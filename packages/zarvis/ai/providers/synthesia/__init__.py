from ai.providers._unsupported import UnsupportedProvider


class SynthesiaProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("synthesia")
