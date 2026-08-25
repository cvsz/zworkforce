from ai.providers._unsupported import UnsupportedProvider


class Zero1AiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("zero1_ai")
