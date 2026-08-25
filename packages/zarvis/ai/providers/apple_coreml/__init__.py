from ai.providers._unsupported import UnsupportedProvider


class AppleCoremlProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("apple_coreml")
