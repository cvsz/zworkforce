from ai.providers._unsupported import UnsupportedProvider


class RecraftAiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("recraft_ai")
