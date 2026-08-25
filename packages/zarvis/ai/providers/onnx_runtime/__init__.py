from ai.providers._unsupported import UnsupportedProvider


class OnnxRuntimeProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("onnx_runtime")
