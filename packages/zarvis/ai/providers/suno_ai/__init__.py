from ai.providers._unsupported import UnsupportedProvider


class SunoAiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("suno_ai")
