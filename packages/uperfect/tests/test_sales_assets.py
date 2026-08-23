from pathlib import Path

from app.services.sales_assets import load_sales_assets


def test_sales_asset_pack_is_bilingual_and_uses_local_media_only():
    pack = load_sales_assets()

    required_intents = {
        "greeting",
        "product_lookup",
        "ingredients",
        "price",
        "delivery",
        "buy",
        "payment",
        "address",
        "objection",
        "fallback",
        "takeover",
    }
    assert required_intents <= set(pack["intents"])
    assert set(pack["languages"]) == {"th", "en"}
    assert {"LOE_VITC_SERUM", "MALA_CHILI_OIL", "LOE_CHARCOAL_SOAP", "CHOE_FOUNDATION", "THE_COPPER_CREAM"} <= set(
        pack["products"]
    )

    for intent in required_intents:
        assert set(pack["intents"][intent]["replies"]) == {"th", "en"}
        assert pack["intents"][intent]["keywords"]["th"]
        assert pack["intents"][intent]["keywords"]["en"]

    for product in pack["products"].values():
        assert set(product["selling_points"]) == {"th", "en"}
        assert set(product["closing_cta"]) == {"th", "en"}

    assert "loe-vitc-serum-front" not in pack["products"]["LOE_VITC_SERUM"]["asset_ids"]
    assert "loe-charcoal-soap-reference" in pack["products"]["LOE_CHARCOAL_SOAP"]["asset_ids"]

    root = Path(__file__).resolve().parents[1]
    for item in pack["asset_manifest"]["items"]:
        path = item["path"]
        assert not path.startswith(("http://", "https://"))
        assert (root / path).is_file(), path


def test_sales_assets_mark_unpriced_products_for_admin_review():
    pack = load_sales_assets()

    assert pack["products"]["LOE_VITC_SERUM"]["close_mode"] == "catalog_review"
    assert pack["products"]["MALA_CHILI_OIL"]["close_mode"] == "admin_review"
    assert pack["products"]["MALA_CHILI_OIL"]["price_verified"] is False
    assert pack["products"]["CHOE_FOUNDATION"]["catalog_status"] == "reference_only"
