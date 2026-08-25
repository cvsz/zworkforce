from ai.providers._unsupported import UnsupportedProvider


class LmStudioProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("lm_studio")
