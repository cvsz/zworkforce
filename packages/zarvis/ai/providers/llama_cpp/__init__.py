from ai.providers._unsupported import UnsupportedProvider


class LlamaCppProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("llama_cpp")
