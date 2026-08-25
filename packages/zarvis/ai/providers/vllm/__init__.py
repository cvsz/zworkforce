from ai.providers._unsupported import UnsupportedProvider


class VllmProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("vllm")
