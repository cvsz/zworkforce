from ai.providers._unsupported import UnsupportedProvider


class HuaweiPanguProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("huawei_pangu")
