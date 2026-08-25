from ai.providers._unsupported import UnsupportedProvider


class BraveSearchApiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("brave_search_api")
