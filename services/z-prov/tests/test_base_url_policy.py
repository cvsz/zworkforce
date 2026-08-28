import pytest
from zeaz_agent.client import _validate_gateway_url
from zeaz_enterprise.admin import _validate_base_url as validate_admin_url
from zeaz_enterprise.agent_memory import _validate_base_url as validate_memory_url
from zeaz_enterprise.compliance import _validate_base_url as validate_compliance_url
from zeaz_enterprise.managed_agents import _validate_base_url as validate_agents_url
from zeaz_enterprise.wif import _validate_base_url as validate_wif_url
from zeaz_web.dashboard import _validate_upstream

VALIDATORS = (
    _validate_gateway_url,
    validate_admin_url,
    validate_memory_url,
    validate_compliance_url,
    validate_agents_url,
    validate_wif_url,
    _validate_upstream,
)


@pytest.mark.parametrize("validator", VALIDATORS)
@pytest.mark.parametrize(
    "url",
    (
        "https://api.example.com/v1",
        "https://api.example.com:bad",
        "https://api.example.com:70000",
    ),
)
def test_service_urls_are_strict_origins(validator, url: str) -> None:
    with pytest.raises(ValueError):
        validator(url)


@pytest.mark.parametrize("validator", VALIDATORS)
@pytest.mark.parametrize("url", ("https://api.example.com", "https://api.example.com:443"))
def test_service_urls_allow_https_origins(validator, url: str) -> None:
    validator(url)
