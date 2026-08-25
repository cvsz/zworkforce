from ai.providers._unsupported import UnsupportedProvider


class ExaSearchProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("exa_search")
