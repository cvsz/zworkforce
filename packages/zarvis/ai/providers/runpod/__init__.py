from ai.providers._unsupported import UnsupportedProvider


class RunpodProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("runpod")
