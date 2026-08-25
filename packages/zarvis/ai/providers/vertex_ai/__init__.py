from ai.providers._unsupported import UnsupportedProvider


class VertexAiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("vertex_ai")
