from ai.providers._unsupported import UnsupportedProvider


class QdrantCloudProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("qdrant_cloud")
