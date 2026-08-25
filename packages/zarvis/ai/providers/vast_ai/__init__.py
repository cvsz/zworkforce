from ai.providers._unsupported import UnsupportedProvider


class VastAiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("vast_ai")
