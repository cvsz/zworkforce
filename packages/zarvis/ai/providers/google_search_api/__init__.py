from ai.providers._unsupported import UnsupportedProvider


class GoogleSearchApiProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("google_search_api")
