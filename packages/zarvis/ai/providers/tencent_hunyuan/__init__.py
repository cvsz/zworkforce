from ai.providers._unsupported import UnsupportedProvider


class TencentHunyuanProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("tencent_hunyuan")
