from ai.providers._unsupported import UnsupportedProvider


class AndroidNnapiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("android_nnapi")
