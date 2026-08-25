from ai.providers._unsupported import UnsupportedProvider


class SpeechmaticsProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("speechmatics")
