from ai.providers._unsupported import UnsupportedProvider


class GithubCopilotProvider(UnsupportedProvider):
    def __init__(self) -> None:
        super().__init__("github_copilot")
