from ai.providers._unsupported import UnsupportedProvider


class ChromadbCloudProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("chromadb_cloud")
