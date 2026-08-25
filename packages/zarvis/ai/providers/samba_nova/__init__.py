from ai.providers._unsupported import UnsupportedProvider


class SambaNovaProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("samba_nova")
