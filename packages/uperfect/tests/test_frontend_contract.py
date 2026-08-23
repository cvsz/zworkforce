from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_uses_the_api_and_bilingual_settings_contract():
    source = (ROOT / "web/app.js").read_text(encoding="utf-8")

    for route in (
        'api("/api/messages"',
        'api("/api/orders"',
        'api(`/api/orders/${',
        'api("/api/settings"',
        'api("/api/sales-assets"',
    ):
        assert route in source
    assert 'id="settings-form"' in source
    assert 'localStorage.getItem("uperfect-language")' in source
    assert '"nav.settings": "ตั้งค่า"' in source
    assert '"nav.settings": "Settings"' in source
    assert 'setting-line' in source
