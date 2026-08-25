from ai.providers._unsupported import UnsupportedProvider


class AlibabaDashscopeProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("alibaba_dashscope")
