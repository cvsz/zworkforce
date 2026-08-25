from ai.providers._unsupported import UnsupportedProvider


class ReplicateDeploymentsProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("replicate_deployments")
