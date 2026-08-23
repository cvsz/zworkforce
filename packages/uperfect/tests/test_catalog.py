from decimal import Decimal


def test_keyword_match_returns_the_seeded_serum(catalog):
    product = catalog.find_by_text("สนใจวิตซีโลเอ้ มีส่วนผสมอะไร")

    assert product is not None
    assert product.id == "LOE_VITC_SERUM"
    assert product.price_thb == Decimal("98.00")
    assert len(product.ingredients) == 8
    assert "1736533886654383714" in product.source_urls[0]


def test_mala_listing_is_available_without_an_invented_price(catalog):
    product = catalog.find_by_text("น้ำพริกเสือร้องไห้")

    assert product is not None
    assert product.id == "MALA_CHILI_OIL"
    assert product.price_thb is None
    assert product.allergen_warning


def test_unknown_keyword_does_not_invent_a_product(catalog):
    assert catalog.find_by_text("ครีมที่ไม่มีในร้าน") is None
