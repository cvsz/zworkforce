from ai.providers._unsupported import UnsupportedProvider


class OnnxWebProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("onnx_web")
